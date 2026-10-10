"""참조 데이터 관리자 API 직렬화 (specs/06, specs/08 ADM-7).

이 직렬화기는 **관리자 전용**이다. 한계값 원본·계수가 들어 있으므로 USER 응답에 쓰지 않는다.
"""

from __future__ import annotations

from rest_framework import serializers

from common.exceptions import Conflict
from reference.models import CalcParameterSet, CleaningMethod, GtModel, SmpPrice
from reference.param_defs import ParamValidationError, validate_params


class VersionedSerializer(serializers.ModelSerializer):
    """수정 요청에 version 을 실어 보내면, 다른 관리자가 먼저 고쳤을 때 409 를 낸다(ADM-7)."""

    def validate(self, attrs: dict) -> dict:
        expected = self.initial_data.get("version") if isinstance(self.initial_data, dict) else None
        if self.instance is not None and expected is not None:
            if int(expected) != self.instance.version:
                raise Conflict(
                    code="STALE_VERSION",
                    message="다른 관리자가 먼저 수정했습니다. 새로고침 후 다시 시도하세요.",
                    details={"current_version": self.instance.version},
                )
        return attrs

    def update(self, instance, validated_data):
        validated_data.pop("version", None)
        changed = any(getattr(instance, k) != v for k, v in validated_data.items())
        instance = super().update(instance, validated_data)
        if changed:
            instance.version += 1
            instance.save(update_fields=["version", "updated_at"])
        return instance


class GtModelSerializer(VersionedSerializer):
    class Meta:
        model = GtModel
        fields = [
            "id",
            "name",
            "manufacturer",
            "rated_gt_mw",
            "rated_st_mw",
            "design_backpressure_kpa",
            "backpressure_alarm_kpa",
            "backpressure_trip_kpa",
            "design_exhaust_temp_c",
            "exhaust_temp_alarm_c",
            "exhaust_temp_trip_c",
            "design_stack_temp_c",
            "is_placeholder",
            "is_active",
            "note",
            "version",
            "updated_at",
        ]
        read_only_fields = ["id", "version", "updated_at"]

    def validate(self, attrs: dict) -> dict:
        attrs = super().validate(attrs)

        def value(key):
            return attrs.get(key, getattr(self.instance, key, None))

        errors: dict[str, list[str]] = {}
        if (value("rated_gt_mw") or 0) <= 0:
            errors["rated_gt_mw"] = ["정격 출력은 0 보다 커야 합니다."]
        rated_st = value("rated_st_mw")
        if rated_st is not None and rated_st <= 0:
            errors["rated_st_mw"] = ["ST 정격은 비우거나 0 보다 커야 합니다."]
        for alarm, trip, label in (
            ("backpressure_alarm_kpa", "backpressure_trip_kpa", "배압"),
            ("exhaust_temp_alarm_c", "exhaust_temp_trip_c", "배기온도"),
        ):
            if value(alarm) is not None and value(trip) is not None and value(alarm) >= value(trip):
                errors[trip] = [f"{label} 트립 한계는 경보 한계보다 커야 합니다."]
        if errors:
            raise serializers.ValidationError(errors)
        return attrs


class CleaningMethodSerializer(VersionedSerializer):
    class Meta:
        model = CleaningMethod
        fields = [
            "id",
            "name",
            "cleaning_cost_won",
            "outage_days",
            "recovery_ratio",
            "is_placeholder",
            "is_active",
            "note",
            "version",
            "updated_at",
        ]
        read_only_fields = ["id", "version", "updated_at"]
        extra_kwargs = {
            "cleaning_cost_won": {"min_value": 0},
            "outage_days": {"min_value": 0},
            "recovery_ratio": {"min_value": 0.0001, "max_value": 1},
        }


class SmpPriceSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(
        source="created_by.full_name", read_only=True, default=""
    )

    class Meta:
        model = SmpPrice
        fields = [
            "id",
            "value_won_per_kwh",
            "as_of_date",
            "period_label",
            "source",
            "is_estimate",
            "created_by_name",
            "created_at",
        ]
        read_only_fields = ["id", "created_by_name", "created_at"]
        extra_kwargs = {"value_won_per_kwh": {"min_value": 0.0001, "max_value": 1000}}


class CalcParameterSetSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(
        source="created_by.full_name", read_only=True, default=""
    )

    class Meta:
        model = CalcParameterSet
        fields = [
            "id",
            "version_label",
            "params",
            "is_active",
            "is_seed",
            "note",
            "created_by_name",
            "created_at",
        ]
        read_only_fields = fields


class ParamsInputSerializer(serializers.Serializer):
    params = serializers.JSONField()
    note = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")

    def validate_params(self, value):
        try:
            return validate_params(value)
        except ParamValidationError as exc:
            raise serializers.ValidationError(exc.details) from exc
