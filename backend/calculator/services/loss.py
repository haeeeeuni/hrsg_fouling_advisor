"""손실·회수 효과 — 임시 계산식 `[임시값]` (specs/05 §6, formula_version = v0-placeholder).

이전 앱의 편익 모델(specs/archive/v1-fouling-advisor/09)을 입력 기반으로 바꾼 것이다.
실무진의 자체 산정 방식을 받으면 이 모듈을 통째로 교체하고 FORMULA_VERSION 을 올린다.

**이 모듈의 식과 계수는 서버 밖으로 나가지 않는다**(specs/05 CALC-8). 결과만 돌려준다.
순수 함수 — 난수·현재 시각을 쓰지 않는다(CALC-7).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from calculator.services.types import (
    STATE_ALARM,
    STATE_NORMAL,
    STATE_TO_LEVEL,
    STATE_TRIP,
    GtSpec,
    LossInputs,
    MethodSpec,
    worst,
)

FORMULA_VERSION = "v0-placeholder"

# ST 정격이 참조표에 없을 때의 가정(specs/05 §6). 결과에 안내를 붙인다.
ST_RATED_FALLBACK_RATIO = 0.5
# 세정 후 선형 재오염 가정 — 평가 기간 평균 회수율이 절반이 된다.
LINEAR_REFOULING_FACTOR = 0.5
DAYS_PER_MONTH = 30
KW_PER_MW = 1000
HOURS_PER_DAY = 24

NOTICE_ST_FALLBACK = "ST 정격이 등록되지 않아 GT 정격의 절반으로 가정했습니다."


@dataclass(frozen=True)
class LossResult:
    delta_backpressure_kpa: float
    delta_stack_temp_c: float
    power_loss_gt_mw: float
    power_loss_st_mw: float
    power_loss_total_mw: float
    daily_loss_won: float
    monthly_loss_won: float
    notices: tuple[str, ...]


def _state(value: float, alarm: float, trip: float) -> str:
    if value >= trip:
        return STATE_TRIP
    if value >= alarm:
        return STATE_ALARM
    return STATE_NORMAL


def operating_status(inputs: LossInputs, gt: GtSpec) -> dict[str, Any]:
    """운전 상태 판정 (specs/05 CALC-2). 종합 상태는 가장 나쁜 변수를 따른다."""
    variables = []
    for key, label, unit, value, alarm, trip in (
        (
            "backpressure",
            "배압",
            "kPa",
            inputs.backpressure_kpa,
            gt.backpressure_alarm_kpa,
            gt.backpressure_trip_kpa,
        ),
        (
            "exhaust_temp",
            "배기온도",
            "℃",
            inputs.exhaust_temp_c,
            gt.exhaust_temp_alarm_c,
            gt.exhaust_temp_trip_c,
        ),
    ):
        state = _state(value, alarm, trip)
        variables.append(
            {
                "key": key,
                "label": label,
                "unit": unit,
                "value": value,
                "state": state,
                "level": STATE_TO_LEVEL[state],
                "ratio_to_alarm_pct": round(value / alarm * 100, 1),
                "ratio_to_trip_pct": round(value / trip * 100, 1),
            }
        )
    levels = [v["level"] for v in variables]
    overall_level = worst(levels)
    overall_state = next(v["state"] for v in variables if v["level"] == overall_level)
    return {"state": overall_state, "level": overall_level, "variables": variables}


def rated_st_mw(gt: GtSpec) -> tuple[float, bool]:
    """(ST 정격, 가정 여부)"""
    if gt.rated_st_mw is not None:
        return gt.rated_st_mw, False
    return gt.rated_gt_mw * ST_RATED_FALLBACK_RATIO, True


def compute_loss(inputs: LossInputs, gt: GtSpec, params: dict[str, Any]) -> LossResult:
    """현재 손실(MW·원/일). 음의 차이는 손실이 아니다(보수적 추정, CALC-9)."""
    delta_bp = max(0.0, inputs.backpressure_kpa - inputs.clean_backpressure_kpa)
    delta_stack = max(0.0, inputs.stack_temp_c - inputs.clean_stack_temp_c)
    st_mw, st_assumed = rated_st_mw(gt)

    # 부분 부하에서 손실을 과대 계상하지 않는다(보수적 방향).
    load_ratio = inputs.gt_power_mw / gt.rated_gt_mw
    loss_gt = gt.rated_gt_mw * params["dp_power_loss_coeff"] / 100 * delta_bp * load_ratio
    loss_st = st_mw * params["stack_temp_loss_coeff"] / 100 * delta_stack * load_ratio
    total = loss_gt + loss_st

    daily = (
        total
        * inputs.operating_hours_per_day
        * params["capacity_factor"]
        * KW_PER_MW
        * inputs.smp_won_per_kwh
    )
    return LossResult(
        delta_backpressure_kpa=delta_bp,
        delta_stack_temp_c=delta_stack,
        power_loss_gt_mw=loss_gt,
        power_loss_st_mw=loss_st,
        power_loss_total_mw=total,
        daily_loss_won=daily,
        monthly_loss_won=daily * DAYS_PER_MONTH,
        notices=(NOTICE_ST_FALLBACK,) if st_assumed else (),
    )


@dataclass(frozen=True)
class MethodResult:
    method_id: int
    name: str
    cleaning_cost_won: float
    outage_loss_won: float
    total_cost_won: float
    recovered_daily_won: float
    gross_benefit_won: float
    net_benefit_won: float
    payback_days: float | None


def evaluate_method(
    daily_loss_won: float,
    smp_won_per_kwh: float,
    gt: GtSpec,
    method: MethodSpec,
    params: dict[str, Any],
) -> MethodResult:
    """공법 하나의 비용·회수 효과. 정지 손실은 매출이 아니라 마진 기준이다."""
    st_mw, _ = rated_st_mw(gt)
    recovered_daily = daily_loss_won * method.recovery_ratio
    outage_loss = (
        (gt.rated_gt_mw + st_mw)
        * HOURS_PER_DAY
        * params["capacity_factor"]
        * method.outage_days
        * KW_PER_MW
        * smp_won_per_kwh
        * (1 - params["fuel_cost_ratio"])
    )
    total_cost = method.cleaning_cost_won + outage_loss
    gross = recovered_daily * params["evaluation_horizon_days"] * LINEAR_REFOULING_FACTOR
    payback = total_cost / recovered_daily if recovered_daily > 0 else None
    return MethodResult(
        method_id=method.id,
        name=method.name,
        cleaning_cost_won=method.cleaning_cost_won,
        outage_loss_won=outage_loss,
        total_cost_won=total_cost,
        recovered_daily_won=recovered_daily,
        gross_benefit_won=gross,
        net_benefit_won=gross - total_cost,
        payback_days=payback,
    )


def compare_methods(
    daily_loss_won: float,
    smp_won_per_kwh: float,
    gt: GtSpec,
    methods: list[MethodSpec],
    params: dict[str, Any],
) -> list[MethodResult]:
    """공법별 결과를 순편익 큰 순서로 (specs/05 CALC-3). 같으면 이름순 — 결과 순서도 결정적이다."""
    results = [evaluate_method(daily_loss_won, smp_won_per_kwh, gt, m, params) for m in methods]
    return sorted(results, key=lambda r: (-r.net_benefit_won, r.name))
