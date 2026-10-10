"""참조 데이터(DB) → 계산 서비스 입력 타입 (specs/05 §9).

services/* 는 Django 모델을 모른다. 이 모듈이 그 사이를 잇는다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from calculator.services.types import GtSpec, MethodSpec
from common.exceptions import NotFound, ValidationError
from common.settings_resolver import get_setting
from reference.models import CalcParameterSet, CleaningMethod, GtModel, SmpPrice
from reference.param_defs import default_params


@dataclass(frozen=True)
class ParamContext:
    version_label: str
    params: dict[str, Any]
    is_seed: bool


def active_params() -> ParamContext:
    """활성 파라미터 세트. 아직 시드 전이면 코드 시드값으로 계산하되 임시값으로 표시한다."""
    row = CalcParameterSet.objects.filter(is_active=True).first()
    if row is None:
        return ParamContext(version_label="seed", params=default_params(), is_seed=True)
    return ParamContext(version_label=row.version_label, params=row.params, is_seed=row.is_seed)


def get_gt_model(gt_model_id: int) -> GtModel:
    model = GtModel.objects.filter(pk=gt_model_id, is_active=True).first()
    if model is None:
        raise NotFound(message="사용할 수 있는 GT 모델이 아닙니다.", code="GT_MODEL_NOT_FOUND")
    return model


def to_gt_spec(model: GtModel) -> GtSpec:
    return GtSpec(
        rated_gt_mw=model.rated_gt_mw,
        rated_st_mw=model.rated_st_mw,
        backpressure_alarm_kpa=model.backpressure_alarm_kpa,
        backpressure_trip_kpa=model.backpressure_trip_kpa,
        exhaust_temp_alarm_c=model.exhaust_temp_alarm_c,
        exhaust_temp_trip_c=model.exhaust_temp_trip_c,
    )


def to_method_spec(method: CleaningMethod) -> MethodSpec:
    return MethodSpec(
        id=method.id,
        name=method.name,
        cleaning_cost_won=method.cleaning_cost_won,
        outage_days=method.outage_days,
        recovery_ratio=method.recovery_ratio,
    )


def active_methods() -> list[CleaningMethod]:
    return list(CleaningMethod.objects.filter(is_active=True).order_by("name"))


def default_method() -> CleaningMethod | None:
    """설정 calc_default_method(공법 이름). 없거나 비활성이면 첫 공법."""
    name = get_setting("calc_default_method")
    methods = active_methods()
    return next((m for m in methods if m.name == name), methods[0] if methods else None)


def get_method(method_id: int | None) -> CleaningMethod:
    if method_id is None:
        method = default_method()
    else:
        method = CleaningMethod.objects.filter(pk=method_id, is_active=True).first()
    if method is None:
        raise NotFound(message="사용할 수 있는 세정 공법이 아닙니다.", code="METHOD_NOT_FOUND")
    return method


def latest_smp() -> SmpPrice | None:
    return SmpPrice.objects.order_by("-as_of_date", "-created_at").first()


def resolve_smp(user_value: float | None) -> dict[str, Any]:
    """계산에 쓸 SMP 와 그 출처 표시 (specs/06 REF-4).

    사용자가 값을 주면 '사용자 입력', 아니면 등록된 최신값. 둘 다 없으면 계산할 수 없다.
    """
    registered = latest_smp()
    if user_value is not None:
        return {
            "value": user_value,
            "user_input": True,
            "is_estimate": False,
            "as_of": None,
            "source": "사용자 입력",
        }
    if registered is None:
        raise ValidationError(
            message="등록된 SMP 가 없습니다. SMP 를 직접 입력해 주세요.",
            code="SMP_REQUIRED",
            details={"smp_won_per_kwh": ["SMP 를 입력해 주세요."]},
        )
    return {
        "value": registered.value_won_per_kwh,
        "user_input": False,
        "is_estimate": registered.is_estimate,
        "as_of": registered.as_of_date.isoformat(),
        "source": registered.source,
    }
