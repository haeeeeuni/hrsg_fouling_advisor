"""분석 직렬화 (specs/15 §6)."""

from rest_framework import serializers

from analysis.models import (
    AnalysisRun,
    BenefitResult,
    ComparisonReport,
    FoulingIndexPoint,
    ModelVersion,
    TrendForecast,
)
from analysis.pipeline import BENEFIT_KEYS


def validate_benefit_params(params: dict) -> dict:
    """편익 파라미터 검증 (specs/09 §8 — 음수 입력은 400)."""
    unknown = set(params) - set(BENEFIT_KEYS)
    if unknown:
        raise serializers.ValidationError(
            {"benefit_params_override": [f"알 수 없는 파라미터입니다: {sorted(unknown)}"]}
        )
    negative = [
        key for key, value in params.items() if isinstance(value, (int, float)) and value < 0
    ]
    if negative:
        raise serializers.ValidationError(
            {"benefit_params_override": [f"음수를 입력할 수 없습니다: {sorted(negative)}"]}
        )
    return params


class BenefitParamsSerializer(serializers.Serializer):
    """POST /api/analysis-runs/{id}/recalculate-benefit/ — 편익 파라미터만 변경."""

    benefit_params_override = serializers.DictField(required=False, default=dict)

    def validate_benefit_params_override(self, value: dict) -> dict:
        return validate_benefit_params(value)


class AnalysisRunRequestSerializer(serializers.Serializer):
    unit_id = serializers.IntegerField()
    period_start = serializers.DateTimeField()
    period_end = serializers.DateTimeField()
    settings_override = serializers.DictField(required=False, default=dict)
    # 이 분석에만 적용되는 임시값. 관리자 기본값은 바뀌지 않는다 (specs/09 §3.2).
    benefit_params_override = serializers.DictField(required=False, default=dict)
    force_retrain = serializers.BooleanField(required=False, default=False)

    def validate_benefit_params_override(self, value: dict) -> dict:
        return validate_benefit_params(value)

    def validate(self, attrs: dict) -> dict:
        if attrs["period_end"] <= attrs["period_start"]:
            raise serializers.ValidationError(
                {"period_end": ["종료일은 시작일보다 뒤여야 합니다."]}
            )
        return attrs


class TrendForecastSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrendForecast
        fields = [
            "model_type",
            "fit_start",
            "fit_end",
            "coefficients",
            "slope_per_day",
            "r2",
            "mae",
            "p_value",
            "threshold_used",
            "current_fi",
            "eta_date",
            "eta_days",
            "eta_lower_date",
            "eta_upper_date",
            "caution_eta_date",
            "warning_eta_date",
            "exceeded_days",
            "weekly_increase",
            "days_since_cleaning",
            "uncertain",
            "status",
            "message",
        ]


class BenefitResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = BenefitResult
        fields = [
            "params_snapshot",
            "delta_dp_kpa",
            "delta_stack_c",
            "power_loss_gt_mw",
            "power_loss_st_mw",
            "power_loss_total_mw",
            "daily_loss_cost",
            "daily_fuel_loss",
            "cleaning_cost",
            "outage_loss",
            "total_cleaning_cost",
            "gross_benefit",
            "gross_benefit_simple",
            "net_benefit",
            "payback_days",
            "roi_pct",
            "recommended_offset_days",
            "recommended_cleaning_date",
            "recommended_net_benefit",
            "scenarios",
            "sensitivity",
            "warnings",
            "updated_at",
        ]


class ModelVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ModelVersion
        fields = [
            "id",
            "target",
            "algorithm",
            "version",
            "baseline_start",
            "baseline_end",
            "feature_list",
            "hyperparams",
            "metrics",
            "residual_mean",
            "residual_std",
            "training_rows",
            "is_active",
            "trained_at",
        ]


class AnalysisRunSerializer(serializers.ModelSerializer):
    unit_code = serializers.CharField(source="unit.code", read_only=True)
    unit_name = serializers.CharField(source="unit.name", read_only=True)
    executed_by_name = serializers.CharField(source="executed_by.full_name", read_only=True)
    model_dp = ModelVersionSerializer(source="model_version_dp", read_only=True)
    model_st = ModelVersionSerializer(source="model_version_st", read_only=True)
    trend = TrendForecastSerializer(read_only=True)
    benefit = BenefitResultSerializer(read_only=True)

    class Meta:
        model = AnalysisRun
        fields = [
            "id",
            "unit",
            "unit_code",
            "unit_name",
            "executed_by_name",
            "executed_at",
            "period_start",
            "period_end",
            "status",
            "failed_stage",
            "error_message",
            "duration_sec",
            "is_auto",
            "settings_snapshot",
            "data_stats",
            "warnings",
            "result_fi",
            "result_grade",
            "result_confidence",
            "result_dday",
            "result_net_benefit",
            "model_dp",
            "model_st",
            "trend",
            "benefit",
        ]
        read_only_fields = fields


class AnalysisRunListSerializer(serializers.ModelSerializer):
    """목록은 비정규화 요약 필드만 써서 조인을 줄인다 (specs/18 §1)."""

    unit_code = serializers.CharField(source="unit.code", read_only=True)
    executed_by_name = serializers.CharField(source="executed_by.full_name", read_only=True)

    class Meta:
        model = AnalysisRun
        fields = [
            "id",
            "unit",
            "unit_code",
            "executed_by_name",
            "executed_at",
            "period_start",
            "period_end",
            "status",
            "duration_sec",
            "is_auto",
            "result_fi",
            "result_grade",
            "result_confidence",
            "result_dday",
            "result_net_benefit",
        ]
        read_only_fields = fields


class FoulingIndexPointSerializer(serializers.ModelSerializer):
    class Meta:
        model = FoulingIndexPoint
        fields = [
            "date",
            "cluster_key",
            "fi_value",
            "score_dp",
            "score_st",
            "residual_dp",
            "residual_st",
            "expected_dp",
            "expected_st",
            "measured_dp",
            "measured_st",
            "sample_count",
            "confidence",
            "grade",
        ]


class ComparisonRequestSerializer(serializers.Serializer):
    """POST /api/comparisons/ (specs/15 §8)."""

    cleaning_event_id = serializers.IntegerField()
    window_days = serializers.IntegerField(required=False, default=30, min_value=1, max_value=365)
    before_offset_days = serializers.IntegerField(required=False, default=0, min_value=0)
    after_offset_days = serializers.IntegerField(required=False, default=1, min_value=0)


class ComparisonReportSerializer(serializers.ModelSerializer):
    unit_code = serializers.CharField(source="unit.code", read_only=True)
    cleaned_at = serializers.DateTimeField(source="cleaning_event.cleaned_at", read_only=True)
    method_label = serializers.CharField(source="cleaning_event.get_method_display", read_only=True)
    created_by_name = serializers.CharField(source="created_by.full_name", read_only=True)
    is_comparable = serializers.SerializerMethodField()

    class Meta:
        model = ComparisonReport
        fields = [
            "id",
            "unit",
            "unit_code",
            "cleaning_event",
            "cleaned_at",
            "method_label",
            "created_by_name",
            "created_at",
            "window_days",
            "before_start",
            "before_end",
            "after_start",
            "after_end",
            "metrics",
            "cluster_metrics",
            "p_values",
            "common_clusters",
            "recovery_ratio",
            "warnings",
            "is_comparable",
        ]
        read_only_fields = fields

    def get_is_comparable(self, obj) -> bool:
        return bool(obj.common_clusters)
