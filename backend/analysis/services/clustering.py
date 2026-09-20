"""부하대·계절 군집화 (specs/05).

차압과 스택온도는 부하와 외기 조건에 크게 좌우된다. 비교의 공정성을 확보하기 위해
운전 구간을 부하대 × 계절로 나누고, 이후 모든 비교를 **같은 군집 안에서** 수행한다.

순수 함수 모듈 — Django 모델을 import 하지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from common.constants import RANDOM_SEED

METHOD_RULE = "RULE"
METHOD_KMEANS = "KMEANS"

LOAD_BANDS = ("L1", "L2", "L3", "L4")
LOAD_BAND_LABELS = {"L1": "저부하", "L2": "중부하", "L3": "고부하", "L4": "정격"}
SEASON_LABELS = {"SP": "봄", "SU": "여름", "FA": "가을", "WI": "겨울"}

# KMeans 도메인 판정에 쓰는 기본 피처 (specs/05 §2.2)
KMEANS_FEATURES = ("gt_power_mw", "ambient_temp_c", "exhaust_flow", "gt_exhaust_temp_c")


@dataclass
class ClusterResult:
    frame: pd.DataFrame  # load_band / season / cluster_key / is_sparse 포함
    summary: pd.DataFrame  # 군집별 요약 (specs/05 §5)
    params: dict[str, Any] = field(default_factory=dict)
    warnings: list[dict[str, Any]] = field(default_factory=list)


def assign_load_band(load_ratio_pct: pd.Series, edges: list[float]) -> pd.Series:
    """부하율(%) → L1~L4 (specs/05 §2.1).

    edges = [40, 60, 80, 95] 이면 L1:40~60, L2:60~80, L3:80~95, L4:95 초과.
    """
    bounds = [*sorted(edges), np.inf]
    labels = LOAD_BANDS[: len(bounds) - 1]
    return pd.cut(load_ratio_pct, bins=bounds, labels=labels, right=False).astype(object)


def assign_season(
    timestamps: pd.Series, ambient_temp_c: pd.Series | None, definition: str
) -> pd.Series:
    """계절 판정 (specs/05 §2.1).

    TEMP 모드에서 10~20 ℃ 구간은 봄·가을이 겹치므로 월 정보를 병용해 가른다.
    """
    month = pd.DatetimeIndex(timestamps).month

    if definition == "TEMP" and ambient_temp_c is not None:
        season = pd.Series("SP", index=timestamps.index, dtype=object)
        season[ambient_temp_c > 20] = "SU"
        season[ambient_temp_c < 10] = "WI"
        mid = (ambient_temp_c >= 10) & (ambient_temp_c <= 20)
        season[mid & (month >= 7)] = "FA"
        season[mid & (month < 7)] = "SP"
        return season

    conditions = [
        (month >= 3) & (month <= 5),
        (month >= 6) & (month <= 8),
        (month >= 9) & (month <= 11),
    ]
    return pd.Series(
        np.select(conditions, ["SP", "SU", "FA"], default="WI"),
        index=timestamps.index,
        dtype=object,
    )


def _fit_kmeans(frame: pd.DataFrame, k: int) -> tuple[dict[str, Any], list[str]]:
    from sklearn.cluster import KMeans
    from sklearn.preprocessing import StandardScaler

    features = [c for c in KMEANS_FEATURES if c in frame.columns and frame[c].notna().any()]
    data = frame[features].dropna()
    if len(data) < k:
        raise ValueError("KMeans 학습에 필요한 표본이 부족합니다.")

    scaler = StandardScaler().fit(data)
    model = KMeans(n_clusters=k, random_state=RANDOM_SEED, n_init=10).fit(scaler.transform(data))

    # 군집 번호가 재실행마다 뒤바뀌지 않도록 중심을 정렬해 고정한다 (AC-05-3).
    centers = model.cluster_centers_
    order = np.lexsort(centers.T[::-1])
    centers = centers[order]

    params = {
        "features": features,
        "scaler_mean": scaler.mean_.tolist(),
        "scaler_scale": scaler.scale_.tolist(),
        "centers": centers.tolist(),
        "k": k,
    }
    return params, features


def _assign_kmeans(frame: pd.DataFrame, params: dict[str, Any]) -> pd.Series:
    """저장된 중심에 대해 최근접 할당 — 재계산해도 라벨이 유지된다 (AC-05-3)."""
    features = params["features"]
    mean = np.asarray(params["scaler_mean"])
    scale = np.asarray(params["scaler_scale"])
    centers = np.asarray(params["centers"])

    values = frame[features].to_numpy(dtype=float)
    scaled = (values - mean) / np.where(scale == 0, 1, scale)

    keys = pd.Series("", index=frame.index, dtype=object)
    usable = ~np.isnan(scaled).any(axis=1)
    if usable.any():
        distances = ((scaled[usable][:, None, :] - centers[None, :, :]) ** 2).sum(axis=2)
        keys.loc[frame.index[usable]] = [f"K{i}" for i in distances.argmin(axis=1)]
    keys.loc[frame.index[~usable]] = None
    return keys


def mahalanobis_distance(frame: pd.DataFrame, params: dict[str, Any]) -> pd.Series:
    """학습 분포 대비 마할라노비스 거리 (specs/05 §6, specs/06 §10).

    거리가 임계를 넘으면 OUT_OF_DOMAIN — 기대값 신뢰도를 낮춘다.
    """
    features = params.get("features") or []
    available = [c for c in features if c in frame.columns]
    if not available or "inv_cov" not in params:
        return pd.Series(np.nan, index=frame.index)

    mean = np.asarray(params["domain_mean"])
    inv_cov = np.asarray(params["inv_cov"])
    values = frame[available].to_numpy(dtype=float)

    result = np.full(len(frame), np.nan)
    usable = ~np.isnan(values).any(axis=1)
    if usable.any():
        delta = values[usable] - mean
        result[usable] = np.sqrt(np.einsum("ij,jk,ik->i", delta, inv_cov, delta))
    return pd.Series(result, index=frame.index)


def build_domain_params(frame: pd.DataFrame, features: list[str]) -> dict[str, Any]:
    """도메인 판정용 평균·공분산 역행렬을 만든다."""
    available = [c for c in features if c in frame.columns]
    data = frame[available].dropna()
    if len(data) < len(available) + 2:
        return {}
    cov = np.cov(data.to_numpy(dtype=float), rowvar=False)
    try:
        inv_cov = np.linalg.pinv(np.atleast_2d(cov))
    except np.linalg.LinAlgError:  # pragma: no cover
        return {}
    return {
        "features": available,
        "domain_mean": data.mean().to_numpy().tolist(),
        "inv_cov": inv_cov.tolist(),
    }


def cluster(
    frame: pd.DataFrame, config: dict[str, Any], params: dict[str, Any] | None = None
) -> ClusterResult:
    """군집 키를 부여하고 군집별 요약을 만든다.

    params 가 주어지면(재계산·신규 데이터 할당) 그 정의를 그대로 쓴다.
    """
    out = frame.copy()
    warnings: list[dict[str, Any]] = []
    method = (params or {}).get("method") or config["cluster_method"]

    rated = config["rated_power_mw"]
    out["load_ratio_pct"] = out["gt_power_mw"] / rated * 100

    if method == METHOD_KMEANS:
        try:
            if params and "centers" in params:
                kmeans_params = params
            else:
                kmeans_params, _ = _fit_kmeans(out, config["kmeans_k"])
                kmeans_params["method"] = METHOD_KMEANS
            out["cluster_key"] = _assign_kmeans(out, kmeans_params)
            out["load_band"] = assign_load_band(out["load_ratio_pct"], config["load_band_edges"])
            out["season"] = assign_season(
                out["timestamp"], out.get("ambient_temp_c"), config["season_definition"]
            )
            active_params = kmeans_params
        except (ValueError, ImportError) as exc:
            # 수렴 실패·표본 부족 시 RULE 로 폴백하고 사유를 남긴다 (specs/05 §6).
            warnings.append(
                {
                    "code": "KMEANS_FALLBACK",
                    "message": "KMeans 군집화에 실패해 규칙 기반으로 전환했습니다.",
                    "details": {"reason": str(exc)},
                }
            )
            method = METHOD_RULE
            active_params = {}
    else:
        active_params = {}

    if method == METHOD_RULE:
        out["load_band"] = assign_load_band(out["load_ratio_pct"], config["load_band_edges"])
        out["season"] = assign_season(
            out["timestamp"], out.get("ambient_temp_c"), config["season_definition"]
        )
        out["cluster_key"] = out["load_band"].astype(str) + "-" + out["season"].astype(str)
        out.loc[out["load_band"].isna(), "cluster_key"] = None
        active_params = {
            "method": METHOD_RULE,
            "load_band_edges": config["load_band_edges"],
            "season_definition": config["season_definition"],
        }

    # 희소 군집 판정 (specs/05 §3)
    counts = out["cluster_key"].value_counts()
    sparse_keys = set(counts[counts < config["min_cluster_points"]].index)
    out["is_sparse"] = out["cluster_key"].isin(sparse_keys)

    # 도메인 판정 파라미터 (기대값 신뢰도에 사용)
    domain = build_domain_params(out, list(KMEANS_FEATURES))
    active_params.update(domain)

    summary = summarize(out, sparse_keys)

    if len(counts) <= 1:
        warnings.append(
            {
                "code": "SINGLE_CLUSTER",
                "message": "운전 조건 다양성이 부족합니다(유효 군집 1개).",
                "details": {"cluster_count": int(len(counts))},
            }
        )
    if sparse_keys:
        warnings.append(
            {
                "code": "SPARSE_CLUSTERS",
                "message": "표본이 부족한 군집이 있습니다.",
                "details": {"keys": sorted(sparse_keys)},
            }
        )

    return ClusterResult(frame=out, summary=summary, params=active_params, warnings=warnings)


def summarize(frame: pd.DataFrame, sparse_keys: set[str]) -> pd.DataFrame:
    """군집별 요약 테이블 (specs/05 §5)."""
    if frame.empty or "cluster_key" not in frame.columns:
        return pd.DataFrame()

    aggregations: dict[str, Any] = {"sample_count": ("cluster_key", "size")}
    for column, name in (
        ("load_ratio_pct", "avg_load_ratio_pct"),
        ("ambient_temp_c", "avg_ambient_temp_c"),
        ("hrsg_gas_dp_kpa", "avg_dp_kpa"),
        ("stack_temp_c", "avg_stack_temp_c"),
    ):
        if column in frame.columns:
            aggregations[name] = (column, "mean")

    summary = frame.groupby("cluster_key", dropna=True).agg(**aggregations).reset_index()
    total = summary["sample_count"].sum()
    summary["share_pct"] = (summary["sample_count"] / total * 100).round(2) if total else 0.0
    summary["is_sparse"] = summary["cluster_key"].isin(sparse_keys)
    summary["label"] = summary["cluster_key"].map(_cluster_label)
    return summary.sort_values("sample_count", ascending=False).reset_index(drop=True)


def _cluster_label(key: str) -> str:
    if not isinstance(key, str) or "-" not in key:
        return str(key)
    band, season = key.split("-", 1)
    return f"{LOAD_BAND_LABELS.get(band, band)}·{SEASON_LABELS.get(season, season)}"
