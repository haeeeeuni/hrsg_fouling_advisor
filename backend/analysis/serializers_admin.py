"""모델 관리 직렬화 (specs/15 §11)."""

from rest_framework import serializers

from analysis.models import (
    AutoRecalcConfig,
    AutoRecalcTrigger,
    BacktestResult,
    CleanBaselinePeriod,
    ClusterDefinition,
    ModelTarget,
    Notification,
)


class TrainRequestSerializer(serializers.Serializer):
    """POST /api/model-versions/train/"""

    unit_id = serializers.IntegerField()
    targets = serializers.ListField(
        child=serializers.ChoiceField(choices=ModelTarget.values),
        allow_empty=False,
        default=list(ModelTarget.values),
    )
    algorithm = serializers.ChoiceField(choices=["GBR", "RIDGE"], required=False, allow_blank=True)
    baseline_period_ids = serializers.ListField(child=serializers.IntegerField(), required=False)


class CleanBaselinePeriodSerializer(serializers.ModelSerializer):
    unit_code = serializers.CharField(source="unit.code", read_only=True)
    created_by_name = serializers.CharField(source="created_by.full_name", read_only=True)

    class Meta:
        model = CleanBaselinePeriod
        fields = [
            "id",
            "unit",
            "unit_code",
            "start_at",
            "end_at",
            "source",
            "cleaning_event",
            "is_active",
            "note",
            "created_by_name",
            "created_at",
        ]
        read_only_fields = ["id", "unit_code", "created_by_name", "created_at"]

    def validate(self, attrs: dict) -> dict:
        start = attrs.get("start_at", getattr(self.instance, "start_at", None))
        end = attrs.get("end_at", getattr(self.instance, "end_at", None))
        if start and end and end <= start:
            raise serializers.ValidationError(
                {"end_at": ["종료 일시는 시작 일시보다 뒤여야 합니다."]}
            )
        return attrs


class ClusterDefinitionSerializer(serializers.ModelSerializer):
    unit_code = serializers.CharField(source="unit.code", read_only=True)

    class Meta:
        model = ClusterDefinition
        fields = [
            "id",
            "unit",
            "unit_code",
            "method",
            "version",
            "params",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["id", "unit_code", "version", "created_at"]


# --- Phase 7: 옵션 기능 (specs/19) ---


class AutoRecalcConfigSerializer(serializers.ModelSerializer):
    unit_code = serializers.CharField(source="unit.code", read_only=True)
    updated_by_name = serializers.CharField(source="updated_by.full_name", read_only=True)

    class Meta:
        model = AutoRecalcConfig
        fields = [
            "id",
            "unit",
            "unit_code",
            "enabled",
            "trigger",
            "schedule_cron",
            "base_analysis_run",
            "period_mode",
            "rolling_months",
            "retrain_model",
            "notify_on_grade_change",
            "updated_by_name",
            "updated_at",
        ]
        read_only_fields = ["id", "unit", "unit_code", "updated_by_name", "updated_at"]

    def validate(self, attrs: dict) -> dict:
        trigger = attrs.get("trigger", getattr(self.instance, "trigger", None))
        cron = attrs.get("schedule_cron", getattr(self.instance, "schedule_cron", ""))
        if trigger == AutoRecalcTrigger.SCHEDULE and not cron:
            raise serializers.ValidationError(
                {"schedule_cron": ["스케줄 실행은 cron 식을 입력해야 합니다."]}
            )
        return attrs


class BacktestResultSerializer(serializers.ModelSerializer):
    unit_code = serializers.CharField(source="unit.code", read_only=True)
    created_by_name = serializers.CharField(source="created_by.full_name", read_only=True)

    class Meta:
        model = BacktestResult
        fields = [
            "id",
            "unit",
            "unit_code",
            "lookahead_days",
            "cases",
            "summary",
            "coefficient_suggestion",
            "warnings",
            "created_by_name",
            "created_at",
        ]
        read_only_fields = fields


class BacktestRequestSerializer(serializers.Serializer):
    """POST /api/backtests/"""

    unit_id = serializers.IntegerField()
    lookahead_days = serializers.IntegerField(required=False, min_value=1, max_value=365)


class NotificationSerializer(serializers.ModelSerializer):
    unit_code = serializers.CharField(source="unit.code", read_only=True)

    class Meta:
        model = Notification
        fields = [
            "id",
            "unit",
            "unit_code",
            "analysis_run",
            "level",
            "title",
            "message",
            "payload",
            "is_read",
            "created_at",
        ]
        read_only_fields = fields
