"""업로드 배치와 원본 측정값 (specs/03 §5, specs/14 §4.3).

Measurement 는 **불변(immutable)** 으로 취급한다. 정제·제외는 파생 테이블의
플래그로 표현하고 원본은 수정·삭제하지 않는다(AGENTS.md §5.3, AC-04-5).
"""

from django.conf import settings as django_settings
from django.db import models

from units.models import ColumnMappingVersion, Unit


class UploadKind(models.TextChoices):
    OPERATION = "OPERATION", "운전 데이터"
    MAINTENANCE = "MAINTENANCE", "정비 이력"


class BatchStatus(models.TextChoices):
    PENDING = "PENDING", "검증 대기"
    VALIDATED = "VALIDATED", "검증 완료"
    LOADED = "LOADED", "적재 완료"
    FAILED = "FAILED", "실패"
    CANCELED = "CANCELED", "취소됨"


class DuplicatePolicy(models.TextChoices):
    SKIP = "SKIP", "건너뛰기"
    OVERWRITE = "OVERWRITE", "덮어쓰기"


class UploadBatch(models.Model):
    unit = models.ForeignKey(
        Unit, verbose_name="호기", on_delete=models.CASCADE, related_name="upload_batches"
    )
    kind = models.CharField(
        "종류", max_length=20, choices=UploadKind.choices, default=UploadKind.OPERATION
    )
    uploaded_by = models.ForeignKey(
        django_settings.AUTH_USER_MODEL,
        verbose_name="업로더",
        on_delete=models.SET_NULL,
        null=True,
        related_name="upload_batches",
    )
    uploaded_at = models.DateTimeField("업로드 일시", auto_now_add=True)

    original_filename = models.CharField("원본 파일명", max_length=255)
    stored_path = models.CharField("저장 경로", max_length=500, blank=True)
    file_size_bytes = models.BigIntegerField("파일 크기", default=0)
    checksum = models.CharField("체크섬(sha256)", max_length=64, blank=True, db_index=True)

    status = models.CharField(
        "상태", max_length=20, choices=BatchStatus.choices, default=BatchStatus.PENDING
    )
    row_total = models.IntegerField("총 행수", default=0)
    row_loaded = models.IntegerField("적재 행수", default=0)
    row_skipped = models.IntegerField("제외 행수", default=0)
    row_duplicated = models.IntegerField("중복 행수", default=0)

    period_start = models.DateTimeField("데이터 시작", null=True, blank=True)
    period_end = models.DateTimeField("데이터 종료", null=True, blank=True)

    validation_report = models.JSONField("검증 리포트", default=dict, blank=True)
    error_message = models.TextField("오류 메시지", blank=True)
    column_mapping_version = models.ForeignKey(
        ColumnMappingVersion,
        verbose_name="매핑 버전",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "업로드 배치"
        verbose_name_plural = "업로드 배치"
        ordering = ["-uploaded_at"]
        indexes = [models.Index(fields=["unit", "-uploaded_at"]), models.Index(fields=["status"])]

    def __str__(self) -> str:
        return f"{self.unit.code} {self.original_filename} ({self.status})"


class Measurement(models.Model):
    """호기별 누적 운전 시계열. 가장 큰 테이블이다.

    성능 주의(specs/14 §4.3): (unit, timestamp) 복합 인덱스를 필수로 두고,
    수천만 행 규모로 커지면 월 단위 선언적 파티셔닝을 검토한다.
    """

    unit = models.ForeignKey(
        Unit, verbose_name="호기", on_delete=models.CASCADE, related_name="measurements"
    )
    timestamp = models.DateTimeField("측정 시각", db_index=True)

    gt_power_mw = models.FloatField(null=True, blank=True)
    ambient_temp_c = models.FloatField(null=True, blank=True)
    gt_exhaust_temp_c = models.FloatField(null=True, blank=True)
    exhaust_flow = models.FloatField(null=True, blank=True)
    fuel_flow = models.FloatField(null=True, blank=True)
    igv_position_pct = models.FloatField(null=True, blank=True)
    hrsg_gas_dp_kpa = models.FloatField(null=True, blank=True)
    gt_backpressure_kpa = models.FloatField(null=True, blank=True)
    stack_temp_c = models.FloatField(null=True, blank=True)
    duct_burner_on = models.BooleanField(null=True, blank=True)
    st_power_mw = models.FloatField(null=True, blank=True)
    steam_flow_tph = models.FloatField(null=True, blank=True)
    feedwater_temp_c = models.FloatField(null=True, blank=True)
    ambient_pressure_kpa = models.FloatField(null=True, blank=True)
    humidity_pct = models.FloatField(null=True, blank=True)

    upload_batch = models.ForeignKey(
        UploadBatch,
        verbose_name="업로드 배치",
        on_delete=models.SET_NULL,
        null=True,
        related_name="measurements",
    )

    class Meta:
        verbose_name = "측정값"
        verbose_name_plural = "측정값"
        constraints = [
            models.UniqueConstraint(fields=["unit", "timestamp"], name="uniq_unit_timestamp")
        ]
        indexes = [models.Index(fields=["unit", "timestamp"])]

    def __str__(self) -> str:
        return f"{self.unit_id}@{self.timestamp:%Y-%m-%d %H:%M}"
