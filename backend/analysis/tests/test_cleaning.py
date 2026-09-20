"""정제 검증 (specs/04 §4~6). DB 불필요."""

import numpy as np
import pandas as pd
import pytest

from analysis.services import cleaning
from analysis.tests.factories import config, steady_frame
from units.standard_fields import DEFAULT_PHYSICAL_RANGES, resolve_ranges

RANGES = resolve_ranges(DEFAULT_PHYSICAL_RANGES, 160.0)


def run(frame, **overrides):
    return cleaning.clean(frame, config(**overrides), RANGES)


def test_original_frame_is_never_mutated():
    """AC-04-5: 원본 Measurement 는 정제 과정에서 수정·삭제되지 않는다."""
    frame = steady_frame(days=3)
    before = frame.copy(deep=True)

    run(frame)

    pd.testing.assert_frame_equal(frame, before)


def test_clean_data_survives_intact():
    frame = steady_frame(days=5)

    result = run(frame)

    assert result.stats["row_output"] == pytest.approx(len(frame), rel=0.02)
    assert result.stats["cells_stuck"] == 0


def test_duplicate_timestamps_are_removed_keeping_last():
    frame = steady_frame(days=1)
    duplicated = pd.concat([frame, frame.iloc[:5]], ignore_index=True)

    out = cleaning.sort_and_dedupe(duplicated)

    assert len(out) == len(frame)
    assert out.timestamp.is_monotonic_increasing


def test_out_of_range_values_become_nan():
    frame = steady_frame(days=2)
    frame.loc[10, "stack_temp_c"] = 9999.0

    out, removed = cleaning.apply_physical_ranges(frame, RANGES)

    assert removed == 1
    assert pd.isna(out.loc[10, "stack_temp_c"])


def test_short_gaps_are_interpolated():
    frame = steady_frame(days=2)
    frame.loc[20:22, "stack_temp_c"] = np.nan

    out, filled = cleaning.fill_short_gaps(frame, max_points=3)

    assert filled == 3
    assert out.stack_temp_c.iloc[20:23].notna().all()


def test_long_gaps_are_left_missing():
    frame = steady_frame(days=2)
    frame.loc[20:40, "stack_temp_c"] = np.nan

    out, _ = cleaning.fill_short_gaps(frame, max_points=3)

    assert out.stack_temp_c.iloc[20:41].isna().any()


# --- AC-04-3 : 오염 신호 보존 ---


def test_ac_04_3_slow_fouling_rise_is_not_removed():
    """AC-04-3: 오염에 의한 완만한 차압 상승이 이상치로 제거되지 않는다."""
    n = 6 * 24 * 120  # 120일
    timestamps = pd.Series(pd.date_range("2024-01-01", periods=n, freq="10min"))
    rising = pd.Series(3.0 + np.arange(n) * 0.0004 + np.random.default_rng(0).normal(0, 0.02, n))

    flagged = cleaning.detect_outliers_mad(rising, timestamps, window_h=3, k=5.0)

    assert flagged.mean() < 0.01  # 1% 미만


def test_short_spike_is_removed():
    n = 2000
    timestamps = pd.Series(pd.date_range("2024-01-01", periods=n, freq="10min"))
    series = pd.Series(np.full(n, 3.0) + np.random.default_rng(0).normal(0, 0.02, n))
    series.iloc[1000] = 30.0

    flagged = cleaning.detect_outliers_mad(series, timestamps, window_h=3, k=5.0)

    assert bool(flagged.iloc[1000]) is True


def test_constant_series_is_not_all_flagged():
    """MAD 가 0 인 구간에서 전부 이상치가 되면 안 된다."""
    n = 500
    timestamps = pd.Series(pd.date_range("2024-01-01", periods=n, freq="10min"))
    series = pd.Series(np.full(n, 3.0))

    assert cleaning.detect_outliers_mad(series, timestamps, 3, 5.0).sum() == 0


# --- 고착 ---


def test_stuck_values_are_detected():
    series = pd.Series([1.0] * 10 + [2.5] * 40 + [3.0] * 10)

    flagged = cleaning.detect_stuck(series, min_points=30)

    assert flagged.iloc[10:50].all()
    assert not flagged.iloc[:10].any()


def test_short_constant_run_is_not_stuck():
    series = pd.Series([1.0] * 10 + [2.5] * 5 + [3.0] * 10)

    assert cleaning.detect_stuck(series, min_points=30).sum() == 0


def test_stuck_detection_is_limited_to_online_rows():
    """정지 구간의 일정값을 고착으로 오판하면 안 된다."""
    frame = steady_frame(days=3)
    frame.loc[:200, "gt_power_mw"] = 0.0  # 정지
    frame.loc[:200, "exhaust_flow"] = 0.0

    result = run(frame)

    # 정지 구간이 살아남아 구간 분류가 STARTUP/OFFLINE 을 볼 수 있어야 한다.
    assert result.stats["row_output"] > len(frame) * 0.9


# --- 단차 ---


def test_step_change_is_reported_as_warning_not_removed():
    """specs/04 §5.4 — 단차는 제외하지 않고 경고만 한다."""
    n = 3000
    timestamps = pd.Series(pd.date_range("2024-01-01", periods=n, freq="10min"))
    series = pd.Series(np.concatenate([np.full(n // 2, 3.0), np.full(n - n // 2, 5.0)]))

    events = cleaning.detect_step_changes(series, timestamps, sigma_multiple=1.0)

    assert events
    assert "at" in events[0]


def test_no_step_change_in_smooth_series():
    n = 2000
    timestamps = pd.Series(pd.date_range("2024-01-01", periods=n, freq="10min"))
    series = pd.Series(np.full(n, 3.0) + np.random.default_rng(0).normal(0, 0.01, n))

    assert cleaning.detect_step_changes(series, timestamps, sigma_multiple=5.0) == []


# --- 리샘플링 ---


def test_resample_uses_max_for_duct_burner():
    """specs/04 §6 — 한 번이라도 ON 이면 ON."""
    frame = steady_frame(days=1, interval_min=5)
    frame.loc[0, "duct_burner_on"] = True

    out = cleaning.resample(frame, interval_min=10)

    assert bool(out.duct_burner_on.iloc[0]) is True


def test_resample_averages_numeric_columns():
    frame = steady_frame(days=1, interval_min=5)

    out = cleaning.resample(frame, interval_min=10)

    assert len(out) == pytest.approx(len(frame) / 2, rel=0.05)


# --- 필수 항목 결측 ---


def test_rows_missing_core_fields_are_dropped():
    frame = steady_frame(days=2)
    frame.loc[5:9, "stack_temp_c"] = np.nan

    out, dropped = cleaning.drop_rows_missing_core(frame)

    assert dropped == 5
    assert len(out) == len(frame) - 5


def test_row_survives_when_only_backpressure_present():
    frame = steady_frame(days=2)
    frame["hrsg_gas_dp_kpa"] = np.nan  # 차압 미계측 호기

    _, dropped = cleaning.drop_rows_missing_core(frame)

    assert dropped == 0


def test_high_missing_columns_are_excluded_from_features():
    frame = steady_frame(days=2)
    frame.loc[: len(frame) // 2, "humidity_pct"] = np.nan

    result = run(frame)

    assert "humidity_pct" in result.excluded_features
    assert any(w["code"] == "HIGH_MISSING_RATE" for w in result.warnings)


def test_empty_frame_is_handled():
    result = run(pd.DataFrame(columns=["timestamp", "gt_power_mw"]))

    assert result.stats["row_output"] == 0
