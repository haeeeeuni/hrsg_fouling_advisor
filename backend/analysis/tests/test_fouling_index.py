"""오염도 지수 성질 기반 검증 (specs/07 §8, AGENTS.md §8). DB 불필요."""

import numpy as np
import pandas as pd
import pytest

from analysis.services import fouling_index as fx
from analysis.tests.factories import config

STATS = {"dp": {"mean": 0.0, "std": 0.05}, "st": {"mean": 0.0, "std": 1.0}}


def residual_frame(n=2000, residual_dp=0.0, residual_st=0.0, start="2024-01-01"):
    index = pd.date_range(start, periods=n, freq="10min")
    dp = np.full(n, residual_dp) if np.isscalar(residual_dp) else np.asarray(residual_dp)
    st = np.full(n, residual_st) if np.isscalar(residual_st) else np.asarray(residual_st)
    return pd.DataFrame(
        {
            "timestamp": index,
            "cluster_key": "L3-WI",
            "is_sparse": False,
            "residual_dp": dp,
            "residual_st": st,
            "expected_dp": 2.5,
            "expected_st": 110.0,
            "measured_dp": 2.5 + dp,
            "measured_st": 110.0 + st,
        }
    )


def overall(result):
    return result.points[result.points.cluster_key.isna()].dropna(subset=["fi_value"])


# --- AC-07-1 : 오염 없음 → FI ≈ 0 ---


def test_ac_07_1_no_fouling_gives_fi_near_zero():
    result = fx.compute(residual_frame(residual_dp=0.0, residual_st=0.0), config(), STATS)

    assert result.current_fi == pytest.approx(0.0, abs=1e-6)
    assert overall(result).fi_value.max() <= 10


def test_negative_residual_is_not_fouling():
    """기대보다 낮은 값은 오염이 아니므로 0 으로 클리핑한다 (specs/07 §3.3)."""
    result = fx.compute(residual_frame(residual_dp=-0.5, residual_st=-8.0), config(), STATS)

    assert result.current_fi == pytest.approx(0.0, abs=1e-9)


# --- AC-07-2 : 잔차 선형 증가 → FI 단조 증가 ---


def test_ac_07_2_linear_residual_growth_makes_fi_monotonic():
    n = 4000
    result = fx.compute(
        residual_frame(
            n=n,
            residual_dp=np.linspace(0, 0.25, n),
            residual_st=np.linspace(0, 5.0, n),
        ),
        config(),
        STATS,
    )

    daily = overall(result).sort_values("date").fi_value.to_numpy()
    assert len(daily) > 5
    # 평활·일별 집계 후에도 단조 증가여야 한다.
    assert np.all(np.diff(daily) >= -1e-6)
    assert daily[-1] > daily[0]


# --- AC-07-3 : 세정 직후 FI 급락 ---


def test_ac_07_3_fi_drops_sharply_after_cleaning():
    n = 6000
    half = n // 2
    residual_dp = np.concatenate([np.linspace(0, 0.25, half), np.zeros(n - half)])
    residual_st = np.concatenate([np.linspace(0, 5.0, half), np.zeros(n - half)])

    result = fx.compute(
        residual_frame(n=n, residual_dp=residual_dp, residual_st=residual_st), config(), STATS
    )
    daily = overall(result).sort_values("date")

    peak = daily.fi_value.max()
    tail = daily.fi_value.iloc[-3:].median()
    assert peak > 40
    assert tail < peak * 0.2


# --- AC-07-4 : 0~100 클리핑 ---


def test_ac_07_4_fi_never_leaves_zero_hundred():
    result = fx.compute(residual_frame(residual_dp=99.0, residual_st=999.0), config(), STATS)
    daily = overall(result)

    assert daily.fi_value.max() <= 100
    assert daily.fi_value.min() >= 0
    assert result.current_fi == pytest.approx(100.0)


# --- AC-07-5 : 가중치 변경이 결과에 반영 ---


def test_ac_07_5_changing_weight_dp_changes_fi():
    frame = residual_frame(residual_dp=0.15, residual_st=0.0)  # 차압만 오염

    low = fx.compute(frame, config(weight_dp=0.2, weight_stack_temp=0.8), STATS).current_fi
    high = fx.compute(frame, config(weight_dp=0.8, weight_stack_temp=0.2), STATS).current_fi

    assert high > low


# --- AC-07-6 : 등급 경계 변경 즉시 반영 ---


def test_ac_07_6_grade_boundaries_are_configurable():
    frame = residual_frame(residual_dp=0.10, residual_st=2.0)

    default = fx.compute(frame, config(), STATS)
    tightened = fx.compute(frame, config(grade_caution_min=25, grade_warning_min=55), STATS)

    assert default.current_fi == tightened.current_fi
    assert fx.grade_of(default.current_fi, 30, 60) == default.grade
    assert fx.grade_of(default.current_fi, 25, 55) == tightened.grade


@pytest.mark.parametrize(
    ("fi", "expected"),
    [
        (0, "NORMAL"),
        (29.9, "NORMAL"),
        (30, "CAUTION"),
        (59.9, "CAUTION"),
        (60, "WARNING"),
        (100, "WARNING"),
    ],
)
def test_grade_boundaries(fi, expected):
    assert fx.grade_of(fi, 30, 60) == expected


def test_grade_of_none():
    assert fx.grade_of(None, 30, 60) is None
    assert fx.grade_of(float("nan"), 30, 60) is None


# --- 정규화 ---


def test_sigma_normalization_reaches_100_at_sigma_ref():
    scores = fx.normalize_sigma(pd.Series([6.0]), mu=0.0, sigma=1.0, sigma_ref=6.0)

    assert scores.iloc[0] == pytest.approx(100.0)


def test_sigma_normalization_is_half_at_half_sigma_ref():
    scores = fx.normalize_sigma(pd.Series([3.0]), mu=0.0, sigma=1.0, sigma_ref=6.0)

    assert scores.iloc[0] == pytest.approx(50.0)


def test_sigma_floor_prevents_division_blowup():
    """σ≈0 이어도 폭주하지 않아야 한다 (specs/07 §7)."""
    scores = fx.normalize_sigma(pd.Series([0.1]), mu=0.0, sigma=0.0, sigma_ref=6.0)

    assert 0 <= scores.iloc[0] <= 100


def test_relative_normalization_uses_percent_for_dp():
    scores = fx.normalize_relative_pct(pd.Series([3.25]), pd.Series([2.5]), ref_pct=30)

    assert scores.iloc[0] == pytest.approx(100.0)


def test_relative_normalization_uses_absolute_for_stack():
    scores = fx.normalize_relative_abs(pd.Series([125.0]), pd.Series([110.0]), ref_value=15)

    assert scores.iloc[0] == pytest.approx(100.0)


def test_relative_method_is_selectable():
    frame = residual_frame(residual_dp=0.75, residual_st=15.0)

    result = fx.compute(frame, config(normalization_method="RELATIVE"), STATS)

    assert result.current_fi == pytest.approx(100.0, abs=1.0)


# --- 가중 합산 ---


def test_single_signal_renormalizes_weight():
    score_dp = pd.Series([80.0, 80.0])
    score_st = pd.Series([np.nan, 20.0])

    fi, single = fx.weighted_fi(score_dp, score_st, 0.6, 0.4)

    assert fi.iloc[0] == pytest.approx(80.0)  # 차압 단독 → 가중치 1 로 재정규화
    assert fi.iloc[1] == pytest.approx(0.6 * 80 + 0.4 * 20)
    assert bool(single.iloc[0]) is True
    assert bool(single.iloc[1]) is False


def test_weights_are_normalized_when_sum_is_not_one():
    frame = residual_frame(residual_dp=0.10, residual_st=2.0)

    result = fx.compute(frame, config(weight_dp=6, weight_stack_temp=4), STATS)

    assert any(w["code"] == "WEIGHTS_NORMALIZED" for w in result.warnings)
    assert 0 <= result.current_fi <= 100


def test_zero_weights_are_rejected():
    with pytest.raises(ValueError):
        fx.weighted_fi(pd.Series([1.0]), pd.Series([1.0]), 0.0, 0.0)


# --- 집계 / 현재 지수 ---


def test_cluster_points_and_overall_are_both_emitted():
    frame = residual_frame(residual_dp=0.1, residual_st=2.0)
    frame.loc[frame.index[:1000], "cluster_key"] = "L2-WI"

    result = fx.compute(frame, config(), STATS)

    assert result.points.cluster_key.isna().any()  # 전체 집계
    assert set(result.points.cluster_key.dropna()) == {"L2-WI", "L3-WI"}


def test_overall_is_sample_weighted_across_clusters():
    """전체 FI 는 군집별 FI 의 **표본 수 가중** 평균이다 (specs/07 §3.6).

    평활은 시간 축 전체에 걸리므로, 집계 성질만 떼어 함수를 직접 검증한다.
    """
    per_cluster = pd.DataFrame(
        {
            "date": [pd.Timestamp("2024-01-01")] * 2,
            "cluster_key": ["L1-WI", "L3-WI"],
            "fi_value": [90.0, 10.0],
            "score_dp": [90.0, 10.0],
            "score_st": [90.0, 10.0],
            "residual_dp": [0.5, 0.0],
            "residual_st": [8.0, 0.0],
            "expected_dp": [2.5, 2.5],
            "expected_st": [110.0, 110.0],
            "measured_dp": [3.0, 2.5],
            "measured_st": [118.0, 110.0],
            "sample_count": [100, 900],  # 소수 군집이 크게 오염된 상황
        }
    )

    overall_row = fx._weighted_overall(per_cluster).iloc[0]

    # 단순 평균이면 50, 표본 가중이면 (90*100 + 10*900)/1000 = 18
    assert overall_row["fi_value"] == pytest.approx(18.0)
    assert overall_row["sample_count"] == 1000
    assert overall_row["cluster_key"] is None


def test_overall_ignores_nan_clusters_in_weighting():
    per_cluster = pd.DataFrame(
        {
            "date": [pd.Timestamp("2024-01-01")] * 2,
            "cluster_key": ["L1-WI", "L3-WI"],
            "fi_value": [40.0, np.nan],
            "score_dp": [40.0, np.nan],
            "score_st": [40.0, np.nan],
            "residual_dp": [0.2, np.nan],
            "residual_st": [3.0, np.nan],
            "expected_dp": [2.5, 2.5],
            "expected_st": [110.0, 110.0],
            "measured_dp": [2.7, 2.5],
            "measured_st": [113.0, 110.0],
            "sample_count": [100, 900],
        }
    )

    overall_row = fx._weighted_overall(per_cluster).iloc[0]

    assert overall_row["fi_value"] == pytest.approx(40.0)


def test_sparse_clusters_can_be_dropped():
    frame = residual_frame(n=1000)
    frame["is_sparse"] = True

    result = fx.compute(frame, config(drop_sparse_clusters=True), STATS)

    assert result.points.empty
    assert result.current_fi is None


def test_current_value_uses_recent_window_median():
    n = 3000
    residual = np.concatenate([np.zeros(n - 500), np.full(500, 0.3)])
    result = fx.compute(
        residual_frame(n=n, residual_dp=residual), config(current_window_days=3), STATS
    )

    assert result.current_fi > 0


def test_empty_frame_is_handled():
    result = fx.compute(pd.DataFrame(), config(), STATS)

    assert result.current_fi is None
    assert result.grade is None


# --- 신뢰도 (specs/07 §5) ---


@pytest.mark.parametrize(
    ("grades", "points", "ood", "expected"),
    [
        (["GOOD", "GOOD"], 1000, 0.0, "HIGH"),
        (["GOOD", "FAIR"], 1000, 0.0, "MEDIUM"),
        (["GOOD", "POOR"], 1000, 0.0, "LOW"),
        (["GOOD", "GOOD"], 10, 0.0, "LOW"),
        (["GOOD", "GOOD"], 1000, 0.5, "LOW"),
    ],
)
def test_confidence_rules(grades, points, ood, expected):
    assert fx.confidence_of(grades, points, 500, ood) == expected


# --- 경고 ---


def test_saturated_fi_triggers_warning():
    result = fx.compute(residual_frame(residual_dp=99.0, residual_st=999.0), config(), STATS)

    assert any(w["code"] == "FI_SATURATED" for w in result.warnings)


# --- 평활 ---


def test_smoothing_removes_spikes_but_keeps_level():
    n = 500
    values = pd.Series(np.full(n, 1.0))
    values.iloc[250] = 100.0
    timestamps = pd.Series(pd.date_range("2024-01-01", periods=n, freq="10min"))

    smoothed = fx.smooth(values, timestamps, 24)

    assert smoothed.iloc[250] == pytest.approx(1.0)
