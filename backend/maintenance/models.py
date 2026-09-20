"""정비·세정 이력 (specs/10, specs/14 §4.5).

세정 이력(CleaningEvent)은 청정 기준 기간 산정(specs/06 §2)과 추세 구간 절단(specs/08 §3)의
기준점이므로 Phase 2에서 먼저 들어왔다. 정비 이력 파일 업로드와 키워드 자동 추출은 Phase 5다.
"""

from django.conf import settings as django_settings
from django.db import models

from ingestion.models import UploadBatch
from units.models import Unit


class CleaningMethod(models.TextChoices):
    WATER_WASH = "WATER_WASH", "수세"
    CHEMICAL = "CHEMICAL", "화학세정"
    DRY_ICE = "DRY_ICE", "드라이아이스"
    MECHANICAL = "MECHANICAL", "기계적 청소"
    SOOT_BLOWING = "SOOT_BLOWING", "수트 블로잉"
    OTHER = "OTHER", "기타"


class CleaningSource(models.TextChoices):
    MANUAL = "MANUAL", "수동 등록"
    EXTRACTED = "EXTRACTED", "정비 이력 추출"


class CleaningEvent(models.Model):
    unit = models.ForeignKey(
        Unit, verbose_name="호기", on_delete=models.CASCADE, related_name="cleaning_events"
    )
    cleaned_at = models.DateTimeField("세정 일자")
    cleaned_end_at = models.DateTimeField("세정 종료 일자", null=True, blank=True)

    method = models.CharField(
        "세정 방법", max_length=20, choices=CleaningMethod.choices, default=CleaningMethod.OTHER
    )
    method_detail = models.CharField("세정 방법 상세", max_length=200, blank=True)
    cost = models.BigIntegerField("비용(원)", null=True, blank=True)
    outage_days = models.FloatField("정지 일수", null=True, blank=True)

    source = models.CharField(
        "등록 경로", max_length=20, choices=CleaningSource.choices, default=CleaningSource.MANUAL
    )
    maintenance_record = models.ForeignKey(
        "maintenance.MaintenanceRecord",
        verbose_name="추출 출처",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    note = models.TextField("비고", blank=True)
    created_by = models.ForeignKey(
        django_settings.AUTH_USER_MODEL,
        verbose_name="등록자",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField("생성 일시", auto_now_add=True)
    updated_at = models.DateTimeField("수정 일시", auto_now=True)

    class Meta:
        verbose_name = "세정 이력"
        verbose_name_plural = "세정 이력"
        ordering = ["-cleaned_at"]
        indexes = [models.Index(fields=["unit", "cleaned_at"])]

    def __str__(self) -> str:
        return f"{self.unit.code} {self.cleaned_at:%Y-%m-%d} {self.get_method_display()}"


class KeywordCategory(models.TextChoices):
    CLEANING = "CLEANING", "세정"
    FOULING = "FOULING", "오염 징후"
    INSPECTION = "INSPECTION", "점검"
    EXCLUDE = "EXCLUDE", "제외어"


class FoulingKeyword(models.Model):
    """오염 관련 키워드 사전 (specs/10 §3.1, FR-A-07)."""

    keyword = models.CharField("키워드", max_length=100)
    category = models.CharField("분류", max_length=20, choices=KeywordCategory.choices)
    weight = models.FloatField("가중치", default=1.0)
    is_active = models.BooleanField("사용", default=True)
    created_by = models.ForeignKey(
        django_settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "오염 키워드"
        verbose_name_plural = "오염 키워드"
        unique_together = [("keyword", "category")]
        ordering = ["category", "keyword"]

    def __str__(self) -> str:
        return f"[{self.category}] {self.keyword}"


class ReviewStatus(models.TextChoices):
    PENDING = "PENDING", "검토 대기"
    ACCEPTED = "ACCEPTED", "승인됨"
    IGNORED = "IGNORED", "무시됨"


class MaintenanceRecord(models.Model):
    """정비 이력 (specs/10 §5).

    자동 추출 결과는 **바로 확정하지 않는다.** 사용자/관리자가 승인해야
    CleaningEvent 로 등록된다(오탐 방지 — AC-10-2).
    """

    unit = models.ForeignKey(
        Unit, verbose_name="호기", on_delete=models.CASCADE, related_name="maintenance_records"
    )
    upload_batch = models.ForeignKey(
        UploadBatch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="maintenance_records",
    )

    work_date = models.DateField("작업일")
    work_type = models.CharField("작업구분", max_length=50, blank=True)
    title = models.CharField("제목", max_length=300)
    description = models.TextField("내용", blank=True)
    cost = models.BigIntegerField("비용", null=True, blank=True)
    duration_days = models.FloatField("소요일수", null=True, blank=True)
    worker = models.CharField("작업자", max_length=100, blank=True)

    is_fouling_related = models.BooleanField("오염 관련", default=False)
    matched_keywords = models.JSONField("매칭 키워드", default=list)
    match_score = models.FloatField("매칭 점수", default=0.0)
    match_category = models.CharField("매칭 분류", max_length=20, blank=True)
    review_status = models.CharField(
        "검토 상태", max_length=20, choices=ReviewStatus.choices, default=ReviewStatus.PENDING
    )
    cleaning_event = models.ForeignKey(
        "maintenance.CleaningEvent",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="source_records",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "정비 이력"
        verbose_name_plural = "정비 이력"
        ordering = ["-work_date"]
        indexes = [
            models.Index(fields=["unit", "-work_date"]),
            models.Index(fields=["is_fouling_related"]),
        ]

    def __str__(self) -> str:
        return f"{self.unit.code} {self.work_date} {self.title[:30]}"
