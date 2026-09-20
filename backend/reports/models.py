"""리포트 생성 이력 (specs/12 §5, specs/14 §4.6)."""

from django.conf import settings as django_settings
from django.db import models

from analysis.models import AnalysisRun, ComparisonReport


class ReportFormat(models.TextChoices):
    PDF = "PDF", "PDF"
    XLSX = "XLSX", "엑셀"


class ReportExport(models.Model):
    analysis_run = models.ForeignKey(
        AnalysisRun, on_delete=models.CASCADE, null=True, blank=True, related_name="exports"
    )
    comparison_report = models.ForeignKey(
        ComparisonReport, on_delete=models.CASCADE, null=True, blank=True, related_name="exports"
    )
    format = models.CharField("형식", max_length=10, choices=ReportFormat.choices)
    file_path = models.CharField("파일 경로", max_length=500, blank=True)
    file_name = models.CharField("파일명", max_length=300, blank=True)
    file_size_bytes = models.BigIntegerField("파일 크기", default=0)

    created_by = models.ForeignKey(
        django_settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField("생성 일시", auto_now_add=True)
    expires_at = models.DateTimeField("만료 일시", null=True, blank=True)

    class Meta:
        verbose_name = "리포트 생성 이력"
        verbose_name_plural = "리포트 생성 이력"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["-created_at"])]

    def __str__(self) -> str:
        return f"{self.file_name} ({self.format})"
