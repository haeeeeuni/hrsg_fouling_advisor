from rest_framework import serializers

from maintenance.models import CleaningEvent, FoulingKeyword, MaintenanceRecord


class CleaningEventSerializer(serializers.ModelSerializer):
    unit_code = serializers.CharField(source="unit.code", read_only=True)
    method_label = serializers.CharField(source="get_method_display", read_only=True)
    created_by_name = serializers.CharField(source="created_by.full_name", read_only=True)

    class Meta:
        model = CleaningEvent
        fields = [
            "id",
            "unit",
            "unit_code",
            "cleaned_at",
            "cleaned_end_at",
            "method",
            "method_label",
            "method_detail",
            "cost",
            "outage_days",
            "source",
            "note",
            "created_by_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "source", "created_by_name", "created_at", "updated_at"]

    def validate(self, attrs: dict) -> dict:
        start = attrs.get("cleaned_at", getattr(self.instance, "cleaned_at", None))
        end = attrs.get("cleaned_end_at", getattr(self.instance, "cleaned_end_at", None))
        if start and end and end < start:
            raise serializers.ValidationError(
                {"cleaned_end_at": ["종료 일자는 세정 일자보다 빠를 수 없습니다."]}
            )
        for field_name in ("cost", "outage_days"):
            value = attrs.get(field_name)
            if value is not None and value < 0:
                raise serializers.ValidationError({field_name: ["음수는 입력할 수 없습니다."]})
        return attrs


class FoulingKeywordSerializer(serializers.ModelSerializer):
    category_label = serializers.CharField(source="get_category_display", read_only=True)

    class Meta:
        model = FoulingKeyword
        fields = [
            "id",
            "keyword",
            "category",
            "category_label",
            "weight",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["id", "category_label", "created_at"]

    def validate_weight(self, value: float) -> float:
        if value < 0:
            raise serializers.ValidationError("가중치는 음수일 수 없습니다.")
        return value


class MaintenanceRecordSerializer(serializers.ModelSerializer):
    unit_code = serializers.CharField(source="unit.code", read_only=True)

    class Meta:
        model = MaintenanceRecord
        fields = [
            "id",
            "unit",
            "unit_code",
            "work_date",
            "work_type",
            "title",
            "description",
            "cost",
            "duration_days",
            "worker",
            "is_fouling_related",
            "matched_keywords",
            "match_score",
            "match_category",
            "review_status",
            "cleaning_event",
            "created_at",
        ]
        read_only_fields = [f for f in fields if f not in {"work_type", "description"}]


class AcceptRecordSerializer(serializers.Serializer):
    """POST /maintenance-records/{id}/accept/ — 세정 이벤트로 등록."""

    method = serializers.CharField(required=False, allow_blank=True)
    cost = serializers.IntegerField(required=False, allow_null=True)
    outage_days = serializers.FloatField(required=False, allow_null=True)
    cleaned_end_at = serializers.DateTimeField(required=False, allow_null=True)


class MaintenanceUploadSerializer(serializers.Serializer):
    unit_id = serializers.IntegerField()
    file = serializers.FileField()
    sheet = serializers.CharField(required=False, allow_blank=True)
    mapping = serializers.DictField(required=False)
