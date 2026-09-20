"""리포트 생성·다운로드 API (specs/15 §9)."""

from __future__ import annotations

import logging
from pathlib import Path
from urllib.parse import quote

from django.http import FileResponse
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from analysis.models import AnalysisRun, ComparisonReport, RunStatus
from common.exceptions import Conflict, NotFound
from reports import generators
from reports.models import ReportExport, ReportFormat
from reports.serializers import ExportRequestSerializer, ReportExportSerializer

logger = logging.getLogger(__name__)

CONTENT_TYPES = {
    ReportFormat.PDF: "application/pdf",
    ReportFormat.XLSX: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def _resolve_format(request: Request) -> str:
    serializer = ExportRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data["format"]


class ReportExportViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ReportExport.objects.select_related(
        "analysis_run__unit", "comparison_report__unit", "created_by"
    )
    serializer_class = ReportExportSerializer
    permission_classes = [IsAuthenticated]
    ordering_fields = ["created_at"]

    @action(detail=True, methods=["get"])
    def download(self, request: Request, pk: str | None = None) -> FileResponse:
        """한글 파일명은 RFC 5987 로 전달한다 (specs/12 §5, AC-12-6)."""
        export = self.get_object()
        path = Path(export.file_path)
        if not path.exists():
            raise NotFound(message="리포트 파일이 만료되었거나 삭제되었습니다.")

        response = FileResponse(
            path.open("rb"),
            content_type=CONTENT_TYPES.get(export.format, "application/octet-stream"),
        )
        encoded = quote(export.file_name)
        response["Content-Disposition"] = (
            f'attachment; filename="report.{export.format.lower()}"; ' f"filename*=UTF-8''{encoded}"
        )
        response["Content-Length"] = export.file_size_bytes
        return response


class AnalysisExportView(viewsets.ViewSet):
    """POST /api/analysis-runs/{id}/export/"""

    permission_classes = [IsAuthenticated]

    def create(self, request: Request, analysis_run_id: int) -> Response:
        run = AnalysisRun.objects.filter(pk=analysis_run_id).first()
        if run is None:
            raise NotFound(message="분석 실행을 찾을 수 없습니다.")
        if run.status != RunStatus.SUCCESS:
            raise Conflict(message="성공한 분석만 리포트로 내보낼 수 있습니다.")

        export = generators.generate_analysis_report(
            run, _resolve_format(request), user=request.user
        )
        return Response(ReportExportSerializer(export).data, status=status.HTTP_201_CREATED)


class ComparisonExportView(viewsets.ViewSet):
    """POST /api/comparisons/{id}/export/"""

    permission_classes = [IsAuthenticated]

    def create(self, request: Request, comparison_id: int) -> Response:
        report = ComparisonReport.objects.filter(pk=comparison_id).first()
        if report is None:
            raise NotFound(message="비교 리포트를 찾을 수 없습니다.")

        export = generators.generate_comparison_report(
            report, _resolve_format(request), user=request.user
        )
        return Response(ReportExportSerializer(export).data, status=status.HTTP_201_CREATED)
