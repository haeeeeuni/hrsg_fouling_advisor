"""핀치·어프로치 점검 (specs/05 §5).

공개 열역학 계산이라 식을 화면에 보여 줘도 된다(비공개 대상은 손실 모델뿐이다).
판정 기준은 `[임시값]` 이며 계산 파라미터 세트에 있다.
"""

from __future__ import annotations

from typing import Any

from calculator.services.steam import saturation_temperature_c_from_barg
from calculator.services.types import (
    LEVEL_CAUTION,
    LEVEL_DANGER,
    LEVEL_NORMAL,
    PinchStageInput,
    worst,
)


class PinchInputError(ValueError):
    """물리적으로 불가능한 입력(증발기 출구 가스가 포화온도보다 차가움 등)."""


def _judge_pinch(pinch: float, stage: PinchStageInput, params: dict[str, Any]) -> tuple[str, str]:
    margin = params["calc_pinch_margin_c"]
    if stage.design_pinch_c is not None:
        limit = stage.design_pinch_c + margin
        if pinch > limit:
            return LEVEL_CAUTION, f"설계 핀치보다 {pinch - stage.design_pinch_c:.1f} ℃ 큽니다."
        return LEVEL_NORMAL, ""
    low, high = params["calc_pinch_range_c"]
    if pinch > high:
        return LEVEL_CAUTION, f"기준 범위({low:g}~{high:g} ℃)보다 큽니다 — 열 회수 저하 의심."
    return LEVEL_NORMAL, ""


def _judge_approach(
    approach: float, stage: PinchStageInput, params: dict[str, Any]
) -> tuple[str, str]:
    if approach < 0:
        return LEVEL_DANGER, "절탄기 출구 급수가 포화온도를 넘었습니다 — 스티밍 우려."
    margin = params["calc_pinch_margin_c"]
    if stage.design_approach_c is not None:
        if abs(approach - stage.design_approach_c) > margin:
            return (
                LEVEL_CAUTION,
                f"설계 어프로치와 {approach - stage.design_approach_c:+.1f} ℃ 다릅니다.",
            )
        return LEVEL_NORMAL, ""
    low, high = params["calc_approach_range_c"]
    if approach < low:
        return (
            LEVEL_CAUTION,
            f"기준 범위({low:g}~{high:g} ℃)보다 작습니다 — 스티밍 여유가 적습니다.",
        )
    if approach > high:
        return LEVEL_CAUTION, f"기준 범위({low:g}~{high:g} ℃)보다 큽니다."
    return LEVEL_NORMAL, ""


def check_stage(stage: PinchStageInput, params: dict[str, Any]) -> dict[str, Any]:
    t_sat = saturation_temperature_c_from_barg(stage.drum_pressure_barg)
    pinch = stage.evaporator_outlet_gas_temp_c - t_sat
    approach = t_sat - stage.economizer_outlet_water_temp_c
    if pinch < 0:
        raise PinchInputError(
            f"{stage.label}: 증발기 출구 가스 온도가 포화온도({t_sat:.1f} ℃)보다 낮을 수 없습니다."
        )
    pinch_level, pinch_note = _judge_pinch(pinch, stage, params)
    approach_level, approach_note = _judge_approach(approach, stage, params)
    return {
        "label": stage.label,
        "drum_pressure_barg": stage.drum_pressure_barg,
        "evaporator_outlet_gas_temp_c": stage.evaporator_outlet_gas_temp_c,
        "economizer_outlet_water_temp_c": stage.economizer_outlet_water_temp_c,
        "saturation_temp_c": round(t_sat, 2),
        "pinch_c": round(pinch, 2),
        "approach_c": round(approach, 2),
        "pinch_level": pinch_level,
        "approach_level": approach_level,
        "level": worst([pinch_level, approach_level]),
        "notes": [note for note in (pinch_note, approach_note) if note],
    }


def check_stages(stages: list[PinchStageInput], params: dict[str, Any]) -> dict[str, Any]:
    results = [check_stage(stage, params) for stage in stages]
    return {"level": worst([r["level"] for r in results]), "stages": results}
