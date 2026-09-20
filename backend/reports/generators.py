"""리포트 파일 생성 + 저장 (specs/12 §5)."""

from __future__ import annotations

import logging
import re
import uuid
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from analysis.models import AnalysisRun, ComparisonReport
from reports import context as ctx_builder
from reports.excel.builder import build_analysis_xlsx
from reports.models import ReportExport, ReportFormat
from reports.pdf.builder import build_analysis_pdf
from units.settings_resolver import get_setting

logger = logging.getLogger(__name__)

_UNSAFE = re.compile(r"[^\w가-힣._-]+")


def build_filename(prefix: str, unit_code: str, start: str, end: str, extension: str) -> str:
    """`HRSG오염도리포트_{호기}_{시작}_{종료}_{생성일시}.pdf` (specs/12 §5)."""
    stamp = timezone.localtime().strftime("%Y%m%d%H%M")
    raw = f"{prefix}_{unit_code}_{start}_{end}_{stamp}.{extension}"
    return _UNSAFE.sub("-", raw)


def _store(content: bytes, filename: str) -> Path:
    root = Path(settings.REPORT_ROOT)
    root.mkdir(parents=True, exist_ok=True)
    # 파일명 충돌과 경로 추측을 막기 위해 디스크에는 UUID 로 저장한다.
    path = root / f"{uuid.uuid4().hex}{Path(filename).suffix}"
    path.write_bytes(content)
    return path


def generate_analysis_report(run: AnalysisRun, report_format: str, user=None) -> ReportExport:
    context = ctx_builder.build_analysis_context(run)

    if report_format == ReportFormat.PDF:
        content = build_analysis_pdf(context)
        extension = "pdf"
    else:
        content = build_analysis_xlsx(context)
        extension = "xlsx"

    filename = build_filename(
        "HRSG오염도리포트",
        run.unit.code,
        context["period_start"],
        context["period_end"],
        extension,
    )
    path = _store(content, filename)
    retention = int(get_setting("report_retention_days", run.unit_id))

    export = ReportExport.objects.create(
        analysis_run=run,
        format=report_format,
        file_path=str(path),
        file_name=filename,
        file_size_bytes=len(content),
        created_by=user,
        expires_at=timezone.now() + timedelta(days=retention),
    )
    logger.info("report generated run_id=%s format=%s size=%s", run.id, report_format, len(content))
    return export


def generate_comparison_report(
    report: ComparisonReport, report_format: str, user=None
) -> ReportExport:
    context = ctx_builder.build_comparison_context(report)

    if report_format == ReportFormat.PDF:
        content = build_analysis_pdf(context)
        extension = "pdf"
    else:
        content = build_analysis_xlsx(context)
        extension = "xlsx"

    filename = build_filename(
        "HRSG세정전후비교",
        report.unit.code,
        context["period_start"],
        context["period_end"],
        extension,
    )
    path = _store(content, filename)
    retention = int(get_setting("report_retention_days", report.unit_id))

    return ReportExport.objects.create(
        comparison_report=report,
        format=report_format,
        file_path=str(path),
        file_name=filename,
        file_size_bytes=len(content),
        created_by=user,
        expires_at=timezone.now() + timedelta(days=retention),
    )
