"""모델 관리 API (specs/15 §11, specs/13 §5).

재학습은 비동기로 실행하고, **관리자가 승인해야 활성화된다**(AC-06-5).
승인 전까지 기존 활성 모델이 그대로 쓰인다.
"""

from __future__ import annotations

from django.db import transaction
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from accounts.permissions import IsAdminRole
from analysis import tasks_train
from analysis.models import CleanBaselinePeriod, ClusterDefinition, ModelVersion
from analysis.serializers import ModelVersionSerializer
from analysis.serializers_admin import (
    CleanBaselinePeriodSerializer,
    ClusterDefinitionSerializer,
    TrainRequestSerializer,
)
from common import audit, jobs
from common.audit import AuditedModelMixin
from common.exceptions import Conflict, NotFound
from common.models import AuditAction
from units.models import Unit

TARGET_MODEL_VERSION = "ModelVersion"


class ModelVersionViewSet(viewsets.ReadOnlyModelViewSet):
    """GET /api/model-versions/ + 재학습·활성화 (관리자)."""

    queryset = ModelVersion.objects.select_related("unit", "trained_by")
    serializer_class = ModelVersionSerializer
    permission_classes = [IsAdminRole]
    ordering_fields = ["trained_at", "version"]

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        if unit_id := params.get("unit_id"):
            queryset = queryset.filter(unit_id=unit_id)
        if target := params.get("target"):
            queryset = queryset.filter(target=target)
        if (flag := params.get("is_active")) is not None:
            queryset = queryset.filter(is_active=flag.lower() in {"1", "true", "yes"})
        return queryset

    @action(detail=False, methods=["post"])
    def train(self, request: Request) -> Response:
        """POST /api/model-versions/train/ → 202 + job_id."""
        serializer = TrainRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        unit = Unit.objects.filter(pk=data["unit_id"]).first()
        if unit is None:
            raise NotFound(message="호기를 찾을 수 없습니다.")

        job_id = jobs.enqueue(
            tasks_train.retrain_models,
            unit_id=unit.id,
            targets=data["targets"],
            algorithm=data.get("algorithm") or None,
            baseline_period_ids=data.get("baseline_period_ids") or None,
            user_id=request.user.pk,
        )
        audit.record(
            request=request,
            action=AuditAction.TRAIN,
            target_type=TARGET_MODEL_VERSION,
            target_id=unit.id,
            target_label=f"{unit.code} 재학습 요청",
            after={"targets": data["targets"], "algorithm": data.get("algorithm")},
        )
        return Response(
            {"job_id": job_id, "status": jobs.RUNNING, "unit_id": unit.id},
            status=status.HTTP_202_ACCEPTED,
        )

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def activate(self, request: Request, pk: str | None = None) -> Response:
        """승인된 모델만 활성화한다. 호기·타깃별로 1개만 활성이다."""
        version = self.get_object()
        if version.is_active:
            raise Conflict(message="이미 활성 상태입니다.")

        previous = ModelVersion.objects.filter(
            unit=version.unit, target=version.target, is_active=True
        ).first()

        ModelVersion.objects.filter(unit=version.unit, target=version.target).update(
            is_active=False
        )
        version.is_active = True
        version.save(update_fields=["is_active"])

        audit.record(
            request=request,
            action=AuditAction.ACTIVATE,
            target_type=TARGET_MODEL_VERSION,
            target_id=version.pk,
            target_label=f"{version.unit.code} {version.target} v{version.version}",
            before={"active_version": previous.version if previous else None},
            after={"active_version": version.version},
        )
        return Response(ModelVersionSerializer(version).data)

    @action(detail=True, methods=["get"])
    def compare(self, request: Request, pk: str | None = None) -> Response:
        """신·구 모델 지표 비교표 (specs/13 §5.2)."""
        version = self.get_object()
        current = ModelVersion.objects.filter(
            unit=version.unit, target=version.target, is_active=True
        ).first()
        return Response(
            {
                "candidate": ModelVersionSerializer(version).data,
                "current": ModelVersionSerializer(current).data if current else None,
            }
        )


class CleanBaselinePeriodViewSet(AuditedModelMixin, viewsets.ModelViewSet):
    """청정 기준 기간 (specs/13 §5.1). 기대값 모델의 학습 구간이다."""

    queryset = CleanBaselinePeriod.objects.select_related("unit", "cleaning_event")
    serializer_class = CleanBaselinePeriodSerializer
    permission_classes = [IsAdminRole]
    ordering_fields = ["start_at", "created_at"]
    audit_target_type = "CleanBaselinePeriod"

    def get_queryset(self):
        queryset = super().get_queryset()
        if unit_id := self.request.query_params.get("unit_id"):
            queryset = queryset.filter(unit_id=unit_id)
        return queryset

    def perform_create(self, serializer) -> None:
        # 등록자를 채운 뒤 믹스인이 감사 로그를 남기도록 한다.
        serializer.save(created_by=self.request.user)
        audit.record(
            request=self.request,
            action=AuditAction.CREATE,
            target_type=self.audit_target_type,
            target_id=serializer.instance.pk,
            target_label=str(serializer.instance),
            after=audit.snapshot(serializer.instance),
        )

    @action(detail=True, methods=["get"])
    def preview(self, request: Request, pk: str | None = None) -> Response:
        """지정 기간의 유효 포인트 수와 평균값 미리보기 (specs/13 §5.1)."""
        period = self.get_object()
        from django.db.models import Avg, Count

        from ingestion.models import Measurement

        stats = Measurement.objects.filter(
            unit=period.unit, timestamp__gte=period.start_at, timestamp__lt=period.end_at
        ).aggregate(
            count=Count("id"),
            avg_dp=Avg("hrsg_gas_dp_kpa"),
            avg_stack=Avg("stack_temp_c"),
            avg_power=Avg("gt_power_mw"),
        )
        return Response({"period_id": period.pk, **stats})


class ClusterDefinitionViewSet(AuditedModelMixin, viewsets.ModelViewSet):
    """군집 정의 (specs/15 §11)."""

    queryset = ClusterDefinition.objects.select_related("unit")
    serializer_class = ClusterDefinitionSerializer
    permission_classes = [IsAdminRole]
    ordering_fields = ["version", "created_at"]
    audit_target_type = "ClusterDefinition"

    def get_queryset(self):
        queryset = super().get_queryset()
        if unit_id := self.request.query_params.get("unit_id"):
            queryset = queryset.filter(unit_id=unit_id)
        return queryset
