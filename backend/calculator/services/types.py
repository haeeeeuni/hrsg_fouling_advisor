"""계산기 입출력 타입. 참조 데이터는 Django 모델이 아니라 이 dataclass 로 받는다(AGENTS.md §3)."""

from __future__ import annotations

from dataclasses import dataclass

# 상태 수준 — 화면의 정상·주의·위험 (specs/12 UI-6)
LEVEL_NORMAL = "NORMAL"
LEVEL_CAUTION = "CAUTION"
LEVEL_DANGER = "DANGER"
LEVEL_ORDER = {LEVEL_NORMAL: 0, LEVEL_CAUTION: 1, LEVEL_DANGER: 2}

# 운전 상태 — 정상·경보·트립 (specs/05 CALC-2)
STATE_NORMAL = "NORMAL"
STATE_ALARM = "ALARM"
STATE_TRIP = "TRIP"
STATE_TO_LEVEL = {STATE_NORMAL: LEVEL_NORMAL, STATE_ALARM: LEVEL_CAUTION, STATE_TRIP: LEVEL_DANGER}


def worst(levels: list[str]) -> str:
    return max(levels, key=LEVEL_ORDER.__getitem__, default=LEVEL_NORMAL)


@dataclass(frozen=True)
class GtSpec:
    rated_gt_mw: float
    rated_st_mw: float | None
    backpressure_alarm_kpa: float
    backpressure_trip_kpa: float
    exhaust_temp_alarm_c: float
    exhaust_temp_trip_c: float


@dataclass(frozen=True)
class MethodSpec:
    id: int
    name: str
    cleaning_cost_won: float
    outage_days: float
    recovery_ratio: float


@dataclass(frozen=True)
class LossInputs:
    gt_power_mw: float
    backpressure_kpa: float
    clean_backpressure_kpa: float
    exhaust_temp_c: float
    stack_temp_c: float
    clean_stack_temp_c: float
    operating_hours_per_day: float
    smp_won_per_kwh: float


@dataclass(frozen=True)
class PinchStageInput:
    label: str
    drum_pressure_barg: float
    evaporator_outlet_gas_temp_c: float
    economizer_outlet_water_temp_c: float
    design_pinch_c: float | None = None
    design_approach_c: float | None = None
