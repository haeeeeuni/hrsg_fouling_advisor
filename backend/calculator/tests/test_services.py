"""계산 순수 함수 — 성질 기반 검증 (specs/05 AC-05-1·3·4·6, AGENTS.md §8). DB 불필요."""

import pytest

from calculator.services.loss import (
    NOTICE_ST_FALLBACK,
    compare_methods,
    compute_loss,
    evaluate_method,
    operating_status,
)
from calculator.services.pinch import PinchInputError, check_stage, check_stages
from calculator.services.steam import saturation_temperature_c_from_barg, saturation_temperature_k
from calculator.services.types import GtSpec, LossInputs, MethodSpec, PinchStageInput
from reference.param_defs import default_params

PARAMS = default_params()
GT = GtSpec(
    rated_gt_mw=270,
    rated_st_mw=135,
    backpressure_alarm_kpa=4.5,
    backpressure_trip_kpa=5.5,
    exhaust_temp_alarm_c=640,
    exhaust_temp_trip_c=660,
)
DRY_ICE = MethodSpec(
    id=1, name="드라이아이스", cleaning_cost_won=3e7, outage_days=2, recovery_ratio=0.85
)


def inputs(**overrides) -> LossInputs:
    base = dict(
        gt_power_mw=270,
        backpressure_kpa=4.0,
        clean_backpressure_kpa=3.0,
        exhaust_temp_c=610,
        stack_temp_c=100,
        clean_stack_temp_c=95,
        operating_hours_per_day=20,
        smp_won_per_kwh=150,
    )
    base.update(overrides)
    return LossInputs(**base)


# --- 포화온도 (AC-05-4) ---


@pytest.mark.parametrize(
    ("mpa", "kelvin"), [(0.1, 372.755919), (1.0, 453.035632), (10.0, 584.149488)]
)
def test_saturation_temperature_matches_if97_verification_values(mpa, kelvin):
    assert saturation_temperature_k(mpa) == pytest.approx(kelvin, abs=1e-6)


def test_gauge_pressure_adds_atmosphere():
    # 0 barg = 1.01325 bar(a) → 물의 표준 끓는점
    assert saturation_temperature_c_from_barg(0) == pytest.approx(100.0, abs=0.05)


@pytest.mark.parametrize("mpa", [0.0001, 23.0])
def test_saturation_temperature_rejects_out_of_range(mpa):
    with pytest.raises(ValueError):
        saturation_temperature_k(mpa)


def test_saturation_temperature_increases_with_pressure():
    temps = [saturation_temperature_c_from_barg(p) for p in range(0, 180, 10)]
    assert temps == sorted(temps)


# --- 손실 ---


def test_same_input_same_result_100_times():
    """AC-05-1 — 결정론."""
    results = {compute_loss(inputs(), GT, PARAMS) for _ in range(100)}
    assert len(results) == 1


def test_no_degradation_means_no_loss():
    result = compute_loss(inputs(backpressure_kpa=3.0, stack_temp_c=95), GT, PARAMS)

    assert result.power_loss_total_mw == 0
    assert result.daily_loss_won == 0


def test_negative_delta_is_not_a_gain():
    """AC-05-6 — 청정값보다 좋아도 손실은 0 이지 음수가 아니다."""
    result = compute_loss(inputs(backpressure_kpa=2.0, stack_temp_c=80), GT, PARAMS)

    assert result.delta_backpressure_kpa == 0
    assert result.delta_stack_temp_c == 0
    assert result.daily_loss_won == 0


def test_loss_increases_monotonically_with_backpressure():
    losses = [
        compute_loss(inputs(backpressure_kpa=3.0 + 0.2 * step), GT, PARAMS).daily_loss_won
        for step in range(10)
    ]
    assert losses == sorted(losses)
    assert losses[-1] > losses[0]


def test_loss_increases_monotonically_with_stack_temperature():
    losses = [
        compute_loss(inputs(stack_temp_c=95 + step), GT, PARAMS).daily_loss_won
        for step in range(10)
    ]
    assert losses == sorted(losses)


def test_part_load_reduces_loss_proportionally():
    full = compute_loss(inputs(gt_power_mw=270), GT, PARAMS).power_loss_total_mw
    half = compute_loss(inputs(gt_power_mw=135), GT, PARAMS).power_loss_total_mw

    assert half == pytest.approx(full / 2)


def test_missing_st_rating_falls_back_with_notice():
    gt = GtSpec(**{**GT.__dict__, "rated_st_mw": None})

    result = compute_loss(inputs(), gt, PARAMS)

    assert NOTICE_ST_FALLBACK in result.notices
    assert result.power_loss_st_mw == pytest.approx(
        compute_loss(inputs(), GT, PARAMS).power_loss_st_mw
    )  # 270 × 0.5 = 135 이라 등록된 값과 같다


# --- 공법 ---


def test_no_loss_means_payback_impossible():
    """AC-05-6 — 회수 효과가 0 이면 회수 기간은 None(화면은 '회수 불가')."""
    result = evaluate_method(0, 150, GT, DRY_ICE, PARAMS)

    assert result.recovered_daily_won == 0
    assert result.payback_days is None


def test_recovery_scales_with_recovery_ratio():
    ratios = [0.2, 0.5, 0.9]
    recovered = [
        evaluate_method(1e6, 150, GT, MethodSpec(1, "x", 0, 0, r), PARAMS).recovered_daily_won
        for r in ratios
    ]
    assert recovered == sorted(recovered)


def test_outage_loss_is_margin_based():
    """정지 중에는 연료를 쓰지 않으므로 매출 전액이 아니라 마진만 손실이다."""
    result = evaluate_method(0, 100, GT, DRY_ICE, PARAMS)
    revenue = (270 + 135) * 24 * PARAMS["capacity_factor"] * 2 * 1000 * 100

    assert result.outage_loss_won == pytest.approx(revenue * (1 - PARAMS["fuel_cost_ratio"]))


def test_compare_methods_orders_by_net_benefit_then_name():
    cheap = MethodSpec(2, "나", 0, 0, 0.5)
    same = MethodSpec(3, "가", 0, 0, 0.5)
    pricey = MethodSpec(4, "다", 1e12, 10, 0.5)

    rows = compare_methods(1e6, 150, GT, [pricey, cheap, same], PARAMS)

    assert [r.name for r in rows] == ["가", "나", "다"]


# --- 운전 상태 (AC-05-3) ---


@pytest.mark.parametrize(
    ("backpressure", "state", "level"),
    [
        (4.49, "NORMAL", "NORMAL"),
        (4.5, "ALARM", "CAUTION"),
        (5.49, "ALARM", "CAUTION"),
        (5.5, "TRIP", "DANGER"),
    ],
)
def test_backpressure_state_boundaries(backpressure, state, level):
    status = operating_status(inputs(backpressure_kpa=backpressure), GT)

    assert status["variables"][0]["state"] == state
    assert status["state"] == state
    assert status["level"] == level


def test_overall_state_follows_worst_variable():
    status = operating_status(inputs(backpressure_kpa=4.6, exhaust_temp_c=665), GT)

    assert status["state"] == "TRIP"
    assert status["level"] == "DANGER"


# --- 핀치·어프로치 ---


def stage(**overrides) -> PinchStageInput:
    base = dict(
        label="HP",
        drum_pressure_barg=120,
        evaporator_outlet_gas_temp_c=335,
        economizer_outlet_water_temp_c=318,
    )
    base.update(overrides)
    return PinchStageInput(**base)


def test_pinch_and_approach_definitions():
    result = check_stage(stage(), PARAMS)
    t_sat = saturation_temperature_c_from_barg(120)

    assert result["pinch_c"] == pytest.approx(335 - t_sat, abs=0.01)
    assert result["approach_c"] == pytest.approx(t_sat - 318, abs=0.01)


def test_large_pinch_is_caution():
    result = check_stage(stage(evaporator_outlet_gas_temp_c=360), PARAMS)

    assert result["pinch_level"] == "CAUTION"
    assert result["notes"]


def test_negative_approach_is_danger_steaming():
    result = check_stage(stage(economizer_outlet_water_temp_c=330), PARAMS)

    assert result["approach_level"] == "DANGER"
    assert result["level"] == "DANGER"


def test_design_values_take_precedence_over_range():
    # 핀치 9.7 ℃ 는 기본 범위(5~15) 안이지만 설계 핀치 5 + 여유 3 을 넘는다.
    result = check_stage(stage(design_pinch_c=5), PARAMS)

    assert result["pinch_level"] == "CAUTION"


def test_gas_colder_than_saturation_is_input_error():
    with pytest.raises(PinchInputError):
        check_stage(stage(evaporator_outlet_gas_temp_c=300), PARAMS)


def test_overall_level_is_worst_stage():
    result = check_stages([stage(), stage(label="LP", economizer_outlet_water_temp_c=330)], PARAMS)

    assert result["level"] == "DANGER"
