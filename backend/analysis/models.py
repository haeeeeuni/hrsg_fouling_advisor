"""분석 도메인 모델 (specs/14 §4.4).

모든 분석 결과는 **실행 컨텍스트 스냅샷**(설정값·모델 버전·매핑 버전)을 함께 보관해
재현 가능해야 한다(AGENTS.md §1.3, AC-14-3).
"""

from django.conf import settings as django_settings
from django.db import models

from maintenance.models import CleaningEvent
from units.models import ColumnMappingVersion, Unit


class ClusterMethod(models.TextChoices):
    RULE = "RULE", "규칙 기반"
    KMEANS = "KMEANS", "데이터 기반"


class ClusterDefinition(models.Model):
    unit = models.ForeignKey(Unit, on_delete=models.CASCADE, related_name="cluster_definitions")
    method = models.CharField("방식", max_length=20, choices=ClusterMethod.choices)
    version = models.PositiveIntegerField("버전", default=1)
    params = models.JSONField("파라미터", default=dict)
    is_active = models.BooleanField("활성", default=True)
    created_by = models.ForeignKey(
        django_settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "군집 정의"
        verbose_name_plural = "군집 정의"
        unique_together = [("unit", "version")]
        ordering = ["-version"]


class BaselineSource(models.TextChoices):
    MANUAL = "MANUAL", "관리자 지정"
    AUTO_FROM_CLEANING = "AUTO_FROM_CLEANING", "세정 이력 기반"
    AUTO_FIRST_DATA = "AUTO_FIRST_DATA", "데이터 초기 구간"


class CleanBaselinePeriod(models.Model):
    """청정 기준 기간 (specs/06 §2). 기대값 모델의 학습 구간이다."""

    unit = models.ForeignKey(Unit, on_delete=models.CASCADE, related_name="baseline_periods")
    start_at = models.DateTimeField("시작")
    end_at = models.DateTimeField("종료")
    source = models.CharField(
        "결정 경로", max_length=30, choices=BaselineSource.choices, default=BaselineSource.MANUAL
    )
    cleaning_event = models.ForeignKey(
        CleaningEvent, on_delete=models.SET_NULL, null=True, blank=True
    )
    is_active = models.BooleanField("활성", default=True)
    note = models.TextField("비고", blank=True)
    created_by = models.ForeignKey(
        django_settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "청정 기준 기간"
        verbose_name_plural = "청정 기준 기간"
        ordering = ["-start_at"]

    def __str__(self) -> str:
        return f"{self.unit.code} {self.start_at:%Y-%m-%d}~{self.end_at:%Y-%m-%d}"


class ModelTarget(models.TextChoices):
    DP = "DP", "차압"
    STACK_TEMP = "STACK_TEMP", "스택온도"


class ModelVersion(models.Model):
    """기대값 모델 버전 (specs/06 §7).

    residual_mean / residual_std 는 FI 정규화(SIGMA)의 분모가 되므로 반드시 함께 보관한다.
    """

    unit = models.ForeignKey(Unit, on_delete=models.CASCADE, related_name="model_versions")
    target = models.CharField("타깃", max_length=20, choices=ModelTarget.choices)
    algorithm = models.CharField("알고리즘", max_length=20)
    version = models.PositiveIntegerField("버전")

    baseline_start = models.DateTimeField("학습 기간 시작", null=True, blank=True)
    baseline_end = models.DateTimeField("학습 기간 종료", null=True, blank=True)
    feature_list = models.JSONField("피처 목록", default=list)
    hyperparams = models.JSONField("하이퍼파라미터", default=dict)
    metrics = models.JSONField("지표", default=dict)

    residual_mean = models.FloatField("잔차 평균", default=0.0)
    residual_std = models.FloatField("잔차 표준편차", default=0.0)
    training_rows = models.IntegerField("학습 표본 수", default=0)
    artifact_path = models.CharField("아티팩트 경로", max_length=500, blank=True)

    trained_by = models.ForeignKey(
        django_settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    trained_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField("활성", default=False)
    notes = models.TextField("비고", blank=True)

    class Meta:
        verbose_name = "모델 버전"
        verbose_name_plural = "모델 버전"
        unique_together = [("unit", "target", "version")]
        ordering = ["-trained_at"]

    def __str__(self) -> str:
        return f"{self.unit.code} {self.target} v{self.version}"


class RunStatus(models.TextChoices):
    RUNNING = "RUNNING", "실행 중"
    SUCCESS = "SUCCESS", "성공"
    FAILED = "FAILED", "실패"
    CANCELED = "CANCELED", "취소"


class AnalysisRun(models.Model):
    """분석 실행 이력 (specs/13 §6).

    이 레코드 하나만 보고도 결과를 동일하게 재현할 수 있어야 한다(AC-14-3).
    """

    unit = models.ForeignKey(Unit, on_delete=models.CASCADE, related_name="analysis_runs")
    executed_by = models.ForeignKey(
        django_settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    executed_at = models.DateTimeField("실행 일시", auto_now_add=True)

    period_start = models.DateTimeField("데이터 시작")
    period_end = models.DateTimeField("데이터 종료")

    status = models.CharField(
        "상태", max_length=20, choices=RunStatus.choices, default=RunStatus.RUNNING
    )
    failed_stage = models.CharField("실패 단계", max_length=50, blank=True)
    error_message = models.TextField("오류 메시지", blank=True)
    duration_sec = models.FloatField("소요 시간", null=True, blank=True)
    is_auto = models.BooleanField("자동 실행", default=False)

    # --- 재현성 스냅샷 ---
    settings_snapshot = models.JSONField("설정값 스냅샷", default=dict)
    benefit_params_snapshot = models.JSONField("편익 파라미터 스냅샷", default=dict)
    model_version_dp = models.ForeignKey(
        ModelVersion, on_delete=models.SET_NULL, null=True, blank=True, related_name="runs_as_dp"
    )
    model_version_st = models.ForeignKey(
        ModelVersion, on_delete=models.SET_NULL, null=True, blank=True, related_name="runs_as_st"
    )
    cluster_definition = models.ForeignKey(
        ClusterDefinition, on_delete=models.SET_NULL, null=True, blank=True
    )
    column_mapping_version = models.ForeignKey(
        ColumnMappingVersion, on_delete=models.SET_NULL, null=True, blank=True
    )

    data_stats = models.JSONField("데이터 통계", default=dict)
    warnings = models.JSONField("경고", default=list)

    # --- 목록 조회용 비정규화 요약 (specs/18 §1) ---
    result_fi = models.FloatField("현재 FI", null=True, blank=True)
    result_grade = models.CharField("등급", max_length=20, blank=True)
    result_confidence = models.CharField("신뢰도", max_length=20, blank=True)
    result_dday = models.IntegerField("D-day", null=True, blank=True)
    result_net_benefit = models.BigIntegerField("순편익", null=True, blank=True)

    class Meta:
        verbose_name = "분석 실행"
        verbose_name_plural = "분석 실행"
        ordering = ["-executed_at"]
        indexes = [
            models.Index(fields=["unit", "-executed_at"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self) -> str:
        return f"{self.unit.code} {self.executed_at:%Y-%m-%d %H:%M} ({self.status})"


class CleanedPoint(models.Model):
    """정제·구간분류·기대값까지 담은 상세 시계열.

    대용량이므로 보존 정책 적용 대상이다(specs/14 §5 — 최근 N회 분석분만 보관).
    """

    analysis_run = models.ForeignKey(
        AnalysisRun, on_delete=models.CASCADE, related_name="cleaned_points", db_index=True
    )
    timestamp = models.DateTimeField()

    gt_power_mw = models.FloatField(null=True, blank=True)
    ambient_temp_c = models.FloatField(null=True, blank=True)
    gt_exhaust_temp_c = models.FloatField(null=True, blank=True)
    exhaust_flow = models.FloatField(null=True, blank=True)
    measured_dp = models.FloatField(null=True, blank=True)
    measured_st = models.FloatField(null=True, blank=True)
    duct_burner_on = models.BooleanField(null=True, blank=True)

    segment_state = models.CharField(max_length=20, blank=True)
    segment_id = models.IntegerField(null=True, blank=True)
    cluster_key = models.CharField(max_length=20, blank=True)
    is_valid = models.BooleanField(default=False)
    exclusion_reason = models.CharField(max_length=30, blank=True)

    expected_dp = models.FloatField(null=True, blank=True)
    expected_stack_temp = models.FloatField(null=True, blank=True)
    residual_dp = models.FloatField(null=True, blank=True)
    residual_stack_temp = models.FloatField(null=True, blank=True)

    class Meta:
        verbose_name = "정제 포인트"
        verbose_name_plural = "정제 포인트"
        indexes = [models.Index(fields=["analysis_run", "timestamp"])]


class FoulingIndexPoint(models.Model):
    """FI 시계열 (specs/07 §6).

    원시 잔차와 기대/실측값을 함께 저장해 **역추적과 검증이 가능해야 한다.**
    """

    analysis_run = models.ForeignKey(
        AnalysisRun, on_delete=models.CASCADE, related_name="fouling_points", db_index=True
    )
    date = models.DateField()
    cluster_key = models.CharField(max_length=20, blank=True, default="")  # "" = 전체 집계

    fi_value = models.FloatField(null=True, blank=True)
    score_dp = models.FloatField(null=True, blank=True)
    score_st = models.FloatField(null=True, blank=True)
    residual_dp = models.FloatField(null=True, blank=True)
    residual_st = models.FloatField(null=True, blank=True)
    expected_dp = models.FloatField(null=True, blank=True)
    expected_st = models.FloatField(null=True, blank=True)
    measured_dp = models.FloatField(null=True, blank=True)
    measured_st = models.FloatField(null=True, blank=True)

    sample_count = models.IntegerField(default=0)
    confidence = models.CharField(max_length=10, blank=True)
    grade = models.CharField(max_length=10, blank=True)

    class Meta:
        verbose_name = "오염도 지수"
        verbose_name_plural = "오염도 지수"
        ordering = ["date"]
        indexes = [
            models.Index(fields=["analysis_run", "date"]),
            models.Index(fields=["analysis_run", "cluster_key"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(fi_value__isnull=True)
                | models.Q(fi_value__gte=0, fi_value__lte=100),
                name="fi_value_between_0_and_100",
            )
        ]


class TrendModelType(models.TextChoices):
    LINEAR = "LINEAR", "선형"
    ROBUST = "ROBUST", "로버스트 선형"
    EXPONENTIAL = "EXPONENTIAL", "포화형"


class TrendStatus(models.TextChoices):
    OK = "OK", "정상"
    ALREADY_EXCEEDED = "ALREADY_EXCEEDED", "이미 도달"
    NO_TREND = "NO_TREND", "추세 미확인"
    BEYOND_HORIZON = "BEYOND_HORIZON", "예측 지평 밖"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA", "데이터 부족"


class TrendForecast(models.Model):
    """추세 예측 및 임계치 도달 예상일 (specs/08 §8)."""

    analysis_run = models.OneToOneField(AnalysisRun, on_delete=models.CASCADE, related_name="trend")
    model_type = models.CharField(
        "추세 모델", max_length=20, choices=TrendModelType.choices, blank=True
    )
    fit_start = models.DateField("적합 시작", null=True, blank=True)
    fit_end = models.DateField("적합 종료", null=True, blank=True)

    coefficients = models.JSONField("계수", default=dict)
    slope_per_day = models.FloatField("진행률(FI/일)", null=True, blank=True)
    r2 = models.FloatField("R²", null=True, blank=True)
    mae = models.FloatField("MAE", null=True, blank=True)
    p_value = models.FloatField("p 값", null=True, blank=True)

    threshold_used = models.FloatField("적용 임계치", null=True, blank=True)
    current_fi = models.FloatField("현재 FI", null=True, blank=True)

    eta_date = models.DateField("도달 예상일", null=True, blank=True)
    eta_days = models.IntegerField("D-day", null=True, blank=True)
    eta_lower_date = models.DateField("도달 하한", null=True, blank=True)
    eta_upper_date = models.DateField("도달 상한", null=True, blank=True)
    caution_eta_date = models.DateField("주의 전환 예상일", null=True, blank=True)
    warning_eta_date = models.DateField("경고 전환 예상일", null=True, blank=True)

    exceeded_days = models.IntegerField("초과 일수", null=True, blank=True)
    weekly_increase = models.FloatField("주간 증가량", null=True, blank=True)
    days_since_cleaning = models.IntegerField("세정 후 경과일", null=True, blank=True)
    uncertain = models.BooleanField("불확실성 높음", default=False)

    status = models.CharField("상태", max_length=30, choices=TrendStatus.choices)
    message = models.CharField("안내", max_length=200, blank=True)

    class Meta:
        verbose_name = "추세 예측"
        verbose_name_plural = "추세 예측"

    def __str__(self) -> str:
        return f"run={self.analysis_run_id} {self.status} D-{self.eta_days}"


class BenefitResult(models.Model):
    """세정 회수 편익 (specs/09 §7).

    params_snapshot 에 적용된 모든 계수를 담아 재현 가능해야 한다(AC-09-3).
    """

    analysis_run = models.OneToOneField(
        AnalysisRun, on_delete=models.CASCADE, related_name="benefit"
    )
    params_snapshot = models.JSONField("적용 파라미터", default=dict)

    delta_dp_kpa = models.FloatField("Δ차압", null=True, blank=True)
    delta_stack_c = models.FloatField("Δ스택온도", null=True, blank=True)

    power_loss_gt_mw = models.FloatField("GT 출력 손실", null=True, blank=True)
    power_loss_st_mw = models.FloatField("ST 출력 손실", null=True, blank=True)
    power_loss_total_mw = models.FloatField("총 출력 손실", null=True, blank=True)

    daily_loss_cost = models.FloatField("일일 손실 비용", null=True, blank=True)
    daily_fuel_loss = models.FloatField("일일 연료 손실", null=True, blank=True)

    cleaning_cost = models.FloatField("세정 비용", null=True, blank=True)
    outage_loss = models.FloatField("정지 손실", null=True, blank=True)
    total_cleaning_cost = models.FloatField("총 세정 비용", null=True, blank=True)

    gross_benefit = models.FloatField("총 회수액(정밀)", null=True, blank=True)
    gross_benefit_simple = models.FloatField("총 회수액(간이)", null=True, blank=True)
    net_benefit = models.FloatField("순편익", null=True, blank=True)
    payback_days = models.FloatField("회수기간", null=True, blank=True)
    roi_pct = models.FloatField("ROI", null=True, blank=True)

    recommended_offset_days = models.IntegerField("권고 세정 시점(일)", null=True, blank=True)
    recommended_cleaning_date = models.DateField("권고 세정 일자", null=True, blank=True)
    recommended_net_benefit = models.FloatField("권고 시점 순편익", null=True, blank=True)

    scenarios = models.JSONField("시나리오 비교", default=list)
    sensitivity = models.JSONField("민감도", default=list)
    warnings = models.JSONField("경고", default=list)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "편익 결과"
        verbose_name_plural = "편익 결과"

    def __str__(self) -> str:
        return f"run={self.analysis_run_id} net={self.net_benefit}"


class ComparisonReport(models.Model):
    """세정 전후 비교 (specs/12 §2, specs/14 §4.4).

    같은 운전 구간끼리만 비교하며, 사용한 모델 버전을 함께 기록한다.
    """

    unit = models.ForeignKey(Unit, on_delete=models.CASCADE, related_name="comparisons")
    cleaning_event = models.ForeignKey(
        "maintenance.CleaningEvent", on_delete=models.CASCADE, related_name="comparisons"
    )
    created_by = models.ForeignKey(
        django_settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    window_days = models.PositiveIntegerField("비교 윈도(일)", default=30)
    before_offset_days = models.IntegerField("세정 전 오프셋", default=0)
    after_offset_days = models.IntegerField("세정 후 오프셋", default=1)
    before_start = models.DateTimeField(null=True, blank=True)
    before_end = models.DateTimeField(null=True, blank=True)
    after_start = models.DateTimeField(null=True, blank=True)
    after_end = models.DateTimeField(null=True, blank=True)

    model_version_dp = models.ForeignKey(
        ModelVersion,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="comparisons_as_dp",
    )
    model_version_st = models.ForeignKey(
        ModelVersion,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="comparisons_as_st",
    )

    metrics = models.JSONField("종합 지표", default=dict)
    cluster_metrics = models.JSONField("군집별 지표", default=list)
    p_values = models.JSONField("유의성", default=dict)
    common_clusters = models.JSONField("공통 군집", default=list)
    recovery_ratio = models.FloatField("회복률", null=True, blank=True)
    warnings = models.JSONField("경고", default=list)

    class Meta:
        verbose_name = "세정 전후 비교"
        verbose_name_plural = "세정 전후 비교"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.unit.code} {self.cleaning_event_id} 비교"
