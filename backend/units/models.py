"""호기·컬럼 매핑·설정값 모델 (specs/02, specs/13 §4.1, specs/14 §4.2)."""

from django.conf import settings as django_settings
from django.db import models

from units.setting_defaults import (
    CAT_BENEFIT,
    CAT_CLUSTER,
    CAT_FOULING,
    CAT_MODEL,
    CAT_PREPROCESS,
    CAT_SYSTEM,
    TYPE_BOOL,
    TYPE_FLOAT,
    TYPE_INT,
    TYPE_JSON,
    TYPE_STRING,
)
from units.standard_fields import ALL_FIELD_KEYS, check_required


class SettingCategory(models.TextChoices):
    FOULING = CAT_FOULING, "오염도"
    PREPROCESS = CAT_PREPROCESS, "전처리"
    CLUSTER = CAT_CLUSTER, "군집화"
    MODEL = CAT_MODEL, "모델"
    BENEFIT = CAT_BENEFIT, "편익"
    SYSTEM = CAT_SYSTEM, "시스템"


class SettingValueType(models.TextChoices):
    INT = TYPE_INT, "정수"
    FLOAT = TYPE_FLOAT, "실수"
    BOOL = TYPE_BOOL, "참/거짓"
    STRING = TYPE_STRING, "문자열"
    JSON = TYPE_JSON, "JSON"


class Setting(models.Model):
    """전역 설정값. 값은 문자열로 저장하고 value_type 으로 캐스팅한다."""

    key = models.CharField("키", max_length=80, unique=True)
    value = models.TextField("현재값")
    value_type = models.CharField("값 타입", max_length=10, choices=SettingValueType.choices)
    category = models.CharField("분류", max_length=20, choices=SettingCategory.choices)
    label = models.CharField("표시 이름", max_length=100)
    description = models.TextField("설명", blank=True)
    default_value = models.TextField("기본값")
    min_value = models.FloatField("최솟값", null=True, blank=True)
    max_value = models.FloatField("최댓값", null=True, blank=True)
    unit_label = models.CharField("단위", max_length=20, blank=True)
    updated_by = models.ForeignKey(
        django_settings.AUTH_USER_MODEL,
        verbose_name="변경자",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_settings",
    )
    updated_at = models.DateTimeField("변경 일시", auto_now=True)

    class Meta:
        verbose_name = "설정값"
        verbose_name_plural = "설정값"
        ordering = ["category", "key"]
        indexes = [models.Index(fields=["category"])]

    def __str__(self) -> str:
        return f"{self.key}={self.value}"


class DpSource(models.TextChoices):
    DP = "DP", "가스측 차압 계측"
    BACKPRESSURE = "BACKPRESSURE", "GT 배압 대체"


class FlowSource(models.TextChoices):
    EXHAUST_FLOW = "EXHAUST_FLOW", "배기유량"
    FUEL_FLOW = "FUEL_FLOW", "연료유량"
    IGV = "IGV", "IGV 개도"


class Unit(models.Model):
    """분석 단위가 되는 개별 설비 (specs/02 §2)."""

    code = models.CharField("호기 코드", max_length=30, unique=True)
    name = models.CharField("호기명", max_length=100)
    plant_name = models.CharField("발전소명", max_length=100, blank=True)
    gt_model = models.CharField("GT 기종", max_length=100, blank=True)

    rated_power_mw = models.FloatField("GT 정격 출력(MW)")
    rated_st_power_mw = models.FloatField("ST 정격 출력(MW)", null=True, blank=True)
    min_load_mw = models.FloatField("최소 안정 부하(MW)")
    sampling_interval_min = models.PositiveIntegerField("데이터 주기(분)", default=10)

    dp_source = models.CharField(
        "차압 기준", max_length=20, choices=DpSource.choices, default=DpSource.DP
    )
    flow_source = models.CharField(
        "유량 기준", max_length=20, choices=FlowSource.choices, default=FlowSource.EXHAUST_FLOW
    )

    is_active = models.BooleanField("사용 여부", default=True)
    created_at = models.DateTimeField("생성 일시", auto_now_add=True)
    updated_at = models.DateTimeField("수정 일시", auto_now=True)

    class Meta:
        verbose_name = "호기"
        verbose_name_plural = "호기"
        ordering = ["code"]

    def __str__(self) -> str:
        return f"{self.code} {self.name}"

    # --- 파생 속성 (무거운 계산은 두지 않는다 — AGENTS.md §3) ---

    def mapping_problems(self) -> list[dict]:
        mapped = set(self.column_mappings.values_list("standard_field", flat=True))
        return check_required(mapped)

    @property
    def is_mapping_complete(self) -> bool:
        return not self.mapping_problems()


class BoolRule(models.TextChoices):
    BOOL = "BOOL", "참/거짓 문자열"
    THRESHOLD = "THRESHOLD", "임계값 초과 시 ON"


class ColumnMapping(models.Model):
    """원본 CSV 컬럼 → 표준 항목 (specs/02 §4).

    변환식: 표준값 = 원본값 × scale_factor + offset
    """

    unit = models.ForeignKey(
        Unit, verbose_name="호기", on_delete=models.CASCADE, related_name="column_mappings"
    )
    standard_field = models.CharField(
        "표준 항목", max_length=40, choices=[(k, k) for k in ALL_FIELD_KEYS]
    )
    source_column = models.CharField("원본 컬럼명", max_length=200)
    unit_label = models.CharField("원본 단위", max_length=30, blank=True)
    scale_factor = models.FloatField("환산 계수", default=1.0)
    offset = models.FloatField("환산 오프셋", default=0.0)

    # duct_burner_on 해석 규칙
    bool_rule = models.CharField("해석 규칙", max_length=20, choices=BoolRule.choices, blank=True)
    bool_threshold = models.FloatField("ON 판정 임계값", null=True, blank=True)

    class Meta:
        verbose_name = "컬럼 매핑"
        verbose_name_plural = "컬럼 매핑"
        unique_together = [("unit", "standard_field")]
        ordering = ["unit", "standard_field"]

    def __str__(self) -> str:
        return f"{self.unit.code}: {self.source_column} → {self.standard_field}"


class ColumnMappingVersion(models.Model):
    """매핑 변경 이력 (specs/02 §5.5).

    과거 분석 결과의 재현성을 위해 분석 실행 시 사용한 매핑 버전을 기록한다.
    """

    unit = models.ForeignKey(
        Unit, verbose_name="호기", on_delete=models.CASCADE, related_name="mapping_versions"
    )
    version = models.PositiveIntegerField("버전")
    snapshot = models.JSONField("매핑 스냅샷")
    created_by = models.ForeignKey(
        django_settings.AUTH_USER_MODEL,
        verbose_name="변경자",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField("생성 일시", auto_now_add=True)

    class Meta:
        verbose_name = "컬럼 매핑 버전"
        verbose_name_plural = "컬럼 매핑 버전"
        unique_together = [("unit", "version")]
        ordering = ["-version"]

    def __str__(self) -> str:
        return f"{self.unit.code} v{self.version}"


class UnitSetting(models.Model):
    """호기별 설정 오버라이드 (specs/13 §4.1).

    조회 우선순위: UnitSetting → Setting → 코드 시드 기본값
    """

    unit = models.ForeignKey(
        Unit, verbose_name="호기", on_delete=models.CASCADE, related_name="unit_settings"
    )
    key = models.CharField("키", max_length=80)
    value = models.TextField("값")
    updated_by = models.ForeignKey(
        django_settings.AUTH_USER_MODEL,
        verbose_name="변경자",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    updated_at = models.DateTimeField("변경 일시", auto_now=True)

    class Meta:
        verbose_name = "호기별 설정"
        verbose_name_plural = "호기별 설정"
        unique_together = [("unit", "key")]
        ordering = ["unit", "key"]

    def __str__(self) -> str:
        return f"{self.unit.code}.{self.key}={self.value}"
