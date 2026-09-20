"""옵션 기능 API — 자동 재계산·백테스트·호기 간 비교·알림 (specs/19).

분석 로직은 services 에, 실행은 tasks_auto 에 있다. 여기는 HTTP 입출력만 다룬다.
"""

from __future__ import annotations

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsAdminRole
from analysis.models import (
    AnalysisRun,
    AutoRecalcConfig,
    BacktestResult,
    Notification,
    RunStatus,
)
from analysis.serializers_admin import (
    AutoRecalcConfigSerializer,
    BacktestRequestSerializer,
    BacktestResultSerializer,
    NotificationSerializer,
)
from analysis.services import priority
from analysis.tasks_auto import run_backtest
from common import jobs
from common.exceptions import NotFound, ValidationError
from maintenance.models import CleaningEvent
from units.models import Unit
from units.settings_resolver import get_effective_settings


class AutoRecalcConfigView(GenericAPIView):
    """GET/PUT /api/units/{unit_id}/auto-recalc/ (specs/19 §1.2)."""

    serializer_class = AutoRecalcConfigSerializer

    def get_permissions(self):
        return [IsAuthenticated()] if self.request.method == "GET" else [IsAdminRole()]

    def _config(self, unit_id: int) -> AutoRecalcConfig:
        unit = Unit.objects.filter(pk=unit_id).first()
        if unit is None:
            raise NotFound(message="호기를 찾을 수 없습니다.")
        config, _ = AutoRecalcConfig.objects.get_or_create(unit=unit)
        return config

    def get(self, request: Request, unit_id: int) -> Response:
        return Response(AutoRecalcConfigSerializer(self._config(unit_id)).data)

    def put(self, request: Request, unit_id: int) -> Response:
        config = self._config(unit_id)
        serializer = AutoRecalcConfigSerializer(config, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save(updated_by=request.user)
        return Response(serializer.data)


class BacktestViewSet(viewsets.ReadOnlyModelViewSet):
    """GET /api/backtests/, POST /api/backtests/ (specs/19 §2)."""

    queryset = BacktestResult.objects.select_related("unit", "created_by")
    serializer_class = BacktestResultSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        if unit_id := self.request.query_params.get("unit_id"):
            qs = qs.filter(unit_id=unit_id)
        return qs

    def get_permissions(self):
        if self.action == "create":
            return [IsAdminRole()]
        return super().get_permissions()

    def create(self, request: Request) -> Response:
        serializer = BacktestRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        unit = Unit.objects.filter(pk=data["unit_id"]).first()
        if unit is None:
            raise NotFound(message="호기를 찾을 수 없습니다.")

        # 세정 1회 이하 호기는 검증 자체가 불가능하다 (AC-19-6).
        if CleaningEvent.objects.filter(unit=unit).count() <= 1:
            raise ValidationError(
                code="BACKTEST_NOT_AVAILABLE",
                message="세정 이력이 2회 이상이어야 백테스트를 실행할 수 있습니다.",
            )

        # lookahead_days 를 안 주면 설정의 다중 지점(기본 30/60/90)을 모두 평가한다.
        lookahead = data.get("lookahead_days")
        evaluated = (
            [int(lookahead)]
            if lookahead
            else [
                int(x)
                for x in (get_effective_settings(unit.id).get("backtest_lookahead_days") or [60])
            ]
        )

        job_id = jobs.enqueue(
            run_backtest,
            unit_id=unit.id,
            lookahead_days=int(lookahead) if lookahead else None,
            created_by_id=request.user.id,
        )
        return Response(
            {"job_id": job_id, "status": jobs.RUNNING, "lookahead_days": evaluated},
            status=status.HTTP_202_ACCEPTED,
        )

    @action(detail=False, methods=["get"], url_path="availability")
    def availability(self, request: Request) -> Response:
        """호기별 실행 가능 여부 — 프론트 메뉴 비활성화 판단용 (AC-19-6)."""
        rows = []
        for unit in Unit.objects.filter(is_active=True):
            count = CleaningEvent.objects.filter(unit=unit).count()
            rows.append(
                {
                    "unit_id": unit.id,
                    "unit_code": unit.code,
                    "cleaning_count": count,
                    "available": count > 1,
                    "reason": "" if count > 1 else "세정 이력이 2회 이상이어야 합니다.",
                }
            )
        return Response({"results": rows})


class UnitComparisonView(APIView):
    """GET /api/units/comparison/ — 세정 우선순위 (specs/19 §3)."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        codes = request.query_params.get("unit_ids", "")
        units = Unit.objects.filter(is_active=True)
        if codes:
            units = units.filter(pk__in=[int(x) for x in codes.split(",") if x.strip().isdigit()])

        rows = [_comparison_row(unit) for unit in units]
        weights = get_effective_settings(None).get("priority_weights") or {}
        ranked = priority.rank(rows, weights)
        return Response({"weights": weights or priority.DEFAULT_WEIGHTS, "results": ranked})


def _comparison_row(unit: Unit) -> dict:
    """호기의 최신 성공 분석에서 비교 지표만 뽑는다.

    절대 차압·스택온도는 설비마다 달라 비교 불가이므로 **쓰지 않는다**(specs/19 §3.2).
    """
    run = (
        AnalysisRun.objects.filter(unit=unit, status=RunStatus.SUCCESS)
        .select_related("trend", "benefit")
        .order_by("-executed_at")
        .first()
    )
    base = {"unit_id": unit.id, "unit_code": unit.code, "unit_name": unit.name}
    if run is None:
        return {**base, "has_analysis": False}

    trend = getattr(run, "trend", None)
    benefit = getattr(run, "benefit", None)
    return {
        **base,
        "has_analysis": True,
        "analysis_run_id": run.id,
        "executed_at": run.executed_at,
        "fi": run.result_fi,
        "grade": run.result_grade,
        "confidence": run.result_confidence,
        "slope_per_day": trend.slope_per_day if trend else None,
        "eta_days": run.result_dday,
        "eta_date": trend.eta_date if trend else None,
        "already_exceeded": bool(trend and trend.status == "ALREADY_EXCEEDED"),
        "daily_loss_cost": benefit.daily_loss_cost if benefit else None,
        "net_benefit": run.result_net_benefit,
    }


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """GET /api/notifications/ (specs/19 §1.4)."""

    queryset = Notification.objects.select_related("unit")
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        if (unread := self.request.query_params.get("unread")) is not None:
            qs = qs.filter(is_read=unread.lower() not in {"0", "false", "no"})
        if unit_id := self.request.query_params.get("unit_id"):
            qs = qs.filter(unit_id=unit_id)
        return qs

    def list(self, request: Request, *args, **kwargs) -> Response:
        response = super().list(request, *args, **kwargs)
        response.data["unread_count"] = Notification.objects.filter(is_read=False).count()
        return response

    @action(detail=True, methods=["post"], url_path="read")
    def mark_read(self, request: Request, pk: str | None = None) -> Response:
        notification = self.get_object()
        notification.is_read = True
        notification.save(update_fields=["is_read"])
        return Response(NotificationSerializer(notification).data)

    @action(detail=False, methods=["post"], url_path="read-all")
    def mark_all_read(self, request: Request) -> Response:
        updated = Notification.objects.filter(is_read=False).update(is_read=True)
        return Response({"updated": updated})
