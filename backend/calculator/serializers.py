"""계산기 입력 검증 (specs/05 §3.1, §5.1).

검증 범위는 물리적 타당성 검사다. 튜닝값이 아니므로 이름 붙은 모듈 상수로 둔다(AGENTS.md §1.2).
"""

from __future__ import annotations

from rest_framework import serializers

MAX_BACKPRESSURE_KPA = 50
MIN_EXHAUST_TEMP_C, MAX_EXHAUST_TEMP_C = 200, 700
MIN_STACK_TEMP_C, MAX_STACK_TEMP_C = 40, 250
MAX_HOURS_PER_DAY = 24
MAX_SMP_WON_PER_KWH = 1000
MAX_GT_POWER_OVER_RATED = 1.2
MAX_DRUM_PRESSURE_BARG = 200
MAX_PINCH_STAGES = 3


def _number(label: str, *, min_value=None, max_value=None, min_exclusive=False):
    """선택 입력 숫자. 비우면 서버가 기본값(설계값 등)을 채운다."""
    return serializers.FloatField(
        label=label,
        required=False,
        allow_null=True,
        min_value=None if min_exclusive else min_value,
        max_value=max_value,
    )


class LossInputSerializer(serializers.Serializer):
    gt_model_id = serializers.IntegerField(label="GT 모델")
    gt_power_mw = _number("GT 출력", min_value=0, min_exclusive=True)
    backpressure_kpa = _number("현재 배압", min_value=0, max_value=MAX_BACKPRESSURE_KPA)
    clean_backpressure_kpa = _number("청정(설계) 배압", min_value=0, max_value=MAX_BACKPRESSURE_KPA)
    exhaust_temp_c = _number("배기온도", min_value=MIN_EXHAUST_TEMP_C, max_value=MAX_EXHAUST_TEMP_C)
    stack_temp_c = _number("현재 굴뚝 온도", min_value=MIN_STACK_TEMP_C, max_value=MAX_STACK_TEMP_C)
    clean_stack_temp_c = _number(
        "청정(설계) 굴뚝 온도", min_value=MIN_STACK_TEMP_C, max_value=MAX_STACK_TEMP_C
    )
    operating_hours_per_day = _number(
        "일 운전 시간", max_value=MAX_HOURS_PER_DAY, min_exclusive=True
    )
    smp_won_per_kwh = _number("SMP", max_value=MAX_SMP_WON_PER_KWH, min_exclusive=True)
    cleaning_method_id = serializers.IntegerField(
        label="세정 공법", required=False, allow_null=True
    )

    def validate(self, attrs: dict) -> dict:
        # FloatField 의 min_value 는 '이상'이라 0 을 허용한다. '초과'가 필요한 항목은 여기서 본다.
        errors = {}
        for key, label in (
            ("gt_power_mw", "GT 출력"),
            ("operating_hours_per_day", "일 운전 시간"),
            ("smp_won_per_kwh", "SMP"),
        ):
            value = attrs.get(key)
            if value is not None and value <= 0:
                errors[key] = [f"{label}은(는) 0 보다 커야 합니다."]
        if errors:
            raise serializers.ValidationError(errors)
        return attrs


class PinchStageSerializer(serializers.Serializer):
    label = serializers.CharField(max_length=20, required=False, default="")
    drum_pressure_barg = serializers.FloatField(
        label="드럼 압력", min_value=0, max_value=MAX_DRUM_PRESSURE_BARG
    )
    evaporator_outlet_gas_temp_c = serializers.FloatField(
        label="증발기 출구 가스 온도", min_value=0, max_value=MAX_EXHAUST_TEMP_C
    )
    economizer_outlet_water_temp_c = serializers.FloatField(
        label="절탄기 출구 급수 온도", min_value=0, max_value=MAX_EXHAUST_TEMP_C
    )
    design_pinch_c = serializers.FloatField(required=False, allow_null=True, min_value=0)
    design_approach_c = serializers.FloatField(required=False, allow_null=True)


class PinchInputSerializer(serializers.Serializer):
    gt_model_id = serializers.IntegerField(required=False, allow_null=True)
    stages = PinchStageSerializer(many=True, allow_empty=False)

    def validate_stages(self, value: list) -> list:
        if len(value) > MAX_PINCH_STAGES:
            raise serializers.ValidationError(
                f"압력단은 {MAX_PINCH_STAGES}개까지 입력할 수 있습니다."
            )
        return value
