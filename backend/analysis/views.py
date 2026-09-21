"""분석 API (specs/15 §6)."""

from __future__ import annotations

from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from accounts.permissions import IsAdminRole
from analysis import tasks
from analysis.comparison_service import run_comparison
from analysis.models import (
    AnalysisRun,
    ComparisonReport,
    FoulingIndexPoint,
    RunStatus,
)
from analysis.pipeline import build_config, recalculate_benefit_for_run, release_stale_runs
from analysis.serializers import (
    AnalysisRunListSerializer,
    AnalysisRunRequestSerializer,
    AnalysisRunSerializer,
    BenefitParamsSerializer,
    BenefitResultSerializer,
    ComparisonReportSerializer,
    ComparisonRequestSerializer,
    FoulingIndexPointSerializer,
    ModelVersionSerializer,
    TrendForecastSerializer,
)
from common import jobs
from common.exceptions import Conflict, NotFound
from units.models import Unit


class AnalysisRunViewSet(mixins.DestroyModelMixin, viewsets.ReadOnlyModelViewSet):
    # ReadOnlyModelViewSet 만으로는 DELETE 가 405 다. 삭제는 관리자 전용
    # (get_permissions 참조, specs/15 §6, AGENTS.md §6).
    queryset = AnalysisRun.objects.select_related(
        "unit", "executed_by", "model_version_dp", "model_version_st"
    )
    permission_classes = [IsAuthenticated]
    ordering_fields = ["executed_at", "result_fi"]

    def get_serializer_class(self):
        return AnalysisRunListSerializer if self.action == "list" else AnalysisRunSerializer

    def get_permissions(self):
        if self.action == "destroy":
            return [IsAdminRole()]
        return [IsAuthenticated()]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        if unit_id := params.get("unit_id"):
            qs = qs.filter(unit_id=unit_id)
        if run_status := params.get("status"):
            qs = qs.filter(status=run_status)
        if executed_by := params.get("executed_by"):
            qs = qs.filter(executed_by_id=executed_by)
        if start := params.get("from"):
            qs = qs.filter(executed_at__gte=start)
        if end := params.get("to"):
            qs = qs.filter(executed_at__lte=end)
        return qs

    def create(self, request: Request) -> Response:
        """POST /api/analysis-runs/ → 202 + job_id (specs/15 §6)."""
        serializer = AnalysisRunRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        unit = Unit.objects.filter(pk=data["unit_id"]).first()
        if unit is None:
            raise NotFound(message="호기를 찾을 수 없습니다.")

        # 워커가 죽어 RUNNING 으로 남은 레코드를 먼저 정리한다.
        # 그대로 두면 아래 동시 실행 제약에 걸려 그 호기는 영영 분석을 못 한다.
        config = build_config(unit)
        release_stale_runs(unit, config["analysis_stale_minutes"])

        # 호기당 동시 1건 (specs/15 §13)
        if AnalysisRun.objects.filter(unit=unit, status=RunStatus.RUNNING).exists():
            raise Conflict(
                code="ANALYSIS_ALREADY_RUNNING",
                message="해당 호기에 진행 중인 분석이 있습니다.",
            )

        overrides = data.get("settings_override") or {}
        benefit_overrides = data.get("benefit_params_override") or {}
        run = AnalysisRun.objects.create(
            unit=unit,
            executed_by=request.user,
            period_start=data["period_start"],
            period_end=data["period_end"],
            status=RunStatus.RUNNING,
            # 적용된 설정값 전체를 스냅샷으로 남긴다 — 재현성의 핵심 (AC-14-3)
            settings_snapshot={**config, **overrides},
            benefit_params_snapshot=benefit_overrides,
        )

        job_id = jobs.enqueue(
            tasks.run_analysis_task,
            analysis_run_id=run.id,
            overrides=overrides,
            benefit_overrides=benefit_overrides,
        )
        return Response(
            {"job_id": job_id, "status": jobs.RUNNING, "analysis_run_id": run.id},
            status=status.HTTP_202_ACCEPTED,
        )

    # --- 결과 조회 ---

    @action(detail=True, methods=["get"], url_path="fouling-index")
    def fouling_index(self, request: Request, pk: str | None = None) -> Response:
        """FI 시계열. 차트 데이터는 일 단위 집계로 반환한다 (specs/18 §1)."""
        run = self.get_object()
        qs = FoulingIndexPoint.objects.filter(analysis_run=run)

        cluster_key = request.query_params.get("cluster_key")
        # cluster_key 미지정이면 전체 집계(빈 문자열)만 돌려준다.
        qs = qs.filter(cluster_key=cluster_key if cluster_key is not None else "")

        if start := request.query_params.get("from"):
            qs = qs.filter(date__gte=start)
        if end := request.query_params.get("to"):
            qs = qs.filter(date__lte=end)

        return Response(FoulingIndexPointSerializer(qs.order_by("date"), many=True).data)

    @action(detail=True, methods=["get"])
    def clusters(self, request: Request, pk: str | None = None) -> Response:
        run = self.get_object()
        return Response(run.data_stats.get("cluster_summary", []))

    @action(detail=True, methods=["get"], url_path="model-metrics")
    def model_metrics(self, request: Request, pk: str | None = None) -> Response:
        run = self.get_object()
        return Response(
            {
                "dp": (
                    ModelVersionSerializer(run.model_version_dp).data
                    if run.model_version_dp
                    else None
                ),
                "stack_temp": (
                    ModelVersionSerializer(run.model_version_st).data
                    if run.model_version_st
                    else None
                ),
            }
        )

    @action(detail=True, methods=["get"], url_path="data-quality")
    def data_quality(self, request: Request, pk: str | None = None) -> Response:
        """정제 요약 — UI 표시 필수 (specs/04 §8)."""
        run = self.get_object()
        stats = run.data_stats or {}
        return Response(
            {
                "period": {"start": run.period_start, "end": run.period_end},
                "row_total": stats.get("row_total"),
                "row_valid": stats.get("row_valid"),
                "valid_ratio": stats.get("valid_ratio"),
                "excluded_by_reason": stats.get("excluded_by_reason", {}),
                "segment_count": stats.get("segment_count"),
                "cells_outlier": stats.get("cells_outlier"),
                "cells_interpolated": stats.get("cells_interpolated"),
                "baseline_source": stats.get("baseline_source"),
                "baseline_points": stats.get("baseline_points"),
                "out_of_domain_ratio": stats.get("out_of_domain_ratio"),
                "warnings": run.warnings,
            }
        )

    @action(detail=True, methods=["get"])
    def trend(self, request: Request, pk: str | None = None) -> Response:
        """추세·D-day (specs/15 §6)."""
        run = self.get_object()
        forecast = getattr(run, "trend", None)
        if forecast is None:
            raise NotFound(message="추세 결과가 없습니다.")
        return Response(TrendForecastSerializer(forecast).data)

    @action(detail=True, methods=["get"])
    def benefit(self, request: Request, pk: str | None = None) -> Response:
        run = self.get_object()
        result = getattr(run, "benefit", None)
        if result is None:
            raise NotFound(message="편익 결과가 없습니다.")
        return Response(BenefitResultSerializer(result).data)

    @action(detail=True, methods=["post"], url_path="recalculate-benefit")
    def recalculate_benefit(self, request: Request, pk: str | None = None) -> Response:
        """편익 파라미터만 바꿔 재계산한다 — 분석은 재실행하지 않는다 (specs/15 §6).

        관리자 기본 설정값은 변경되지 않는다(AC-09-2).
        """
        run = self.get_object()
        if run.status != RunStatus.SUCCESS:
            raise Conflict(message="성공한 분석만 편익을 재계산할 수 있습니다.")

        serializer = BenefitParamsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        overrides = serializer.validated_data["benefit_params_override"]

        result = recalculate_benefit_for_run(run, overrides)
        return Response(BenefitResultSerializer(result).data)

    @action(detail=False, methods=["get"], url_path="export-history")
    def export_history(self, request: Request):
        """분석 실행 이력 엑셀 내보내기 (specs/13 §6)."""
        import io
        from urllib.parse import quote

        from django.http import FileResponse
        from django.utils import timezone
        from openpyxl import Workbook

        from reports import formatting as fmt

        rows = self.filter_queryset(self.get_queryset())[:5000]
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "분석이력"
        header = [
            "실행 일시",
            "호기",
            "실행자",
            "데이터 시작",
            "데이터 종료",
            "FI",
            "등급",
            "신뢰도",
            "D-day",
            "순편익(원)",
            "소요시간(초)",
            "상태",
            "자동",
        ]
        sheet.append(header)
        for run in rows:
            sheet.append(
                [
                    fmt.ymd_hm(run.executed_at),
                    run.unit.code,
                    run.executed_by.full_name if run.executed_by else "",
                    fmt.ymd(run.period_start),
                    fmt.ymd(run.period_end),
                    run.result_fi,
                    fmt.grade(run.result_grade),
                    fmt.confidence(run.result_confidence),
                    run.result_dday,
                    run.result_net_benefit,
                    run.duration_sec,
                    run.status,
                    "예" if run.is_auto else "아니오",
                ]
            )
        for index in range(1, len(header) + 1):
            letter = sheet.cell(row=1, column=index).column_letter
            width = max(
                (len(str(c.value)) for c in sheet[letter] if c.value is not None), default=8
            )
            sheet.column_dimensions[letter].width = min(max(width + 3, 10), 40)
        sheet.freeze_panes = "A2"

        buffer = io.BytesIO()
        workbook.save(buffer)
        buffer.seek(0)

        name = f"분석실행이력_{timezone.localtime():%Y%m%d%H%M}.xlsx"
        response = FileResponse(
            buffer,
            content_type=("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        )
        response["Content-Disposition"] = (
            f"attachment; filename=\"history.xlsx\"; filename*=UTF-8''{quote(name)}"
        )
        return response

    @action(detail=True, methods=["get"])
    def residuals(self, request: Request, pk: str | None = None) -> Response:
        """차압·스택온도 실측/기대/잔차 시계열 (일 단위 집계)."""
        run = self.get_object()
        qs = FoulingIndexPoint.objects.filter(analysis_run=run, cluster_key="").order_by("date")
        return Response(
            [
                {
                    "date": row.date,
                    "measured_dp": row.measured_dp,
                    "expected_dp": row.expected_dp,
                    "residual_dp": row.residual_dp,
                    "measured_st": row.measured_st,
                    "expected_st": row.expected_st,
                    "residual_st": row.residual_st,
                }
                for row in qs
            ]
        )


class ComparisonViewSet(viewsets.ReadOnlyModelViewSet):
    """세정 전후 비교 (specs/15 §8)."""

    queryset = ComparisonReport.objects.select_related("unit", "cleaning_event", "created_by")
    serializer_class = ComparisonReportSerializer
    permission_classes = [IsAuthenticated]
    ordering_fields = ["created_at"]

    def get_queryset(self):
        qs = super().get_queryset()
        if unit_id := self.request.query_params.get("unit_id"):
            qs = qs.filter(unit_id=unit_id)
        return qs

    def create(self, request: Request) -> Response:
        from maintenance.models import CleaningEvent

        serializer = ComparisonRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        event = CleaningEvent.objects.filter(pk=data["cleaning_event_id"]).first()
        if event is None:
            raise NotFound(message="세정 이력을 찾을 수 없습니다.")

        report = run_comparison(
            event,
            window_days=data["window_days"],
            before_offset_days=data["before_offset_days"],
            after_offset_days=data["after_offset_days"],
            user=request.user,
        )
        return Response(ComparisonReportSerializer(report).data, status=status.HTTP_201_CREATED)
