from rest_framework import serializers

from reports.models import ReportExport, ReportFormat


class ExportRequestSerializer(serializers.Serializer):
    """POST /analysis-runs/{id}/export/ (specs/15 §9)."""

    format = serializers.ChoiceField(choices=[c.lower() for c in ReportFormat.values])

    def validate_format(self, value: str) -> str:
        return value.upper()


class ReportExportSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source="created_by.full_name", read_only=True)
    unit_code = serializers.SerializerMethodField()

    class Meta:
        model = ReportExport
        fields = [
            "id",
            "analysis_run",
            "comparison_report",
            "unit_code",
            "format",
            "file_name",
            "file_size_bytes",
            "created_by_name",
            "created_at",
            "expires_at",
        ]
        read_only_fields = fields

    def get_unit_code(self, obj) -> str:
        if obj.analysis_run_id:
            return obj.analysis_run.unit.code
        if obj.comparison_report_id:
            return obj.comparison_report.unit.code
        return ""
