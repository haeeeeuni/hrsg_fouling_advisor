"""체크리스트 직렬화 (specs/07, specs/10 §5·§6)."""

from __future__ import annotations

from rest_framework import serializers

from checklist import rules
from checklist.models import (
    CATEGORY_EN,
    CATEGORY_ORDER,
    ChecklistTemplateItem,
    DataRequest,
    DataRequestItem,
    ItemState,
)
from checklist.services import item_dicts, new_template_items
from common.serializers import VersionedSerializer


class TemplateItemSerializer(VersionedSerializer):
    """관리자용 템플릿 항목 (specs/07 CHK-2·6)."""

    category_label = serializers.CharField(source="get_category_display", read_only=True)

    class Meta:
        model = ChecklistTemplateItem
        fields = [
            "id",
            "category",
            "category_label",
            "name_ko",
            "name_en",
            "unit",
            "is_required",
            "why_needed_ko",
            "why_needed_en",
            "is_calculator_input",
            "source",
            "order",
            "is_active",
            "is_placeholder",
            "version",
            "updated_at",
        ]
        read_only_fields = ["id", "category_label", "version", "updated_at"]
        # (분류, 이름) 중복은 DB 제약이 막는다. DRF 기본 문구 대신 아래에서 한국어로 알린다.
        validators: list = []

    def validate(self, attrs: dict) -> dict:
        attrs = super().validate(attrs)
        category = attrs.get("category", getattr(self.instance, "category", None))
        name = attrs.get("name_ko", getattr(self.instance, "name_ko", None))
        clash = ChecklistTemplateItem.objects.filter(category=category, name_ko=name)
        if self.instance is not None:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise serializers.ValidationError(
                {"name_ko": ["같은 분류에 같은 이름의 항목이 이미 있습니다."]}
            )
        return attrs


class RequestItemSerializer(serializers.ModelSerializer):
    category_label = serializers.CharField(source="get_category_display", read_only=True)
    category_label_en = serializers.SerializerMethodField()

    class Meta:
        model = DataRequestItem
        fields = [
            "id",
            "category",
            "category_label",
            "category_label_en",
            "name_ko",
            "name_en",
            "unit",
            "is_required",
            "why_needed_ko",
            "why_needed_en",
            "is_calculator_input",
            "order",
            "state",
            "received_at",
            "memo",
        ]
        read_only_fields = fields

    def get_category_label_en(self, obj) -> str:
        return CATEGORY_EN.get(obj.category, obj.category)


class ItemUpdateSerializer(serializers.Serializer):
    state = serializers.ChoiceField(choices=ItemState.choices, required=False)
    memo = serializers.CharField(max_length=500, required=False, allow_blank=True)


class RequestSerializer(serializers.ModelSerializer):
    """목록·생성·수정. 진행률은 항상 서버가 계산한다(필수 기준, 해당 없음 제외)."""

    progress = serializers.SerializerMethodField()
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = DataRequest
        fields = [
            "id",
            "title",
            "memo",
            "due_date",
            "status",
            "status_label",
            "progress",
            "template_snapshot_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "status_label",
            "progress",
            "template_snapshot_at",
            "created_at",
            "updated_at",
        ]

    def get_progress(self, obj) -> dict:
        return rules.progress(item_dicts(obj))

    def validate_title(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError("요청 건 이름을 입력해 주세요.")
        return value

    def validate_status(self, value: str) -> str:
        # 완료·진행 중은 체크 상태로 자동 결정된다.
        # 사용자가 직접 고르는 것은 보관(과 보관 해제)뿐이다.
        if self.instance is None:
            raise serializers.ValidationError("새 요청 건의 상태는 정할 수 없습니다.")
        return value


class RequestDetailSerializer(RequestSerializer):
    items = RequestItemSerializer(many=True, read_only=True)
    progress_by_category = serializers.SerializerMethodField()
    new_template_items = serializers.SerializerMethodField()

    class Meta(RequestSerializer.Meta):
        fields = [
            *RequestSerializer.Meta.fields,
            "items",
            "progress_by_category",
            "new_template_items",
        ]

    def get_progress_by_category(self, obj) -> list:
        return rules.progress_by_category(item_dicts(obj), CATEGORY_ORDER)

    def get_new_template_items(self, obj) -> int:
        return new_template_items(obj).count()
