"""계산 실행 — 입력 기본값 채우기 → 순수 계산 → 응답 조립 (specs/05).

뷰와 챗봇 도구(N5)가 같은 함수를 부른다. 그래서 계산 카드와 계산기 화면의 수치가 같다(AC-02-3).

**응답에 계수·식·한계값 원본을 넣지 않는다**(specs/05 CALC-8). 아래 _meta()·_result_dict() 가
응답에 들어갈 수 있는 필드의 전부다 — 여기에 계수를 추가하면 비공개가 깨진다.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from calculator import repository as repo
from calculator.serializers import MAX_GT_POWER_OVER_RATED
from calculator.services.loss import (
    FORMULA_VERSION,
    LossResult,
    MethodResult,
    compare_methods,
    compute_loss,
    evaluate_method,
    operating_status,
)
from calculator.services.pinch import PinchInputError, check_stages
from calculator.services.types import LossInputs, PinchStageInput
from common.exceptions import ValidationError

NOTICE_PLACEHOLDER = "임시 참조값을 사용한 결과입니다. 참고용으로만 보세요."


def _round(value: float | None, digits: int) -> float | None:
    return None if value is None else round(value, digits)


def _loss_dict(result: LossResult) -> dict[str, Any]:
    return {
        "delta_backpressure_kpa": _round(result.delta_backpressure_kpa, 3),
        "delta_stack_temp_c": _round(result.delta_stack_temp_c, 2),
        "power_loss_gt_mw": _round(result.power_loss_gt_mw, 3),
        "power_loss_st_mw": _round(result.power_loss_st_mw, 3),
        "power_loss_total_mw": _round(result.power_loss_total_mw, 3),
        "daily_loss_won": _round(result.daily_loss_won, 0),
        "monthly_loss_won": _round(result.monthly_loss_won, 0),
    }


def _method_dict(result: MethodResult) -> dict[str, Any]:
    data = asdict(result)
    for key in ("cleaning_cost_won", "outage_loss_won", "total_cost_won", "recovered_daily_won"):
        data[key] = _round(data[key], 0)
    data["gross_benefit_won"] = _round(data["gross_benefit_won"], 0)
    data["net_benefit_won"] = _round(data["net_benefit_won"], 0)
    data["payback_days"] = _round(data["payback_days"], 1)
    return data


def _meta(params_ctx, *, gt_model=None, methods=(), smp=None, notices=()) -> dict[str, Any]:
    uses_placeholder = params_ctx.is_seed or bool(gt_model and gt_model.is_placeholder)
    uses_placeholder = uses_placeholder or any(m.is_placeholder for m in methods)
    all_notices = list(notices)
    if uses_placeholder:
        all_notices.insert(0, NOTICE_PLACEHOLDER)
    meta: dict[str, Any] = {
        "param_version": params_ctx.version_label,
        "formula_version": FORMULA_VERSION,
        "uses_placeholder": uses_placeholder,
        "notices": all_notices,
    }
    if gt_model is not None:
        meta["gt_model"] = {"id": gt_model.id, "name": gt_model.name, "version": gt_model.version}
    if methods:
        meta["methods"] = [{"id": m.id, "name": m.name, "version": m.version} for m in methods]
    if smp is not None:
        meta["smp"] = smp
    return meta


def _fill_loss_inputs(data: dict[str, Any], gt_model) -> dict[str, Any]:
    """비운 칸을 설계값·기본값으로 채운 입력. 화면이 이 값을 그대로 보여 준다."""
    params_ctx = repo.active_params()

    def pick(key: str, default: float) -> float:
        value = data.get(key)
        return default if value is None else value

    filled = {
        "gt_model_id": gt_model.id,
        "gt_power_mw": pick("gt_power_mw", gt_model.rated_gt_mw),
        "backpressure_kpa": pick("backpressure_kpa", gt_model.design_backpressure_kpa),
        "clean_backpressure_kpa": pick("clean_backpressure_kpa", gt_model.design_backpressure_kpa),
        "exhaust_temp_c": pick("exhaust_temp_c", gt_model.design_exhaust_temp_c),
        "stack_temp_c": pick("stack_temp_c", gt_model.design_stack_temp_c),
        "clean_stack_temp_c": pick("clean_stack_temp_c", gt_model.design_stack_temp_c),
        "operating_hours_per_day": pick(
            "operating_hours_per_day", params_ctx.params["default_operating_hours_per_day"]
        ),
    }
    max_power = gt_model.rated_gt_mw * MAX_GT_POWER_OVER_RATED
    if filled["gt_power_mw"] > max_power:
        raise ValidationError(
            message="GT 출력이 정격의 120 % 를 넘습니다.",
            details={"gt_power_mw": [f"{max_power:.1f} MW 이하로 입력해 주세요."]},
        )
    return filled


def _prepare(data: dict[str, Any]):
    gt_model = repo.get_gt_model(data["gt_model_id"])
    filled = _fill_loss_inputs(data, gt_model)
    smp = repo.resolve_smp(data.get("smp_won_per_kwh"))
    inputs = LossInputs(
        gt_power_mw=filled["gt_power_mw"],
        backpressure_kpa=filled["backpressure_kpa"],
        clean_backpressure_kpa=filled["clean_backpressure_kpa"],
        exhaust_temp_c=filled["exhaust_temp_c"],
        stack_temp_c=filled["stack_temp_c"],
        clean_stack_temp_c=filled["clean_stack_temp_c"],
        operating_hours_per_day=filled["operating_hours_per_day"],
        smp_won_per_kwh=smp["value"],
    )
    return gt_model, filled, smp, inputs


def run_loss(data: dict[str, Any]) -> dict[str, Any]:
    """현재 상태·예상 손실·회수 효과 (specs/05 CALC-1·2)."""
    params_ctx = repo.active_params()
    gt_model, filled, smp, inputs = _prepare(data)
    method = repo.get_method(data.get("cleaning_method_id"))
    gt = repo.to_gt_spec(gt_model)

    loss = compute_loss(inputs, gt, params_ctx.params)
    recovery = evaluate_method(
        loss.daily_loss_won, smp["value"], gt, repo.to_method_spec(method), params_ctx.params
    )
    return {
        "inputs": {**filled, "smp_won_per_kwh": smp["value"], "cleaning_method_id": method.id},
        "status": operating_status(inputs, gt),
        "results": {**_loss_dict(loss), "recovery": _method_dict(recovery)},
        "meta": _meta(
            params_ctx, gt_model=gt_model, methods=[method], smp=smp, notices=loss.notices
        ),
    }


def run_methods(data: dict[str, Any]) -> dict[str, Any]:
    """공법별 비용 비교 (specs/05 CALC-3). 순편익 최대 공법에 is_best 를 단다 — '권장' 이 아니다."""
    params_ctx = repo.active_params()
    gt_model, filled, smp, inputs = _prepare(data)
    methods = repo.active_methods()
    if not methods:
        raise ValidationError(message="사용 중인 세정 공법이 없습니다.", code="NO_METHODS")
    gt = repo.to_gt_spec(gt_model)

    loss = compute_loss(inputs, gt, params_ctx.params)
    rows = [
        _method_dict(r)
        for r in compare_methods(
            loss.daily_loss_won,
            smp["value"],
            gt,
            [repo.to_method_spec(m) for m in methods],
            params_ctx.params,
        )
    ]
    best = max(r["net_benefit_won"] for r in rows)
    for row in rows:
        row["is_best"] = row["net_benefit_won"] == best
    return {
        "inputs": {**filled, "smp_won_per_kwh": smp["value"]},
        "status": operating_status(inputs, gt),
        "results": {**_loss_dict(loss), "methods": rows},
        "meta": _meta(
            params_ctx, gt_model=gt_model, methods=methods, smp=smp, notices=loss.notices
        ),
    }


def run_pinch(data: dict[str, Any]) -> dict[str, Any]:
    """핀치·어프로치 (specs/05 CALC-4). 판정 기준은 공개해도 되는 값이라 응답에 함께 준다."""
    params_ctx = repo.active_params()
    stages = [
        PinchStageInput(
            label=stage.get("label") or f"{index + 1}단",
            drum_pressure_barg=stage["drum_pressure_barg"],
            evaporator_outlet_gas_temp_c=stage["evaporator_outlet_gas_temp_c"],
            economizer_outlet_water_temp_c=stage["economizer_outlet_water_temp_c"],
            design_pinch_c=stage.get("design_pinch_c"),
            design_approach_c=stage.get("design_approach_c"),
        )
        for index, stage in enumerate(data["stages"])
    ]
    try:
        result = check_stages(stages, params_ctx.params)
    except PinchInputError as exc:
        raise ValidationError(message=str(exc), code="PINCH_INPUT_INVALID") from exc

    meta = _meta(params_ctx)
    meta["criteria"] = {
        "pinch_range_c": params_ctx.params["calc_pinch_range_c"],
        "approach_range_c": params_ctx.params["calc_approach_range_c"],
        "design_margin_c": params_ctx.params["calc_pinch_margin_c"],
    }
    return {"results": result, "meta": meta}


def options() -> dict[str, Any]:
    """계산기 화면 초기값 (specs/10 §4). 경보·트립 한계값은 넣지 않는다."""
    params_ctx = repo.active_params()
    smp = repo.latest_smp()
    default = repo.default_method()
    return {
        "gt_models": [
            {
                "id": m.id,
                "name": m.name,
                "manufacturer": m.manufacturer,
                "rated_gt_mw": m.rated_gt_mw,
                "rated_st_mw": m.rated_st_mw,
                "design_backpressure_kpa": m.design_backpressure_kpa,
                "design_exhaust_temp_c": m.design_exhaust_temp_c,
                "design_stack_temp_c": m.design_stack_temp_c,
                "is_placeholder": m.is_placeholder,
            }
            for m in repo.GtModel.objects.filter(is_active=True).order_by("name")
        ],
        "cleaning_methods": [
            {"id": m.id, "name": m.name, "is_placeholder": m.is_placeholder}
            for m in repo.active_methods()
        ],
        "smp": (
            None
            if smp is None
            else {
                "value": smp.value_won_per_kwh,
                "as_of": smp.as_of_date.isoformat(),
                "period_label": smp.period_label,
                "source": smp.source,
                "is_estimate": smp.is_estimate,
            }
        ),
        "defaults": {
            "operating_hours_per_day": params_ctx.params["default_operating_hours_per_day"],
            "cleaning_method_id": default.id if default else None,
        },
        "limits": {"max_gt_power_over_rated": MAX_GT_POWER_OVER_RATED},
        "param_version": params_ctx.version_label,
        "formula_version": FORMULA_VERSION,
    }


# 미리보기 예시 입력 — 설계값에서 이만큼 나빠진 상태를 가정한다(관리자 화면 비교용).
PREVIEW_BACKPRESSURE_RISE_KPA = 1.0
PREVIEW_STACK_TEMP_RISE_C = 5.0


def preview_params(candidate: dict[str, Any]) -> dict[str, Any]:
    """후보 파라미터와 현재 활성 파라미터로 같은 예시 입력을 계산해 비교한다 (specs/06 REF-5).

    관리자 전용 응답이다. 저장하지 않는다.
    """
    gt_model = repo.GtModel.objects.filter(is_active=True).order_by("name").first()
    methods = repo.active_methods()
    smp = repo.latest_smp()
    if gt_model is None or not methods or smp is None:
        raise ValidationError(
            message="미리보기에는 사용 중인 GT 모델·세정 공법과 등록된 SMP 가 하나씩 필요합니다.",
            code="PREVIEW_UNAVAILABLE",
        )
    gt = repo.to_gt_spec(gt_model)
    specs = [repo.to_method_spec(m) for m in methods]

    def calculate(params: dict[str, Any]) -> dict[str, Any]:
        inputs = LossInputs(
            gt_power_mw=gt_model.rated_gt_mw,
            backpressure_kpa=gt_model.design_backpressure_kpa + PREVIEW_BACKPRESSURE_RISE_KPA,
            clean_backpressure_kpa=gt_model.design_backpressure_kpa,
            exhaust_temp_c=gt_model.design_exhaust_temp_c,
            stack_temp_c=gt_model.design_stack_temp_c + PREVIEW_STACK_TEMP_RISE_C,
            clean_stack_temp_c=gt_model.design_stack_temp_c,
            operating_hours_per_day=params["default_operating_hours_per_day"],
            smp_won_per_kwh=smp.value_won_per_kwh,
        )
        loss = compute_loss(inputs, gt, params)
        rows = compare_methods(loss.daily_loss_won, smp.value_won_per_kwh, gt, specs, params)
        return {**_loss_dict(loss), "methods": [_method_dict(r) for r in rows]}

    current = repo.active_params()
    return {
        "example": {
            "gt_model": gt_model.name,
            "backpressure_rise_kpa": PREVIEW_BACKPRESSURE_RISE_KPA,
            "stack_temp_rise_c": PREVIEW_STACK_TEMP_RISE_C,
            "smp_won_per_kwh": smp.value_won_per_kwh,
        },
        "current": {"param_version": current.version_label, **calculate(current.params)},
        "candidate": calculate(candidate),
    }
