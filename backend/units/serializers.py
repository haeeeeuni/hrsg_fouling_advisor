"""호기·매핑 직렬화 (specs/02, specs/15 §4)."""

from rest_framework import serializers

from units.models import ColumnMapping, ColumnMappingVersion, Unit
from units.standard_fields import (
    ALL_FIELD_KEYS,
    ALWAYS_REQUIRED,
    DP_ALTERNATIVES,
    FLOW_ALTERNATIVES,
    STANDARD_FIELDS,
)


class StandardFieldSerializer(serializers.Serializer):
    """GET /api/standard-fields/ — 필수/선택/대체 규칙 포함."""

    key = serializers.CharField()
    label = serializers.CharField()
    dtype = serializers.CharField()
    unit_label = serializers.CharField()
    description = serializers.CharField()
    substitutes = serializers.ListField(child=serializers.CharField())
    requirement = serializers.SerializerMethodField()

    def get_requirement(self, obj) -> str:
        if obj.key in ALWAYS_REQUIRED:
            return "REQUIRED"
        if obj.key in FLOW_ALTERNATIVES or obj.key in DP_ALTERNATIVES:
            return "ALTERNATIVE"
        return "OPTIONAL"

    @staticmethod
    def all_fields() -> list:
        return list(STANDARD_FIELDS)


class UnitSerializer(serializers.ModelSerializer):
    is_mapping_complete = serializers.BooleanField(read_only=True)
    mapping_problems = serializers.SerializerMethodField()

    class Meta:
        model = Unit
        fields = [
            "id",
            "code",
            "name",
            "plant_name",
            "gt_model",
            "rated_power_mw",
            "rated_st_power_mw",
            "min_load_mw",
            "sampling_interval_min",
            "dp_source",
            "flow_source",
            "is_active",
            "is_mapping_complete",
            "mapping_problems",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_mapping_problems(self, obj) -> list:
        return obj.mapping_problems()

    def validate(self, attrs: dict) -> dict:
        rated = attrs.get("rated_power_mw", getattr(self.instance, "rated_power_mw", None))
        min_load = attrs.get("min_load_mw", getattr(self.instance, "min_load_mw", None))
        if rated is not None and rated <= 0:
            raise serializers.ValidationError(
                {"rated_power_mw": ["정격 출력은 0보다 커야 합니다."]}
            )
        if rated is not None and min_load is not None and min_load >= rated:
            raise serializers.ValidationError(
                {"min_load_mw": ["최소 안정 부하는 정격 출력보다 작아야 합니다."]}
            )
        return attrs


class ColumnMappingSerializer(serializers.ModelSerializer):
    class Meta:
        model = ColumnMapping
        fields = [
            "standard_field",
            "source_column",
            "unit_label",
            "scale_factor",
            "offset",
            "bool_rule",
            "bool_threshold",
        ]

    def validate_standard_field(self, value: str) -> str:
        if value not in ALL_FIELD_KEYS:
            raise serializers.ValidationError(f"알 수 없는 표준 항목입니다: {value}")
        return value

    def validate(self, attrs: dict) -> dict:
        if attrs.get("bool_rule") == "THRESHOLD" and attrs.get("bool_threshold") is None:
            raise serializers.ValidationError(
                {"bool_threshold": ["THRESHOLD 규칙에는 임계값이 필요합니다."]}
            )
        return attrs


class ColumnMappingBulkSerializer(serializers.Serializer):
    """PUT /api/units/{id}/column-mappings/ — 매핑 일괄 저장."""

    mappings = ColumnMappingSerializer(many=True)

    def validate_mappings(self, value: list) -> list:
        seen = set()
        for row in value:
            field = row["standard_field"]
            if field in seen:
                raise serializers.ValidationError(f"표준 항목이 중복되었습니다: {field}")
            seen.add(field)
        return value


class ColumnMappingVersionSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source="created_by.full_name", read_only=True)

    class Meta:
        model = ColumnMappingVersion
        fields = ["id", "version", "snapshot", "created_by_name", "created_at"]


class MappingPreviewRequestSerializer(serializers.Serializer):
    """POST /api/units/{id}/column-mappings/preview/ — 샘플 파일 + 매핑 미리보기."""

    file = serializers.FileField()
    # 저장 전 매핑으로 미리보고 싶을 수 있으므로 선택 입력으로 받는다.
    mappings = ColumnMappingSerializer(many=True, required=False)
