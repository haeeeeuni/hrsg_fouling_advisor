"""업로드 직렬화 (specs/15 §5)."""

from rest_framework import serializers

from ingestion.models import DuplicatePolicy, UploadBatch


class UploadBatchSerializer(serializers.ModelSerializer):
    unit_code = serializers.CharField(source="unit.code", read_only=True)
    uploaded_by_name = serializers.CharField(source="uploaded_by.full_name", read_only=True)

    class Meta:
        model = UploadBatch
        fields = [
            "id",
            "unit",
            "unit_code",
            "kind",
            "uploaded_by_name",
            "uploaded_at",
            "original_filename",
            "file_size_bytes",
            "checksum",
            "status",
            "row_total",
            "row_loaded",
            "row_skipped",
            "row_duplicated",
            "period_start",
            "period_end",
            "validation_report",
            "error_message",
        ]
        read_only_fields = fields


class UploadBatchListSerializer(UploadBatchSerializer):
    """목록에서는 검증 리포트 전문을 빼 응답 크기를 줄인다."""

    class Meta(UploadBatchSerializer.Meta):
        fields = [f for f in UploadBatchSerializer.Meta.fields if f != "validation_report"]
        read_only_fields = fields


class OperationUploadSerializer(serializers.Serializer):
    unit_id = serializers.IntegerField()
    file = serializers.FileField()
    # 같은 파일(checksum 동일)을 다시 올릴 때 사용자가 확인했는지 여부 (specs/03 §5)
    confirm_duplicate_file = serializers.BooleanField(required=False, default=False)


class CommitSerializer(serializers.Serializer):
    duplicate_policy = serializers.ChoiceField(
        choices=DuplicatePolicy.choices, required=False, default=DuplicatePolicy.SKIP
    )
