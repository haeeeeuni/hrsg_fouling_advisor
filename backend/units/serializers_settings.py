"""설정값 직렬화 (specs/15 §10)."""

from rest_framework import serializers

from units.models import Setting, UnitSetting
from units.setting_defaults import SETTING_DEF_BY_KEY, cast_value


class SettingSerializer(serializers.ModelSerializer):
    """현재값은 타입 캐스팅해서 내보낸다(문자열 저장은 구현 세부)."""

    value = serializers.SerializerMethodField()
    default = serializers.SerializerMethodField()
    is_modified = serializers.SerializerMethodField()

    class Meta:
        model = Setting
        fields = [
            "key",
            "value",
            "default",
            "value_type",
            "category",
            "label",
            "description",
            "unit_label",
            "min_value",
            "max_value",
            "is_modified",
            "updated_at",
        ]
        read_only_fields = fields

    def get_value(self, obj):
        return cast_value(obj.value, obj.value_type)

    def get_default(self, obj):
        return cast_value(obj.default_value, obj.value_type)

    def get_is_modified(self, obj) -> bool:
        return obj.value != obj.default_value


class UnitSettingSerializer(serializers.ModelSerializer):
    """호기별 오버라이드. 상속값을 함께 보여준다 (specs/13 §4.3)."""

    value = serializers.SerializerMethodField()
    label = serializers.SerializerMethodField()

    class Meta:
        model = UnitSetting
        fields = ["key", "value", "label", "updated_at"]
        read_only_fields = fields

    def get_value(self, obj):
        definition = SETTING_DEF_BY_KEY.get(obj.key)
        return cast_value(obj.value, definition.value_type) if definition else obj.value

    def get_label(self, obj) -> str:
        definition = SETTING_DEF_BY_KEY.get(obj.key)
        return definition.label if definition else obj.key


class SettingsPatchSerializer(serializers.Serializer):
    """PATCH /api/settings/ — {"fouling_threshold": 55, "weight_dp": 0.7}"""

    def to_internal_value(self, data):
        if not isinstance(data, dict) or not data:
            raise serializers.ValidationError("변경할 설정값을 하나 이상 보내야 합니다.")
        return dict(data)


class RestoreDefaultsSerializer(serializers.Serializer):
    category = serializers.CharField(required=False, allow_blank=True)
    keys = serializers.ListField(child=serializers.CharField(), required=False)

    def validate(self, attrs: dict) -> dict:
        if not attrs.get("category") and not attrs.get("keys"):
            raise serializers.ValidationError("category 또는 keys 중 하나는 필요합니다.")
        return attrs
