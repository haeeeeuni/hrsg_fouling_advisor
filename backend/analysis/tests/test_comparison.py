"""세정 전후 비교 (specs/12 §7). DB 불필요."""

import numpy as np
import pandas as pd
import pytest

from analysis.services import comparison as cp

CLEANED_AT = pd.Timestamp("2024-03-01")


def build_frame(before_residual=1.0, after_residual=0.05, clusters=("L3-SP",), n_per_side=600):
    """세정 전후 각각 n_per_side 포인트. 잔차만 다르게 준다."""
    rows = []
    for cluster in clusters:
        for offset, residual in ((-25, before_residual), (5, after_residual)):
            start = CLEANED_AT + pd.Timedelta(days=offset)
            index = pd.date_range(start, periods=n_per_side, freq="20min")
            rows.append(
                pd.DataFrame(
                    {
                        "timestamp": index,
                        "cluster_key": cluster,
                        "residual_dp": residual,
                        "residual_st": residual * 8,
                        "measured_dp": 2.5 + residual,
                        "expected_dp": 2.5,
                        "measured_st": 110 + residual * 8,
                        "expected_st": 110.0,
                        "gt_power_mw": 140.0,
                        "fi": min(100.0, residual * 60),
                    }
                )
            )
    return pd.concat(rows, ignore_index=True)


def run(frame, **kwargs):
    windows = cp.build_windows(CLEANED_AT, None, **kwargs)
    return cp.compare(frame, windows, min_cluster_points=100)


def metric(result, key):
    return next(m for m in result.metrics["rows"] if m["key"] == key)


# --- 구간 산정 (specs/12 §2.2) ---


def test_windows_follow_spec_defaults():
    windows = cp.build_windows(CLEANED_AT, None)

    assert windows.before_end == CLEANED_AT
    assert (windows.before_end - windows.before_start).days == 30
    assert windows.after_start == CLEANED_AT + pd.Timedelta(days=1)
    assert (windows.after_end - windows.after_start).days == 30


def test_windows_use_cleaning_end_for_after_side():
    end_at = CLEANED_AT + pd.Timedelta(days=2)

    windows = cp.build_windows(CLEANED_AT, end_at)

    assert windows.after_start == end_at + pd.Timedelta(days=1)


# --- 비교 ---


def test_improvement_is_detected():
    result = run(build_frame())

    assert result.is_comparable
    assert metric(result, "residual_dp")["delta"] < 0
    assert metric(result, "residual_st")["delta"] < 0
    assert metric(result, "fi")["delta"] < 0


def test_residual_metrics_are_marked_primary():
    """잔차 기반 비교가 주 지표다 (specs/12 §2.3)."""
    result = run(build_frame())

    primary = {m["key"] for m in result.metrics["rows"] if m["is_primary"]}
    assert primary == {"residual_dp", "residual_st", "fi"}


def test_raw_averages_are_reported_as_reference():
    result = run(build_frame())

    assert metric(result, "dp")["before"] is not None
    assert metric(result, "stack")["delta_pct"] is not None


def test_recovery_ratio_is_computed():
    """회복률 = (FI_before − FI_after) / FI_before (specs/12 §2.5)."""
    result = run(build_frame(before_residual=1.0, after_residual=0.1))

    assert result.recovery_ratio == pytest.approx(0.9, abs=0.02)


# --- AC-12-5 : 공통 군집 ---


def test_ac_12_5_only_common_clusters_are_compared():
    """AC-12-5: 공통 군집이 아닌 구간은 비교에 사용되지 않는다."""
    before_only = build_frame(clusters=("L1-SP",))
    before_only = before_only[before_only.timestamp < CLEANED_AT]  # 전 구간만 존재
    frame = pd.concat([build_frame(clusters=("L3-SP",)), before_only], ignore_index=True)

    result = run(frame)

    assert result.common_clusters == ["L3-SP"]
    assert "L1-SP" not in result.common_clusters


def test_no_common_cluster_reports_guidance():
    result = cp.compare(
        build_frame(), cp.build_windows(CLEANED_AT, None), min_cluster_points=100000
    )

    assert not result.is_comparable
    assert result.warnings[0]["code"] == "NO_COMMON_CLUSTER"
    assert "윈도를 넓히" in result.warnings[0]["message"]


def test_sparse_side_is_excluded():
    frame = build_frame(clusters=("L3-SP",))
    thin = build_frame(clusters=("L2-SP",), n_per_side=20)

    result = run(pd.concat([frame, thin], ignore_index=True))

    assert result.common_clusters == ["L3-SP"]


def test_empty_window_is_reported():
    frame = build_frame()
    frame = frame[frame.timestamp < CLEANED_AT]  # 세정 후 데이터 없음

    result = run(frame)

    assert not result.is_comparable
    assert result.warnings[0]["code"] == "WINDOW_EMPTY"


# --- 군집별 / 유의성 ---


def test_cluster_metrics_cover_each_common_cluster():
    result = run(build_frame(clusters=("L2-SP", "L3-SP")))

    assert {row["cluster_key"] for row in result.cluster_metrics} == {"L2-SP", "L3-SP"}
    assert all(row["n_before"] > 0 and row["n_after"] > 0 for row in result.cluster_metrics)


def test_p_values_are_reported():
    """specs/12 §2.3 — t-검정 또는 Mann-Whitney U 로 유의성을 표기한다."""
    frame = build_frame()
    rng = np.random.default_rng(0)
    frame["residual_dp"] += rng.normal(0, 0.02, len(frame))

    result = run(frame)

    assert result.p_values["residual_dp"]["t_p_value"] < 0.05
    assert result.p_values["residual_dp"]["u_p_value"] < 0.05


def test_p_value_is_none_with_too_few_samples():
    tiny = pd.Series([1.0, 2.0])

    assert cp._test_difference(tiny, tiny)["t_p_value"] is None


def test_overall_is_sample_weighted():
    """군집별 지표를 표본 수로 가중 평균한다 (specs/12 §2.2 6단계)."""
    big = build_frame(clusters=("L3-SP",), before_residual=1.0, after_residual=0.1, n_per_side=900)
    small = build_frame(
        clusters=("L2-SP",), before_residual=0.2, after_residual=0.1, n_per_side=150
    )

    result = run(pd.concat([big, small], ignore_index=True))

    # 표본이 많은 L3-SP 쪽 값에 가깝게 나와야 한다.
    assert metric(result, "residual_dp")["before"] > 0.8
