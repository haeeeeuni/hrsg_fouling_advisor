"""세정 전후 비교 (specs/12 §2).

**같은 운전 구간끼리만 비교한다.** 부하·외기 조건이 다르면 차압과 스택온도가
자연히 달라지므로, 조건을 맞추지 않은 비교는 무의미하다.

잔차 기반 비교를 **주 지표**로, 원시 평균 비교는 참고 지표로 둔다(운전 조건 차이를 보정하므로).

순수 함수 모듈 — Django 모델을 import 하지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

# 비교 지표 정의: (키, 라벨, 컬럼, 소수자리, 개선율 표기 여부)
METRICS: tuple[tuple[str, str, str, int, bool], ...] = (
    ("fi", "오염도 지수 FI", "fi", 1, True),
    ("dp", "평균 차압 (kPa)", "measured_dp", 2, True),
    ("residual_dp", "차압 잔차 (kPa)", "residual_dp", 2, False),
    ("stack", "평균 스택온도 (℃)", "measured_st", 1, True),
    ("residual_st", "스택온도 잔차 (℃)", "residual_st", 1, False),
    ("power", "평균 GT 출력 (MW)", "gt_power_mw", 1, True),
)

# 주 지표 — 운전 조건이 보정된 잔차 기반
PRIMARY_METRICS = ("residual_dp", "residual_st", "fi")


@dataclass
class ComparisonWindows:
    before_start: pd.Timestamp
    before_end: pd.Timestamp
    after_start: pd.Timestamp
    after_end: pd.Timestamp


@dataclass
class ComparisonResult:
    windows: ComparisonWindows
    metrics: dict[str, Any] = field(default_factory=dict)
    cluster_metrics: list[dict[str, Any]] = field(default_factory=list)
    p_values: dict[str, Any] = field(default_factory=dict)
    common_clusters: list[str] = field(default_factory=list)
    recovery_ratio: float | None = None
    warnings: list[dict[str, Any]] = field(default_factory=list)

    @property
    def is_comparable(self) -> bool:
        return bool(self.common_clusters)


def build_windows(
    cleaned_at: pd.Timestamp,
    cleaned_end_at: pd.Timestamp | None,
    window_days: int = 30,
    before_offset_days: int = 0,
    after_offset_days: int = 1,
) -> ComparisonWindows:
    """비교 구간 산정 (specs/12 §2.2)."""
    end_at = cleaned_end_at or cleaned_at
    before_end = cleaned_at - pd.Timedelta(days=int(before_offset_days))
    after_start = end_at + pd.Timedelta(days=int(after_offset_days))
    return ComparisonWindows(
        before_start=before_end - pd.Timedelta(days=int(window_days)),
        before_end=before_end,
        after_start=after_start,
        after_end=after_start + pd.Timedelta(days=int(window_days)),
    )


def slice_window(frame: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    return frame[(frame["timestamp"] >= start) & (frame["timestamp"] < end)]


def _summary(frame: pd.DataFrame, column: str) -> float | None:
    if column not in frame.columns:
        return None
    values = frame[column].dropna()
    return float(values.mean()) if len(values) else None


def _delta_row(
    key: str, label: str, before: float | None, after: float | None, digits: int, show_pct: bool
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "key": key,
        "label": label,
        "before": round(before, digits) if before is not None else None,
        "after": round(after, digits) if after is not None else None,
        "delta": None,
        "delta_pct": None,
        "is_primary": key in PRIMARY_METRICS,
    }
    if before is None or after is None:
        return row
    row["delta"] = round(after - before, digits)
    if show_pct and abs(before) > 1e-9:
        row["delta_pct"] = round((after - before) / abs(before) * 100, 1)
    return row


def _test_difference(before: pd.Series, after: pd.Series) -> dict[str, Any]:
    """군집별 잔차 평균 차이의 통계적 유의성 (specs/12 §2.3).

    정규성을 가정하기 어려우므로 t-검정과 Mann–Whitney U 를 함께 낸다.
    """
    from scipy import stats

    a = before.dropna().to_numpy()
    b = after.dropna().to_numpy()
    if len(a) < 3 or len(b) < 3:
        return {"t_p_value": None, "u_p_value": None, "n_before": len(a), "n_after": len(b)}

    result: dict[str, Any] = {"n_before": int(len(a)), "n_after": int(len(b))}
    try:
        result["t_p_value"] = float(stats.ttest_ind(a, b, equal_var=False).pvalue)
    except Exception:  # noqa: BLE001
        result["t_p_value"] = None
    try:
        result["u_p_value"] = float(stats.mannwhitneyu(a, b, alternative="two-sided").pvalue)
    except Exception:  # noqa: BLE001
        result["u_p_value"] = None
    return result


def compare(
    frame: pd.DataFrame,
    windows: ComparisonWindows,
    min_cluster_points: int = 200,
) -> ComparisonResult:
    """전/후 구간을 공통 군집에서만 비교한다.

    frame 은 정제·군집화·잔차 계산이 끝난 유효(STEADY) 데이터여야 한다.
    """
    warnings: list[dict[str, Any]] = []
    before = slice_window(frame, windows.before_start, windows.before_end)
    after = slice_window(frame, windows.after_start, windows.after_end)

    result = ComparisonResult(windows=windows, warnings=warnings)

    if before.empty or after.empty:
        warnings.append(
            {
                "code": "WINDOW_EMPTY",
                "message": "비교 구간에 유효 데이터가 없습니다.",
                "details": {"before": len(before), "after": len(after)},
            }
        )
        return result

    # 양쪽 모두 표본이 충분한 **공통 군집**만 쓴다 (AC-12-5)
    before_counts = before["cluster_key"].value_counts()
    after_counts = after["cluster_key"].value_counts()
    common = sorted(
        key
        for key in set(before_counts.index) & set(after_counts.index)
        if before_counts[key] >= min_cluster_points and after_counts[key] >= min_cluster_points
    )
    result.common_clusters = common

    if not common:
        warnings.append(
            {
                "code": "NO_COMMON_CLUSTER",
                "message": (
                    "비교 가능한 동일 운전 조건 구간이 없습니다. "
                    "비교 윈도를 넓히거나 표본 기준을 완화해 보세요."
                ),
                "details": {
                    "before_clusters": before_counts.to_dict(),
                    "after_clusters": after_counts.to_dict(),
                },
            }
        )
        return result

    before = before[before["cluster_key"].isin(common)]
    after = after[after["cluster_key"].isin(common)]

    # --- 군집별 비교 ---
    cluster_rows: list[dict[str, Any]] = []
    for key in common:
        b = before[before["cluster_key"] == key]
        a = after[after["cluster_key"] == key]
        row = {
            "cluster_key": key,
            "n_before": int(len(b)),
            "n_after": int(len(a)),
            "metrics": [
                _delta_row(k, label, _summary(b, col), _summary(a, col), digits, pct)
                for k, label, col, digits, pct in METRICS
            ],
            "p_values": {
                "residual_dp": _test_difference(
                    b.get("residual_dp", pd.Series(dtype=float)),
                    a.get("residual_dp", pd.Series(dtype=float)),
                ),
                "residual_st": _test_difference(
                    b.get("residual_st", pd.Series(dtype=float)),
                    a.get("residual_st", pd.Series(dtype=float)),
                ),
            },
        }
        cluster_rows.append(row)
    result.cluster_metrics = cluster_rows

    # --- 표본 가중 종합 ---
    weights = np.array([row["n_before"] + row["n_after"] for row in cluster_rows], dtype=float)
    overall: list[dict[str, Any]] = []
    for key, label, _column, digits, pct in METRICS:
        befores, afters, used = [], [], []
        for row, weight in zip(cluster_rows, weights, strict=True):
            metric = next(m for m in row["metrics"] if m["key"] == key)
            if metric["before"] is None or metric["after"] is None:
                continue
            befores.append(metric["before"])
            afters.append(metric["after"])
            used.append(weight)
        if not used:
            overall.append(_delta_row(key, label, None, None, digits, pct))
            continue
        overall.append(
            _delta_row(
                key,
                label,
                float(np.average(befores, weights=used)),
                float(np.average(afters, weights=used)),
                digits,
                pct,
            )
        )

    result.metrics = {
        "rows": overall,
        "n_before": int(len(before)),
        "n_after": int(len(after)),
        "cluster_count": len(common),
    }
    result.p_values = {
        "residual_dp": _test_difference(before.get("residual_dp"), after.get("residual_dp")),
        "residual_st": _test_difference(before.get("residual_st"), after.get("residual_st")),
    }

    # 회복률 = (FI_before − FI_after) / FI_before  (specs/12 §2.5)
    fi_row = next((row for row in overall if row["key"] == "fi"), None)
    if fi_row and fi_row["before"] and fi_row["before"] > 0 and fi_row["after"] is not None:
        result.recovery_ratio = round((fi_row["before"] - fi_row["after"]) / fi_row["before"], 4)

    return result
