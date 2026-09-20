"""오염도 지수(FI) 산출 및 등급 판정 (specs/07).

    [1] 잔차        r = 실측 − 기대
    [2] 평활        이동 중앙값
    [3] 정규화      SIGMA(기본) 또는 RELATIVE → 0~100
    [4] 가중 합산   FI_raw = w_dp·S_dp + w_st·S_st
    [5] 클리핑      FI = clip(FI_raw, 0, 100)
    [6] 군집 집계   군집별 FI → 표본 수 가중 평균

순수 함수 모듈 — Django 모델을 import 하지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

METHOD_SIGMA = "SIGMA"
METHOD_RELATIVE = "RELATIVE"

GRADE_NORMAL = "NORMAL"
GRADE_CAUTION = "CAUTION"
GRADE_WARNING = "WARNING"

CONFIDENCE_HIGH = "HIGH"
CONFIDENCE_MEDIUM = "MEDIUM"
CONFIDENCE_LOW = "LOW"

SIGMA_FLOOR = 1e-6  # σ≈0 하한 (specs/07 §7)

# 실제 값은 설정(out_of_domain_ratio_max)에서 읽는다 — 여기는 폴백이다.
DEFAULT_OUT_OF_DOMAIN_MAX = 0.30


@dataclass
class FoulingResult:
    points: pd.DataFrame  # 일자 × 군집별 FI (cluster_key=None 은 전체 집계)
    current_fi: float | None
    current_as_of: pd.Timestamp | None
    grade: str | None
    confidence: str
    warnings: list[dict[str, Any]] = field(default_factory=list)


# --- [1] 잔차 ---


def compute_residuals(
    frame: pd.DataFrame, expected_dp: pd.Series, expected_st: pd.Series, dp_column: str
) -> pd.DataFrame:
    """실측 − 기대. 차압 미계측 호기는 dp_column 이 gt_backpressure_kpa 가 된다."""
    out = frame.copy()
    out["expected_dp"] = expected_dp
    out["expected_st"] = expected_st
    out["measured_dp"] = frame[dp_column] if dp_column in frame.columns else np.nan
    out["measured_st"] = frame["stack_temp_c"] if "stack_temp_c" in frame.columns else np.nan
    out["residual_dp"] = out["measured_dp"] - out["expected_dp"]
    out["residual_st"] = out["measured_st"] - out["expected_st"]
    return out


# --- [2] 평활 ---


def smooth(series: pd.Series, timestamps: pd.Series, window_h: int) -> pd.Series:
    """이동 중앙값 평활 (specs/07 §3.2). 잔차는 노이즈가 커서 반드시 필요하다."""
    if series.notna().sum() == 0:
        return series
    indexed = pd.Series(series.to_numpy(), index=pd.DatetimeIndex(timestamps))
    smoothed = indexed.rolling(f"{window_h}h", min_periods=1).median()
    return pd.Series(smoothed.to_numpy(), index=series.index)


# --- [3] 정규화 ---


def normalize_sigma(residual: pd.Series, mu: float, sigma: float, sigma_ref: float) -> pd.Series:
    """z = (r − μ) / σ → clip(z / z_ref, 0, 1) × 100 (specs/07 §3.3a).

    **음의 잔차(기대보다 낮음)는 오염이 아니므로 0 으로 클리핑한다.**
    """
    sigma = max(float(sigma), SIGMA_FLOOR)
    z = (residual - mu) / sigma
    return (z / sigma_ref).clip(lower=0, upper=1) * 100


def normalize_relative_pct(measured: pd.Series, expected: pd.Series, ref_pct: float) -> pd.Series:
    """상대 편차(%) 기준 — 차압용 (specs/07 §3.3b)."""
    denominator = expected.where(expected.abs() > SIGMA_FLOOR)
    deviation = (measured - expected) / denominator * 100
    return (deviation / ref_pct).clip(lower=0, upper=1) * 100


def normalize_relative_abs(measured: pd.Series, expected: pd.Series, ref_value: float) -> pd.Series:
    """절대 편차 기준 — 스택온도는 ℃ 가 물리적으로 자연스럽다 (specs/07 §3.3b)."""
    deviation = measured - expected
    return (deviation / ref_value).clip(lower=0, upper=1) * 100


# --- [4][5] 가중 합산 + 클리핑 ---


def weighted_fi(
    score_dp: pd.Series, score_st: pd.Series, w_dp: float, w_st: float
) -> tuple[pd.Series, pd.Series]:
    """FI_raw = w_dp·S_dp + w_st·S_st → clip(0, 100).

    한쪽 신호가 결측이면 나머지 가중치를 1 로 재정규화하고 '단일 신호 기반'을 표시한다.
    Returns: (fi, single_signal_flag)
    """
    total = w_dp + w_st
    if total <= 0:
        raise ValueError("가중치 합이 0보다 커야 합니다.")
    w_dp, w_st = w_dp / total, w_st / total

    has_dp = score_dp.notna()
    has_st = score_st.notna()

    dp_part = score_dp.fillna(0) * w_dp
    st_part = score_st.fillna(0) * w_st
    weight = has_dp.astype(float) * w_dp + has_st.astype(float) * w_st

    fi = (dp_part + st_part) / weight.replace(0, np.nan)
    fi = fi.clip(lower=0, upper=100)  # [5] 0~100 클리핑 — 요구사항 명시
    single = has_dp ^ has_st
    return fi, single


# --- [6] 일별·군집별 집계 ---


def daily_points(frame: pd.DataFrame) -> pd.DataFrame:
    """일자 × 군집별 FI 시계열 (FoulingIndexPoint 의 원본)."""
    if frame.empty:
        return pd.DataFrame()

    work = frame.copy()
    work["date"] = pd.DatetimeIndex(work["timestamp"]).normalize()

    aggregations = {
        "fi_value": ("fi", "median"),
        "score_dp": ("score_dp", "median"),
        "score_st": ("score_st", "median"),
        "residual_dp": ("residual_dp", "median"),
        "residual_st": ("residual_st", "median"),
        "expected_dp": ("expected_dp", "median"),
        "expected_st": ("expected_st", "median"),
        "measured_dp": ("measured_dp", "median"),
        "measured_st": ("measured_st", "median"),
        "sample_count": ("fi", "size"),
    }

    per_cluster = (
        work.groupby(["date", "cluster_key"], dropna=True).agg(**aggregations).reset_index()
    )

    # 전체 집계는 군집별 FI 를 표본 수로 가중 평균한다 (specs/07 §3.6)
    overall = _weighted_overall(per_cluster)
    return pd.concat([overall, per_cluster], ignore_index=True)


def _weighted_overall(per_cluster: pd.DataFrame) -> pd.DataFrame:
    if per_cluster.empty:
        return pd.DataFrame()

    rows = []
    for date, group in per_cluster.groupby("date"):
        weights = group["sample_count"].to_numpy(dtype=float)
        if weights.sum() == 0:
            continue
        row: dict[str, Any] = {"date": date, "cluster_key": None}
        for column in (
            "fi_value",
            "score_dp",
            "score_st",
            "residual_dp",
            "residual_st",
            "expected_dp",
            "expected_st",
            "measured_dp",
            "measured_st",
        ):
            values = group[column].to_numpy(dtype=float)
            mask = ~np.isnan(values)
            row[column] = (
                float(np.average(values[mask], weights=weights[mask])) if mask.any() else np.nan
            )
        row["sample_count"] = int(weights.sum())
        rows.append(row)
    return pd.DataFrame(rows)


# --- 등급 / 현재 지수 / 신뢰도 ---


def grade_of(fi: float | None, caution_min: float, warning_min: float) -> str | None:
    if fi is None or (isinstance(fi, float) and np.isnan(fi)):
        return None
    if fi >= warning_min:
        return GRADE_WARNING
    if fi >= caution_min:
        return GRADE_CAUTION
    return GRADE_NORMAL


def current_value(daily: pd.DataFrame, window_days: int) -> tuple[float | None, Any]:
    """최근 window_days 의 FI_daily 중앙값 = 현재 오염도 지수 (specs/07 §3.7).

    최근 창에 유효 데이터가 없으면 가장 최근 유효일 기준으로 계산하고 기준일을 함께 돌려준다.
    """
    overall = daily[daily["cluster_key"].isna()].dropna(subset=["fi_value"]).copy()
    if overall.empty:
        return None, None

    overall["date"] = pd.to_datetime(overall["date"])
    last_date = pd.Timestamp(overall["date"].max())
    cutoff = last_date - pd.Timedelta(days=int(window_days))
    window = overall[overall["date"] > cutoff]
    if window.empty:
        window = overall.tail(1)
    return float(window["fi_value"].median()), last_date


def confidence_of(
    model_grades: list[str],
    valid_points: int,
    min_points: int,
    out_of_domain_ratio: float,
    out_of_domain_max: float = DEFAULT_OUT_OF_DOMAIN_MAX,
) -> str:
    """신뢰도 등급 (specs/07 §5). 도메인 밖 허용 비율은 설정값이다."""
    if (
        "POOR" in model_grades
        or valid_points < min_points
        or out_of_domain_ratio > out_of_domain_max
    ):
        return CONFIDENCE_LOW
    if "FAIR" in model_grades:
        return CONFIDENCE_MEDIUM
    return CONFIDENCE_HIGH


# --- 전체 파이프라인 ---


def compute(
    frame: pd.DataFrame,
    config: dict[str, Any],
    residual_stats: dict[str, dict[str, float]],
    model_grades: list[str] | None = None,
    out_of_domain_ratio: float = 0.0,
) -> FoulingResult:
    """잔차가 채워진 프레임에서 FI 시계열과 현재 지수를 산출한다.

    residual_stats: {"dp": {"mean":…, "std":…}, "st": {...}} — ModelVersion 에 저장된 값.
    """
    warnings: list[dict[str, Any]] = []
    work = frame.copy()

    if work.empty:
        return FoulingResult(pd.DataFrame(), None, None, None, CONFIDENCE_LOW)

    window_h = config["smoothing_window_h"]
    work["residual_dp_s"] = smooth(work["residual_dp"], work["timestamp"], window_h)
    work["residual_st_s"] = smooth(work["residual_st"], work["timestamp"], window_h)

    method = config["normalization_method"]
    if method == METHOD_RELATIVE:
        work["score_dp"] = normalize_relative_pct(
            work["measured_dp"], work["expected_dp"], config["dp_ref_pct"]
        )
        work["score_st"] = normalize_relative_abs(
            work["measured_st"], work["expected_st"], config["st_ref_c"]
        )
    else:
        work["score_dp"] = normalize_sigma(
            work["residual_dp_s"],
            residual_stats["dp"]["mean"],
            residual_stats["dp"]["std"],
            config["sigma_ref"],
        )
        work["score_st"] = normalize_sigma(
            work["residual_st_s"],
            residual_stats["st"]["mean"],
            residual_stats["st"]["std"],
            config["sigma_ref"],
        )

    w_dp, w_st = _normalized_weights(config, warnings)
    work["fi"], single = weighted_fi(work["score_dp"], work["score_st"], w_dp, w_st)
    if single.any():
        warnings.append(
            {
                "code": "SINGLE_SIGNAL",
                "message": "한쪽 신호가 결측이어서 단일 신호 기반으로 산출된 구간이 있습니다.",
                "details": {"points": int(single.sum())},
            }
        )

    if config.get("drop_sparse_clusters", True) and "is_sparse" in work.columns:
        work = work[~work["is_sparse"]]

    daily = daily_points(work)
    if daily.empty:
        return FoulingResult(daily, None, None, None, CONFIDENCE_LOW, warnings)

    fi_now, as_of = current_value(daily, config["current_window_days"])
    grade = grade_of(fi_now, config["grade_caution_min"], config["grade_warning_min"])

    confidence = confidence_of(
        model_grades or [],
        valid_points=len(work),
        min_points=config["min_valid_points"],
        out_of_domain_ratio=out_of_domain_ratio,
        out_of_domain_max=float(config.get("out_of_domain_ratio_max", DEFAULT_OUT_OF_DOMAIN_MAX)),
    )

    daily["grade"] = daily["fi_value"].map(
        lambda v: grade_of(v, config["grade_caution_min"], config["grade_warning_min"])
    )
    daily["confidence"] = confidence

    _append_sanity_warnings(daily, fi_now, warnings)
    return FoulingResult(daily, fi_now, as_of, grade, confidence, warnings)


def _normalized_weights(config: dict[str, Any], warnings: list[dict]) -> tuple[float, float]:
    w_dp = float(config["weight_dp"])
    w_st = float(config["weight_stack_temp"])
    total = w_dp + w_st
    if abs(total - 1.0) > 1e-6:
        warnings.append(
            {
                "code": "WEIGHTS_NORMALIZED",
                "message": "가중치 합이 1이 아니어서 자동 정규화했습니다.",
                "details": {"weight_dp": w_dp, "weight_stack_temp": w_st},
            }
        )
    return w_dp, w_st


def _append_sanity_warnings(
    daily: pd.DataFrame, fi_now: float | None, warnings: list[dict]
) -> None:
    """정규화 기준값이 잘못됐을 가능성을 알린다 (specs/07 §7)."""
    overall = daily[daily["cluster_key"].isna()].dropna(subset=["fi_value"])
    if overall.empty:
        return

    saturated = (overall["fi_value"] >= 99.9).mean()
    if saturated > 0.5:
        warnings.append(
            {
                "code": "FI_SATURATED",
                "message": (
                    "FI가 장기간 100에 고정되어 있습니다. "
                    "정규화 기준값(sigma_ref / dp_ref_pct)이 과소 설정되었을 수 있습니다."
                ),
                "details": {"saturated_ratio": round(float(saturated), 4)},
            }
        )
