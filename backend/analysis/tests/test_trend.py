"""추세 예측 및 D-day 검증 (specs/08 §10). DB 불필요."""

import numpy as np
import pandas as pd
import pytest

from analysis.services import trend
from analysis.tests.factories import config

RNG = np.random.default_rng(0)


def daily(values, start="2024-01-01", counts=300, confidence="HIGH"):
    return pd.DataFrame(
        {
            "date": pd.date_range(start, periods=len(values), freq="D"),
            "fi_value": values,
            "sample_count": counts,
            "confidence": confidence,
        }
    )


def linear_series(slope, days, intercept=10.0, noise=1.0, seed=0):
    rng = np.random.default_rng(seed)
    return np.clip(intercept + slope * np.arange(days) + rng.normal(0, noise, days), 0, 100)


# --- AC-08-1 : D-day 정확도 ---


@pytest.mark.parametrize(("slope", "days"), [(0.20, 120), (0.10, 150), (0.35, 100)])
def test_ac_08_1_dday_within_five_days_of_theory(slope, days):
    """AC-08-1: 선형 증가 합성 FI 시계열에서 D-day 가 이론값과 ±5일 이내로 일치한다."""
    y = linear_series(slope, days)
    result = trend.forecast(daily(y), config(), current_fi=float(y[-5:].mean()))

    theory = (60 - 10) / slope - (days - 1)
    assert result.status == trend.STATUS_OK
    assert abs(result.eta_days - theory) <= 5


# --- AC-08-2 : 감소 추세 ---


def test_ac_08_2_decreasing_trend_reports_no_forecast():
    """AC-08-2: FI 가 감소 추세일 때 '도달 예측 불가'로 표시된다."""
    y = linear_series(-0.15, 120, intercept=60)
    result = trend.forecast(daily(y), config(), current_fi=float(y[-5:].mean()))

    assert result.status == trend.STATUS_NO_TREND
    assert result.eta_days is None
    assert result.slope_per_day < 0


def test_flat_series_is_not_significant():
    y = np.full(120, 25.0) + RNG.normal(0, 1.0, 120)
    result = trend.forecast(daily(y), config(), current_fi=25.0)

    assert result.status == trend.STATUS_NO_TREND


# --- AC-08-3 : 세정 이전 데이터 절단 ---


def test_ac_08_3_data_before_cleaning_is_excluded():
    """AC-08-3: 세정 이벤트 이전 데이터가 추세 적합에 포함되지 않는다."""
    y = np.concatenate([np.linspace(50, 80, 60), np.linspace(5, 25, 60)])
    frame = daily(y)
    cleaned_at = frame.date.iloc[59]

    without = trend.forecast(frame, config(), current_fi=25.0)
    with_cut = trend.forecast(frame, config(), current_fi=25.0, last_cleaning=cleaned_at)

    assert without.slope_per_day < 0  # 세정을 섞으면 기울기가 음수로 뒤집힌다
    assert with_cut.slope_per_day > 0
    assert with_cut.fit_start > cleaned_at
    assert any(w["code"] == "TREND_TRIMMED_AT_CLEANING" for w in with_cut.warnings)


def test_window_falls_back_to_trend_window_without_cleaning():
    y = linear_series(0.1, 400)
    frame = daily(y)

    result = trend.forecast(frame, config(trend_window_days=90), current_fi=float(y[-5:].mean()))

    assert (result.fit_end - result.fit_start).days <= 90


# --- AC-08-4 : 임계치 변경 ---


def test_ac_08_4_lower_threshold_shortens_dday():
    """AC-08-4: 임계치를 60에서 50으로 바꾸면 D-day 가 짧아진다."""
    y = linear_series(0.2, 120)
    frame, fi_now = daily(y), float(y[-5:].mean())

    high = trend.forecast(frame, config(fouling_threshold=60), fi_now)
    low = trend.forecast(frame, config(fouling_threshold=50), fi_now)

    assert low.eta_days < high.eta_days


# --- AC-08-5 : 데이터 부족 ---


def test_ac_08_5_insufficient_days_gives_guidance():
    """AC-08-5: 유효 일자 30일 미만이면 추세·D-day 대신 데이터 부족 안내가 표시된다."""
    result = trend.forecast(daily(np.linspace(10, 20, 20)), config(), current_fi=20.0)

    assert result.status == trend.STATUS_INSUFFICIENT_DATA
    assert result.eta_days is None
    assert "30일" in result.message


# --- 상태 분기 ---


def test_already_exceeded_reports_zero_and_days_over():
    y = np.clip(55 + 0.2 * np.arange(90), 0, 100)
    result = trend.forecast(daily(y), config(), current_fi=float(y[-5:].mean()))

    assert result.status == trend.STATUS_ALREADY_EXCEEDED
    assert result.eta_days == 0
    assert result.exceeded_days > 0


def test_beyond_horizon_is_reported():
    y = linear_series(0.005, 200, intercept=5, noise=0.2)
    result = trend.forecast(daily(y), config(max_forecast_days=30), current_fi=float(y[-5:].mean()))

    assert result.status == trend.STATUS_BEYOND_HORIZON


# --- 모델 선택 (specs/08 §4) ---


def test_exponential_is_selected_for_saturating_series():
    t = np.arange(150)
    y = 70 * (1 - np.exp(-t / 60)) + RNG.normal(0, 0.8, 150)

    result = trend.forecast(daily(y), config(), current_fi=float(y[-5:].mean()))

    assert result.model_type == trend.MODEL_EXPONENTIAL
    assert result.r2 > 0.9


def test_linear_is_preferred_for_linear_series():
    result = trend.forecast(daily(linear_series(0.2, 120)), config(), current_fi=34.0)

    assert result.model_type in (trend.MODEL_LINEAR, trend.MODEL_ROBUST)


def test_model_can_be_forced():
    frame = daily(linear_series(0.2, 120))

    result = trend.forecast(frame, config(trend_model=trend.MODEL_ROBUST), current_fi=34.0)

    assert result.model_type == trend.MODEL_ROBUST


def test_robust_resists_outliers():
    y = linear_series(0.2, 120, noise=0.3)
    y[50:55] = 95.0  # 이상점 주입
    frame = daily(y)

    linear = trend.forecast(frame, config(trend_model=trend.MODEL_LINEAR), 34.0)
    robust = trend.forecast(frame, config(trend_model=trend.MODEL_ROBUST), 34.0)

    assert abs(robust.slope_per_day - 0.2) < abs(linear.slope_per_day - 0.2)


def test_choose_prefers_simpler_model_on_tie():
    def fit(model_type, mae):
        return trend.TrendFit(
            model_type=model_type,
            predict=lambda t: np.zeros_like(np.asarray(t, dtype=float)),
            coefficients={"intercept": 0.0, "slope": 0.0},
            slope_per_day=0.0,
            r2=0.9,
            mae=mae,
            validation_mae=mae,
            p_value=0.01,
            residual_std=1.0,
        )

    chosen = trend.choose([fit(trend.MODEL_EXPONENTIAL, 1.0), fit(trend.MODEL_LINEAR, 1.0)])

    assert chosen.model_type == trend.MODEL_LINEAR


def test_choose_returns_none_without_candidates():
    assert trend.choose([]) is None


# --- 부가 지표 (specs/08 §6) ---


def test_weekly_increase_and_grade_etas_are_reported():
    y = linear_series(0.2, 120)
    result = trend.forecast(daily(y), config(), current_fi=float(y[-5:].mean()))

    assert result.weekly_increase == pytest.approx(result.slope_per_day * 7)
    assert result.caution_eta_date is not None or result.current_fi >= 30
    assert result.warning_eta_date is not None


def test_days_since_cleaning_is_tracked():
    y = linear_series(0.2, 120)
    frame = daily(y)

    result = trend.forecast(frame, config(), 34.0, last_cleaning=frame.date.iloc[10])

    assert result.days_since_cleaning == 109


# --- 신뢰구간 (specs/08 §5) ---


def test_confidence_interval_brackets_the_estimate():
    y = linear_series(0.2, 120, noise=2.0)
    result = trend.forecast(daily(y), config(), current_fi=float(y[-5:].mean()))

    assert result.eta_lower_date <= result.eta_date <= result.eta_upper_date


def test_wide_interval_is_flagged_uncertain():
    y = linear_series(0.05, 120, noise=8.0, seed=3)
    result = trend.forecast(daily(y), config(), current_fi=float(y[-5:].mean()))

    if result.status == trend.STATUS_OK and result.eta_lower_date and result.eta_upper_date:
        span = (result.eta_upper_date - result.eta_lower_date).days
        assert result.uncertain == (span > max(result.eta_days, 1) * 2)


# --- 가중치 ---


def test_low_confidence_days_carry_less_weight():
    y = linear_series(0.2, 120, noise=0.2)
    frame = daily(y)
    frame.loc[:20, "fi_value"] = 90.0  # 잘못된 앞부분
    frame.loc[:20, "confidence"] = "LOW"
    frame.loc[:20, "sample_count"] = 5

    weighted = trend.forecast(frame, config(trend_model=trend.MODEL_LINEAR), 34.0)
    frame.loc[:20, "confidence"] = "HIGH"
    frame.loc[:20, "sample_count"] = 300
    unweighted = trend.forecast(frame, config(trend_model=trend.MODEL_LINEAR), 34.0)

    assert weighted.slope_per_day > unweighted.slope_per_day


def test_empty_frame_is_insufficient():
    empty = pd.DataFrame(columns=["date", "fi_value", "sample_count", "confidence"])

    assert trend.forecast(empty, config(), None).status == trend.STATUS_INSUFFICIENT_DATA
