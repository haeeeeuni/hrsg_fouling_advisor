"""데이터 정제 (specs/04 §4~6).

Django 모델을 import 하지 않는 순수 함수 모듈이다(AGENTS.md §3).
입출력은 DataFrame / dataclass / dict 다.

**원본은 절대 수정하지 않는다.** 이 모듈은 항상 새 DataFrame 을 돌려준다(AC-04-5).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from units.standard_fields import NUMERIC_FIELDS, TIMESTAMP

# 이 항목들이 결측이면 해당 행 자체를 분석에서 제외한다 (specs/04 §4).
CORE_FIELDS: tuple[str, ...] = ("gt_power_mw", "stack_temp_c")
DP_FIELDS: tuple[str, ...] = ("hrsg_gas_dp_kpa", "gt_backpressure_kpa")

MAD_SCALE = 1.4826  # 정규분포에서 MAD → 표준편차 환산 상수


@dataclass
class CleaningResult:
    frame: pd.DataFrame
    stats: dict[str, Any] = field(default_factory=dict)
    warnings: list[dict[str, Any]] = field(default_factory=list)
    excluded_features: list[str] = field(default_factory=list)


def sort_and_dedupe(frame: pd.DataFrame) -> pd.DataFrame:
    """타임스탬프 정렬 + 중복 제거(마지막 값 우선)."""
    out = frame.sort_values(TIMESTAMP, kind="stable")
    return out[~out[TIMESTAMP].duplicated(keep="last")].reset_index(drop=True)


def apply_physical_ranges(
    frame: pd.DataFrame, ranges: dict[str, tuple]
) -> tuple[pd.DataFrame, int]:
    """물리 범위 하드 필터 — 벗어난 값은 NaN (specs/04 §5.1)."""
    out = frame.copy()
    removed = 0
    for column, (low, high) in ranges.items():
        if column not in out.columns:
            continue
        values = out[column]
        outside = pd.Series(False, index=out.index)
        if low is not None:
            outside |= values < low
        if high is not None:
            outside |= values > high
        outside &= values.notna()
        removed += int(outside.sum())
        out.loc[outside, column] = np.nan
    return out, removed


def fill_short_gaps(frame: pd.DataFrame, max_points: int) -> tuple[pd.DataFrame, int]:
    """연속 결측이 max_points 이하인 구간만 시간 기준 선형 보간 (specs/04 §4)."""
    if max_points <= 0:
        return frame.copy(), 0

    out = frame.copy()
    indexed = out.set_index(TIMESTAMP)
    filled_total = 0

    for column in NUMERIC_FIELDS:
        if column not in indexed.columns:
            continue
        series = indexed[column]
        if series.notna().sum() < 2:
            continue
        was_na = series.isna()
        interpolated = series.interpolate(method="time", limit=max_points, limit_area="inside")
        filled = was_na & interpolated.notna()
        filled_total += int(filled.sum())
        indexed[column] = interpolated

    out = indexed.reset_index()
    return out, filled_total


def detect_outliers_mad(
    series: pd.Series, timestamps: pd.Series, window_h: int, k: float
) -> pd.Series:
    """롤링 로버스트 이상치 (specs/04 §5.2).

    |x - median| > k × 1.4826 × MAD 를 이상치로 본다.

    윈도를 24시간 이상으로 잡고 k 를 보수적으로 두는 이유는, 오염에 의한 **완만한 상승**을
    제거하지 않기 위해서다(AC-04-3). 중앙값이 추세를 따라가므로 짧은 스파이크만 걸린다.
    """
    if series.notna().sum() < 3:
        return pd.Series(False, index=series.index)

    indexed = pd.Series(series.to_numpy(), index=pd.DatetimeIndex(timestamps))
    window = f"{window_h}h"
    median = indexed.rolling(window, center=True, min_periods=3).median()
    deviation = (indexed - median).abs()
    mad = deviation.rolling(window, center=True, min_periods=3).median()

    threshold = k * MAD_SCALE * mad
    # MAD 가 0 에 가까우면(값이 거의 일정) 임계가 0 이 되어 전부 이상치가 된다.
    # 그런 구간은 건너뛴다.
    valid = threshold > 0
    flagged = (deviation > threshold) & valid & indexed.notna()
    return pd.Series(flagged.to_numpy(), index=series.index)


def detect_stuck(series: pd.Series, min_points: int) -> pd.Series:
    """동일 값이 연속 min_points 이상 반복되면 계측기 고착 (specs/04 §5.3)."""
    if len(series) == 0 or min_points <= 1:
        return pd.Series(False, index=series.index)

    values = series.to_numpy()
    # 값이 바뀔 때마다 증가하는 그룹 번호
    changed = np.ones(len(values), dtype=bool)
    changed[1:] = ~((values[1:] == values[:-1]) & ~pd.isna(values[1:]) & ~pd.isna(values[:-1]))
    groups = np.cumsum(changed)
    counts = pd.Series(groups).map(pd.Series(groups).value_counts())
    return pd.Series((counts.to_numpy() >= min_points) & ~pd.isna(values), index=series.index)


def detect_step_changes(
    series: pd.Series, timestamps: pd.Series, sigma_multiple: float, window_h: int = 6
) -> list[dict[str, Any]]:
    """단차(계측기 교정/교체 의심) 탐지 — **제외하지 않고 경고만** 한다 (specs/04 §5.4)."""
    if series.notna().sum() < 10:
        return []

    indexed = pd.Series(series.to_numpy(), index=pd.DatetimeIndex(timestamps)).dropna()
    window = f"{window_h}h"
    trailing = indexed.rolling(window, min_periods=3).mean()
    leading = indexed[::-1].rolling(window, min_periods=3).mean()[::-1]

    gap = (leading - trailing).abs()

    # 인접 6시간 평균의 차이가 전체 표준편차의 sigma_multiple 배를 넘으면 단차로 본다.
    spread = float(indexed.std())
    if not np.isfinite(spread) or spread == 0:
        return []
    threshold = sigma_multiple * spread

    flagged = gap > threshold
    if not flagged.any():
        return []

    # 연속 구간의 대표 시점만 보고한다.
    marks = flagged[flagged].index
    events: list[dict[str, Any]] = []
    last: pd.Timestamp | None = None
    for mark in marks:
        if last is not None and (mark - last) < pd.Timedelta(hours=window_h):
            continue
        events.append({"at": mark.isoformat(), "gap": round(float(gap.loc[mark]), 4)})
        last = mark
    return events


def resample(frame: pd.DataFrame, interval_min: int) -> pd.DataFrame:
    """분석 표준 주기로 다운샘플링 (specs/04 §6).

    duct_burner_on 은 max — 한 번이라도 ON 이면 ON 으로 본다.
    유효 비율이 50% 미만인 구간은 버린다.
    """
    if interval_min <= 0:
        return frame.copy()

    indexed = frame.set_index(TIMESTAMP).sort_index()
    rule = f"{interval_min}min"

    numeric_cols = [c for c in NUMERIC_FIELDS if c in indexed.columns]
    aggregated = indexed[numeric_cols].resample(rule).mean() if numeric_cols else pd.DataFrame()

    if "duct_burner_on" in indexed.columns:
        burner = indexed["duct_burner_on"].astype("float").resample(rule).max()
        aggregated["duct_burner_on"] = burner.map(lambda v: None if pd.isna(v) else bool(v))

    # 구간 내 원시 포인트 중 유효 비율이 절반 미만이면 버린다.
    counts = indexed[numeric_cols].resample(rule).count() if numeric_cols else None
    sizes = indexed.resample(rule).size()
    if counts is not None and len(counts):
        ratio = counts.max(axis=1) / sizes.replace(0, np.nan)
        aggregated = aggregated[(ratio.fillna(0) >= 0.5) & (sizes > 0)]

    return aggregated.reset_index()


def drop_rows_missing_core(frame: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """필수 분석 항목이 결측인 행을 제외한다 (specs/04 §4)."""
    out = frame.copy()
    mask = pd.Series(True, index=out.index)

    for column in CORE_FIELDS:
        if column in out.columns:
            mask &= out[column].notna()

    available_dp = [c for c in DP_FIELDS if c in out.columns]
    if available_dp:
        dp_present = pd.Series(False, index=out.index)
        for column in available_dp:
            dp_present |= out[column].notna()
        mask &= dp_present

    dropped = int((~mask).sum())
    return out[mask].reset_index(drop=True), dropped


def high_missing_columns(frame: pd.DataFrame, max_rate_pct: float) -> list[str]:
    """결측률이 임계를 넘어 피처에서 제외할 컬럼 (specs/04 §4)."""
    if frame.empty:
        return []
    excluded = []
    for column in NUMERIC_FIELDS:
        if column not in frame.columns:
            continue
        rate = frame[column].isna().mean() * 100
        if rate > max_rate_pct:
            excluded.append(column)
    return excluded


def clean(frame: pd.DataFrame, config: dict[str, Any], ranges: dict[str, tuple]) -> CleaningResult:
    """정제 파이프라인 전체 (specs/04 §2 의 1~4단계).

    구간 분류(5~6단계)는 segmentation.py 가 이어받는다.
    """
    stats: dict[str, Any] = {"row_input": len(frame)}
    warnings: list[dict[str, Any]] = []

    if frame.empty:
        return CleaningResult(frame=frame.copy(), stats={**stats, "row_output": 0})

    work = sort_and_dedupe(frame)
    stats["row_deduped"] = stats["row_input"] - len(work)

    work, out_of_range = apply_physical_ranges(work, ranges)
    stats["cells_out_of_range"] = out_of_range

    # 이상치·고착 탐지는 보간 전에 한다(보간값이 판정을 흐리지 않도록).
    online = (
        work["gt_power_mw"] >= config["min_load_mw"]
        if "gt_power_mw" in work.columns
        else pd.Series(True, index=work.index)
    ).fillna(False)

    outlier_cells = 0
    stuck_cells = 0
    step_events: dict[str, list] = {}
    for column in NUMERIC_FIELDS:
        if column not in work.columns or work[column].notna().sum() < 3:
            continue

        # 이상치·고착 판정은 **운전 중 구간에만** 적용한다.
        # 정지 구간의 0(또는 일정값)은 정상이며, 이를 지우면 기동/정지 전환점 자체가
        # 사라져 segmentation 이 STARTUP/SHUTDOWN 을 찾지 못한다.
        outliers = (
            detect_outliers_mad(
                work[column], work[TIMESTAMP], config["rolling_window_h"], config["mad_k"]
            )
            & online
        )
        outlier_cells += int(outliers.sum())
        work.loc[outliers, column] = np.nan

        # 고착 탐지는 운전 중 구간에만 적용한다. 정지 구간은 값이 일정한 것이 정상이며,
        # 이를 계측기 고착으로 오판하면 필수 항목이 통째로 NaN 이 되어 행이 사라진다.
        stuck = detect_stuck(work[column], config["stuck_points"]) & online
        stuck_cells += int(stuck.sum())
        work.loc[stuck, column] = np.nan

        if column in ("hrsg_gas_dp_kpa", "gt_backpressure_kpa", "stack_temp_c"):
            events = detect_step_changes(work[column], work[TIMESTAMP], config["step_change_sigma"])
            if events:
                step_events[column] = events

    stats["cells_outlier"] = outlier_cells
    stats["cells_stuck"] = stuck_cells

    if step_events:
        warnings.append(
            {
                "code": "STEP_CHANGE_SUSPECTED",
                "message": "계측값 급변이 감지되었습니다. 계측기 점검을 확인하세요.",
                "details": step_events,
            }
        )

    work, filled = fill_short_gaps(work, config["gap_fill_max_points"])
    stats["cells_interpolated"] = filled

    work = resample(work, config["sampling_interval_min"])
    stats["row_resampled"] = len(work)

    work, dropped_core = drop_rows_missing_core(work)
    stats["row_missing_core"] = dropped_core

    excluded = high_missing_columns(work, config["max_missing_rate_pct"])
    if excluded:
        warnings.append(
            {
                "code": "HIGH_MISSING_RATE",
                "message": "결측률이 높아 모델 피처에서 제외한 항목이 있습니다.",
                "details": {"columns": excluded},
            }
        )

    stats["row_output"] = len(work)
    return CleaningResult(frame=work, stats=stats, warnings=warnings, excluded_features=excluded)
