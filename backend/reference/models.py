"""참조 데이터 (specs/06, specs/09 §6).

지금은 전부 `[임시값]` 이다. 실무 자료를 받으면 관리자 모드에서 교체하고 is_placeholder 를 해제한다.
수정하면 version 이 올라가고, 계산 결과는 쓴 참조값의 버전을 남긴다(specs/05 CALC-10).
"""

from django.conf import settings as django_settings
from django.db import models
from django.db.models import F, Q


class VersionedModel(models.Model):
    """수정할 때마다 version 을 올린다. 동시 편집 충돌 판정에도 쓴다(specs/08 ADM-7)."""

    version = models.PositiveIntegerField("버전", default=1)
    is_placeholder = models.BooleanField("임시값", default=True)
    is_active = models.BooleanField("사용", default=True)
    note = models.TextField("비고", blank=True)
    created_at = models.DateTimeField("생성 일시", auto_now_add=True)
    updated_at = models.DateTimeField("수정 일시", auto_now=True)

    class Meta:
        abstract = True


class GtModel(VersionedModel):
    """GT 모델별 운전 한계 참조표 (specs/06 REF-1)."""

    name = models.CharField("모델 이름", max_length=100, unique=True)
    manufacturer = models.CharField("제조사", max_length=100, blank=True)
    rated_gt_mw = models.FloatField("GT 정격 출력(MW)")
    rated_st_mw = models.FloatField("ST 정격 출력(MW)", null=True, blank=True)
    design_backpressure_kpa = models.FloatField("설계 배압(kPa)")
    backpressure_alarm_kpa = models.FloatField("배압 경보(kPa)")
    backpressure_trip_kpa = models.FloatField("배압 트립(kPa)")
    design_exhaust_temp_c = models.FloatField("설계 배기온도(℃)")
    exhaust_temp_alarm_c = models.FloatField("배기온도 경보(℃)")
    exhaust_temp_trip_c = models.FloatField("배기온도 트립(℃)")
    design_stack_temp_c = models.FloatField("설계 굴뚝 온도(℃)")

    class Meta:
        verbose_name = "GT 운전 한계"
        verbose_name_plural = "GT 운전 한계"
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(
                condition=Q(backpressure_alarm_kpa__lt=F("backpressure_trip_kpa")),
                name="gtmodel_backpressure_alarm_lt_trip",
            ),
            models.CheckConstraint(
                condition=Q(exhaust_temp_alarm_c__lt=F("exhaust_temp_trip_c")),
                name="gtmodel_exhaust_alarm_lt_trip",
            ),
            models.CheckConstraint(
                condition=Q(rated_gt_mw__gt=0), name="gtmodel_rated_gt_positive"
            ),
        ]

    def __str__(self) -> str:
        return self.name


class CleaningMethod(VersionedModel):
    """세정 공법 표 (specs/06 REF-2)."""

    name = models.CharField("공법", max_length=100, unique=True)
    cleaning_cost_won = models.FloatField("세정 비용(원)")
    outage_days = models.FloatField("정지 일수(일)")
    recovery_ratio = models.FloatField("회복률")

    class Meta:
        verbose_name = "세정 공법"
        verbose_name_plural = "세정 공법"
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(
                condition=Q(recovery_ratio__gt=0) & Q(recovery_ratio__lte=1),
                name="cleaningmethod_recovery_ratio_range",
            ),
            models.CheckConstraint(
                condition=Q(cleaning_cost_won__gte=0), name="cleaningmethod_cost_nonnegative"
            ),
            models.CheckConstraint(
                condition=Q(outage_days__gte=0), name="cleaningmethod_outage_nonnegative"
            ),
        ]

    def __str__(self) -> str:
        return self.name


class SmpPrice(models.Model):
    """관리자가 등록한 SMP (specs/06 REF-3).

    이력은 지우지 않고 남긴다 — 최신 기준일 값이 계산기 기본값이다.
    """

    value_won_per_kwh = models.FloatField("SMP(원/kWh)")
    as_of_date = models.DateField("기준일")
    period_label = models.CharField("기간 표기", max_length=50, blank=True)
    source = models.CharField("출처", max_length=200)
    is_estimate = models.BooleanField("추정값", default=False)
    created_by = models.ForeignKey(
        django_settings.AUTH_USER_MODEL,
        verbose_name="등록자",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    created_at = models.DateTimeField("등록 일시", auto_now_add=True)

    class Meta:
        verbose_name = "SMP"
        verbose_name_plural = "SMP"
        ordering = ["-as_of_date", "-created_at"]
        constraints = [
            models.CheckConstraint(condition=Q(value_won_per_kwh__gt=0), name="smp_positive"),
        ]

    def __str__(self) -> str:
        return f"{self.value_won_per_kwh} 원/kWh ({self.as_of_date})"


class CalcParameterSet(models.Model):
    """손실 모델 계수의 버전 묶음 (specs/06 REF-5). 활성 세트는 하나다.

    값을 바꾸면 행을 고치지 않고 새 버전을 만든다 — 이전 결과의 param_version 이 계속 뜻을 가진다.
    """

    version_label = models.CharField("버전", max_length=20, unique=True)
    params = models.JSONField("파라미터")
    is_active = models.BooleanField("활성", default=False)
    is_seed = models.BooleanField("시드값 그대로", default=False)
    note = models.TextField("변경 사유", blank=True)
    created_by = models.ForeignKey(
        django_settings.AUTH_USER_MODEL,
        verbose_name="작성자",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    created_at = models.DateTimeField("생성 일시", auto_now_add=True)

    class Meta:
        verbose_name = "계산 파라미터 세트"
        verbose_name_plural = "계산 파라미터 세트"
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["is_active"],
                condition=Q(is_active=True),
                name="calcparameterset_single_active",
            ),
        ]

    def __str__(self) -> str:
        return self.version_label
