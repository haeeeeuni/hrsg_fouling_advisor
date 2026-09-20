"""세정 편익 산출 검증 (specs/09 §10). DB 불필요."""

import pytest

from analysis.services import benefit as bf
from analysis.tests.factories import config

# specs/09 §6 예시의 손실 출력(GT 1.9 / ST 0.9 MW)을 역산한 Δ 값
DELTA_DP = 1.9 / (160 * 0.0035)
DELTA_ST = 0.9 / (80 * 0.0012)

BASE = dict(
    delta_dp=DELTA_DP,
    delta_stack=DELTA_ST,
    fi_now=62.4,
    slope_per_day=0.18,
    rated_gt_mw=160,
    rated_st_mw=80,
    eta_days=0,
)


def compute(params=None, **overrides):
    return bf.compute(params=params or config(), **{**BASE, **overrides})


# --- specs/09 §6 예시 재현 ---


def test_power_losses_match_spec_example():
    """§4.1 식과 §3.1 기본 계수로 명세 예시(2.8 MW = GT 1.9 + ST 0.9)가 재현된다."""
    result = compute()

    assert result.power_loss_gt_mw == pytest.approx(1.9, abs=0.01)
    assert result.power_loss_st_mw == pytest.approx(0.9, abs=0.01)
    assert result.power_loss_total_mw == pytest.approx(2.8, abs=0.02)


def test_daily_loss_cost_matches_spec_example():
    """§4.2 — 5,712,000 원/일."""
    assert compute().daily_loss_cost == pytest.approx(5_712_000, rel=1e-6)


# --- AC-09-1 : 전력 단가 비례 ---


def test_ac_09_1_doubling_price_doubles_daily_loss():
    """AC-09-1: 전력 단가를 2배로 하면 일일 손실 비용이 비례해 증가한다."""
    base = compute()
    doubled = compute(params=config(electricity_price=240))

    assert doubled.daily_loss_cost == pytest.approx(base.daily_loss_cost * 2)


def test_ac_09_1_doubling_price_increases_net_benefit_when_economic():
    """순편익도 함께 증가한다(세정이 경제적인 조건에서)."""
    online = config(outage_days=0)  # 운전 중 세정 → 정지 손실 없음
    base = compute(params=online)
    doubled = compute(params={**online, "electricity_price": 240})

    assert base.net_benefit > 0
    assert doubled.net_benefit > base.net_benefit


# --- AC-09-3 : 파라미터 스냅샷 ---


def test_ac_09_3_params_snapshot_is_stored():
    """AC-09-3: 편익 결과에 적용 파라미터 스냅샷이 함께 저장되어 재현 가능하다."""
    result = compute(params=config(electricity_price=135, cleaning_cost=28_000_000))

    assert result.params_snapshot["electricity_price"] == 135
    assert result.params_snapshot["cleaning_cost"] == 28_000_000


def test_same_inputs_reproduce_same_result():
    assert compute().net_benefit == compute().net_benefit


# --- AC-09-4 : 오염도 0 ---


def test_ac_09_4_zero_fouling_gives_negative_net_benefit():
    """AC-09-4: 오염도 0 상태에서 순편익이 음수(세정 비경제)로 계산된다."""
    result = compute(delta_dp=0.0, delta_stack=0.0, fi_now=0.0, slope_per_day=0.0)

    assert result.power_loss_total_mw == 0
    assert result.net_benefit < 0
    assert result.payback_days is None
    assert any(w["code"] == "NO_ECONOMIC_BENEFIT" for w in result.warnings)


def test_negative_delta_is_clipped_to_zero():
    """기대보다 낮은 값은 오염이 아니다 (specs/09 §4.1)."""
    result = compute(delta_dp=-1.0, delta_stack=-5.0)

    assert result.delta_dp_kpa == 0
    assert result.power_loss_total_mw == 0


# --- AC-09-5 : 3개 시나리오 ---


def test_ac_09_5_three_scenarios_are_compared():
    """AC-09-5: 3개 시나리오 비교표가 포함된다."""
    result = compute(params=config(outage_days=0), eta_days=167)

    keys = [row["scenario"] for row in result.scenarios]
    assert keys == [bf.SCENARIO_NOW, bf.SCENARIO_AT_THRESHOLD, bf.SCENARIO_PLANNED_OUTAGE]
    assert all(row["net_benefit"] is not None for row in result.scenarios)


def test_scenario_without_eta_is_marked_unavailable():
    result = compute(eta_days=None)

    row = next(r for r in result.scenarios if r["scenario"] == bf.SCENARIO_AT_THRESHOLD)
    assert row["net_benefit"] is None
    assert row["note"]


# --- 세정 비용 (specs/09 §4.4) ---


def test_online_cleaning_has_no_outage_loss():
    result = compute(params=config(outage_days=0))

    assert result.outage_loss == 0
    assert result.total_cleaning_cost == result.cleaning_cost


def test_outage_loss_scales_with_days():
    one = compute(params=config(outage_days=1)).outage_loss
    two = compute(params=config(outage_days=2)).outage_loss

    assert two == pytest.approx(one * 2)


# --- 회수 편익 (specs/09 §4.5) ---


def test_precise_and_simple_estimates_are_both_reported():
    result = compute(params=config(outage_days=0))

    assert result.gross_benefit > 0
    assert result.gross_benefit_simple > 0
    assert result.gross_benefit != result.gross_benefit_simple


def test_recovery_ratio_scales_benefit():
    full = compute(params=config(outage_days=0, cleaning_recovery_ratio=1.0))
    half = compute(params=config(outage_days=0, cleaning_recovery_ratio=0.5))

    assert full.gross_benefit > half.gross_benefit


def test_longer_horizon_increases_gross_benefit():
    short = compute(params=config(outage_days=0, evaluation_horizon_days=180))
    long = compute(params=config(outage_days=0, evaluation_horizon_days=365))

    assert long.gross_benefit > short.gross_benefit


def test_discount_rate_reduces_benefit():
    plain = compute(params=config(outage_days=0, discount_rate_annual=0.0))
    discounted = compute(params=config(outage_days=0, discount_rate_annual=0.1))

    assert discounted.gross_benefit < plain.gross_benefit


def test_residual_fouling_uses_fi_at_cleaning_time():
    """잔류 오염은 분석 시점이 아니라 **세정 시점**의 FI 기준이다.

    혼동하면 늦게 세정할수록 유리해 보이는 왜곡이 생긴다.
    """
    params = config(outage_days=0, cleaning_recovery_ratio=1.0)
    # 완전 회복이면 세정 직후 FI 는 0 이므로, 늦게 세정할수록 절약 구간이 짧아진다.
    now = bf.gross_benefit_precise(50.0, 0.1, 1_000_000, params, clean_offset_days=0)
    later = bf.gross_benefit_precise(50.0, 0.1, 1_000_000, params, clean_offset_days=200)

    assert now > later


def test_payback_and_roi():
    result = compute(params=config(outage_days=0))

    assert result.payback_days > 0
    assert result.roi_pct == pytest.approx(result.net_benefit / result.total_cleaning_cost * 100)


# --- 최적 시점 (specs/09 §4.6) ---


def test_recommended_offset_is_within_horizon():
    result = compute(params=config(outage_days=0))

    assert 0 <= result.recommended_offset_days < 365
    assert result.recommended_net_benefit is not None


def test_heavy_fouling_recommends_cleaning_sooner_than_light():
    heavy = compute(params=config(outage_days=0), fi_now=70.0, slope_per_day=0.25)
    light = compute(
        params=config(outage_days=0),
        delta_dp=0.3,
        delta_stack=1.5,
        fi_now=8.0,
        slope_per_day=0.05,
    )

    assert heavy.recommended_offset_days < light.recommended_offset_days


# --- 연료 손실 (specs/09 §4.3) ---


def test_fuel_loss_is_zero_without_fuel_data():
    result = compute()

    assert result.daily_fuel_loss == 0
    assert any(w["code"] == "FUEL_LOSS_NOT_INCLUDED" for w in result.warnings)


def test_fuel_loss_is_included_when_data_exists():
    result = compute(avg_fuel_flow=30_000)

    assert result.daily_fuel_loss > 0
    assert not any(w["code"] == "FUEL_LOSS_NOT_INCLUDED" for w in result.warnings)


# --- ST 정격 (specs/09 §8) ---


def test_missing_st_rating_falls_back_to_half_of_gt():
    result = compute(rated_st_mw=None)

    assert result.power_loss_st_mw == pytest.approx(160 * 0.5 * 0.0012 * DELTA_ST)
    assert any(w["code"] == "ST_RATING_ASSUMED" for w in result.warnings)


def test_measured_st_power_is_preferred_over_assumption():
    result = compute(rated_st_mw=None, avg_st_power_mw=75.0)

    assert result.power_loss_st_mw == pytest.approx(75.0 * 0.0012 * DELTA_ST)


# --- 민감도 (specs/09 §5) ---


def test_sensitivity_covers_four_params_sorted_by_swing():
    result = compute(params=config(outage_days=1))

    params = [row["param"] for row in result.sensitivity]
    assert set(params) == set(bf.SENSITIVITY_KEYS)
    swings = [row["swing"] for row in result.sensitivity]
    assert swings == sorted(swings, reverse=True)


def test_sensitivity_can_be_skipped():
    result = bf.compute(params=config(), with_sensitivity=False, **BASE)

    assert result.sensitivity == []
