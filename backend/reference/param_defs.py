"""계산 파라미터 세트의 항목 정의 (specs/06 §5).

여기 있는 값은 **시드값**일 뿐이다(AGENTS.md §1.2). 실제 계산은 DB 의 활성 CalcParameterSet 을 쓴다.
관리자 화면은 이 정의를 API 로 받아 그리므로, 프론트 번들에 계수 이름·값이 들어가지 않는다
(specs/05 CALC-8).

순수 모듈 — Django 모델을 import 하지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

KIND_NUMBER = "NUMBER"
KIND_RANGE = "RANGE"  # [하한, 상한]

GROUP_LOSS = "LOSS"
GROUP_PINCH = "PINCH"


@dataclass(frozen=True)
class ParamDef:
    key: str
    label: str
    default: Any
    unit: str = ""
    min_value: float | None = None
    max_value: float | None = None
    kind: str = KIND_NUMBER
    group: str = GROUP_LOSS
    description: str = ""


PARAM_DEFS: tuple[ParamDef, ...] = (
    # --- 손실 모델 `[임시값]` (specs/05 §6) ---
    ParamDef(
        "dp_power_loss_coeff",
        "배압 손실 계수",
        0.35,
        unit="%MW/kPa",
        min_value=0,
        max_value=5,
        description="배압 1 kPa 상승당 GT 출력 손실",
    ),
    ParamDef(
        "stack_temp_loss_coeff",
        "굴뚝 온도 손실 계수",
        0.12,
        unit="%MW(ST)/℃",
        min_value=0,
        max_value=5,
        description="굴뚝 온도 1 ℃ 상승당 ST 출력 손실",
    ),
    ParamDef("capacity_factor", "이용률", 0.85, min_value=0.01, max_value=1),
    ParamDef(
        "fuel_cost_ratio",
        "전력단가 중 연료비 비중",
        0.792,
        min_value=0,
        max_value=0.99,
        description="세정 정지 손실을 마진 기준으로 계산할 때 쓴다(정지 중에는 연료를 쓰지 않는다)",
    ),
    ParamDef(
        "evaluation_horizon_days",
        "편익 평가 기간",
        365,
        unit="일",
        min_value=30,
        max_value=3650,
    ),
    ParamDef(
        "default_operating_hours_per_day",
        "일 운전 시간 기본값",
        20,
        unit="h/일",
        min_value=1,
        max_value=24,
    ),
    # --- 핀치·어프로치 판정 기준 `[임시값]` (specs/05 §5) ---
    ParamDef(
        "calc_pinch_range_c",
        "핀치 기준 범위",
        [5, 15],
        unit="℃",
        min_value=0,
        max_value=100,
        kind=KIND_RANGE,
        group=GROUP_PINCH,
        description="설계값이 없을 때 쓰는 정상 범위. 상한을 넘으면 주의",
    ),
    ParamDef(
        "calc_approach_range_c",
        "어프로치 기준 범위",
        [3, 15],
        unit="℃",
        min_value=0,
        max_value=100,
        kind=KIND_RANGE,
        group=GROUP_PINCH,
        description="설계값이 없을 때 쓰는 정상 범위. 벗어나면 주의, 0 미만이면 위험(스티밍 우려)",
    ),
    ParamDef(
        "calc_pinch_margin_c",
        "설계값 대비 허용 여유",
        3,
        unit="℃",
        min_value=0,
        max_value=50,
        group=GROUP_PINCH,
        description="설계 핀치·어프로치가 주어졌을 때 이만큼 벗어나면 주의",
    ),
)

PARAM_DEF_BY_KEY: dict[str, ParamDef] = {d.key: d for d in PARAM_DEFS}


def default_params() -> dict[str, Any]:
    return {d.key: d.default for d in PARAM_DEFS}


class ParamValidationError(Exception):
    def __init__(self, message: str, details: dict[str, list[str]]) -> None:
        self.message = message
        self.details = details
        super().__init__(message)


def _check_number(definition: ParamDef, value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError("숫자여야 합니다.")
    if definition.min_value is not None and value < definition.min_value:
        raise ValueError(f"{definition.min_value:g} 이상이어야 합니다.")
    if definition.max_value is not None and value > definition.max_value:
        raise ValueError(f"{definition.max_value:g} 이하여야 합니다.")
    return float(value)


def validate_params(params: Any) -> dict[str, Any]:
    """파라미터 세트 전체를 검증한다. 빠진 키·모르는 키·범위 오류를 한 번에 알린다."""
    if not isinstance(params, dict):
        raise ParamValidationError("파라미터는 객체여야 합니다.", {"params": ["객체여야 합니다."]})

    errors: dict[str, list[str]] = {}
    for key in sorted(set(params) - set(PARAM_DEF_BY_KEY)):
        errors[key] = ["정의되지 않은 항목입니다."]

    clean: dict[str, Any] = {}
    for definition in PARAM_DEFS:
        if definition.key not in params:
            errors[definition.key] = ["값이 필요합니다."]
            continue
        value = params[definition.key]
        try:
            if definition.kind == KIND_RANGE:
                if not isinstance(value, list | tuple) or len(value) != 2:
                    raise ValueError("[하한, 상한] 두 값이어야 합니다.")
                low, high = (_check_number(definition, v) for v in value)
                if low > high:
                    raise ValueError("하한이 상한보다 클 수 없습니다.")
                clean[definition.key] = [low, high]
            else:
                clean[definition.key] = _check_number(definition, value)
        except ValueError as exc:
            errors[definition.key] = [f"{definition.label}: {exc}"]

    if errors:
        raise ParamValidationError("계산 파라미터가 올바르지 않습니다.", errors)
    return clean


def describe() -> list[dict[str, Any]]:
    """관리자 화면이 쓰는 정의 목록(라벨·단위·범위). 값은 담지 않는다."""
    return [
        {
            "key": d.key,
            "label": d.label,
            "unit": d.unit,
            "min_value": d.min_value,
            "max_value": d.max_value,
            "kind": d.kind,
            "group": d.group,
            "description": d.description,
            "default": d.default,
        }
        for d in PARAM_DEFS
    ]
