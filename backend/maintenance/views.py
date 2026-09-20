"""정비·세정 이력 API (specs/15 §7)."""

from __future__ import annotations

import uuid
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from accounts.permissions import IsAdminRole
from common import jobs
from common.exceptions import Conflict, NotFound, ValidationError
from ingestion.models import BatchStatus, UploadBatch, UploadKind
from maintenance import tasks
from maintenance.models import (
    CleaningEvent,
    CleaningSource,
    FoulingKeyword,
    MaintenanceRecord,
    ReviewStatus,
)
from maintenance.serializers import (
    AcceptRecordSerializer,
    CleaningEventSerializer,
    FoulingKeywordSerializer,
    MaintenanceRecordSerializer,
    MaintenanceUploadSerializer,
)
from maintenance.services import extractor
from maintenance.services.keywords import DEFAULT_KEYWORDS
from units.models import Unit

ALLOWED_SUFFIXES = {".csv", ".xlsx", ".xls"}


class CleaningEventViewSet(viewsets.ModelViewSet):
    queryset = CleaningEvent.objects.select_related("unit", "created_by")
    serializer_class = CleaningEventSerializer
    ordering_fields = ["cleaned_at", "created_at"]

    def get_permissions(self):
        if self.action in {"list", "retrieve"}:
            return [IsAuthenticated()]
        return [IsAdminRole()]

    def get_queryset(self):
        qs = super().get_queryset()
        if unit_id := self.request.query_params.get("unit_id"):
            qs = qs.filter(unit_id=unit_id)
        return qs

    def perform_create(self, serializer) -> None:
        serializer.save(created_by=self.request.user, source=CleaningSource.MANUAL)

    def create(self, request: Request, *args, **kwargs) -> Response:
        response = super().create(request, *args, **kwargs)
        data = response.data
        duplicates = (
            CleaningEvent.objects.filter(
                unit_id=data["unit"], cleaned_at__date=str(data["cleaned_at"])[:10]
            )
            .exclude(pk=data["id"])
            .count()
        )
        if duplicates:
            response.data = {
                **data,
                "warning": "같은 호기에 동일 일자의 세정 이력이 이미 있습니다.",
            }
        return response

    def destroy(self, request: Request, *args, **kwargs) -> Response:
        """삭제해도 **과거 분석 결과의 수치는 변하지 않는다** (AC-10-5).

        분석 결과는 실행 당시 스냅샷을 그대로 보관하기 때문이다.
        """
        event = self.get_object()
        impact = {
            "comparisons": event.comparisons.count(),
            "source_records": event.source_records.count(),
        }
        response = super().destroy(request, *args, **kwargs)
        response.data = {
            "deleted": True,
            "impact": impact,
            "note": (
                "청정 기준 기간 산정, 추세 구간 절단, 전후 비교, 대시보드 마커에 영향을 줍니다. "
                "과거 분석 결과의 수치는 그대로 유지됩니다."
            ),
        }
        response.status_code = status.HTTP_200_OK
        return response


class MaintenanceRecordViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = MaintenanceRecord.objects.select_related("unit")
    serializer_class = MaintenanceRecordSerializer
    permission_classes = [IsAuthenticated]
    ordering_fields = ["work_date", "match_score"]
    search_fields = ["title", "description"]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        if unit_id := params.get("unit_id"):
            qs = qs.filter(unit_id=unit_id)
        if (flag := params.get("is_fouling_related")) is not None:
            qs = qs.filter(is_fouling_related=flag.lower() in {"1", "true", "yes"})
        if review := params.get("review_status"):
            qs = qs.filter(review_status=review)
        return qs

    @action(detail=True, methods=["post"])
    def accept(self, request: Request, pk: str | None = None) -> Response:
        """세정 이벤트로 등록한다 — 승인 전에는 등록되지 않는다 (AC-10-2)."""
        record = self.get_object()
        if record.review_status == ReviewStatus.ACCEPTED:
            raise Conflict(message="이미 승인된 이력입니다.")

        serializer = AcceptRecordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        with transaction.atomic():
            event = CleaningEvent.objects.create(
                unit=record.unit,
                cleaned_at=timezone.make_aware(
                    timezone.datetime.combine(record.work_date, timezone.datetime.min.time())
                ),
                cleaned_end_at=data.get("cleaned_end_at"),
                method=data.get("method")
                or extractor.guess_method(record.title, record.description),
                method_detail=record.title[:200],
                cost=data.get("cost") if data.get("cost") is not None else record.cost,
                outage_days=(
                    data.get("outage_days")
                    if data.get("outage_days") is not None
                    else record.duration_days
                ),
                source=CleaningSource.EXTRACTED,
                maintenance_record=record,
                note=record.description[:2000],
                created_by=request.user,
            )
            record.review_status = ReviewStatus.ACCEPTED
            record.cleaning_event = event
            record.save(update_fields=["review_status", "cleaning_event"])

        return Response(CleaningEventSerializer(event).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def ignore(self, request: Request, pk: str | None = None) -> Response:
        record = self.get_object()
        record.review_status = ReviewStatus.IGNORED
        record.save(update_fields=["review_status"])
        return Response(MaintenanceRecordSerializer(record).data)

    @action(detail=False, methods=["post"], url_path="re-extract", permission_classes=[IsAdminRole])
    def re_extract(self, request: Request) -> Response:
        """키워드 사전 변경 후 재추출 (관리자)."""
        unit_id = request.data.get("unit_id")
        return Response(tasks.re_extract(unit_id=unit_id))


class MaintenanceUploadView(viewsets.ViewSet):
    """POST /api/uploads/maintenance/ (specs/15 §5)."""

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def create(self, request: Request) -> Response:
        serializer = MaintenanceUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        unit = Unit.objects.filter(pk=data["unit_id"]).first()
        if unit is None:
            raise NotFound(message="호기를 찾을 수 없습니다.")

        upload = data["file"]
        if Path(upload.name).suffix.lower() not in ALLOWED_SUFFIXES:
            raise ValidationError(
                code="UNSUPPORTED_FILE_TYPE",
                message="정비 이력은 CSV 또는 엑셀(.xlsx, .xls) 파일만 업로드할 수 있습니다.",
            )

        root = Path(settings.UPLOAD_ROOT)
        root.mkdir(parents=True, exist_ok=True)
        path = root / f"{uuid.uuid4().hex}{Path(upload.name).suffix.lower()}"
        with path.open("wb") as fp:
            for block in upload.chunks():
                fp.write(block)

        batch = UploadBatch.objects.create(
            unit=unit,
            kind=UploadKind.MAINTENANCE,
            uploaded_by=request.user,
            original_filename=upload.name[:255],
            stored_path=str(path),
            file_size_bytes=upload.size,
            status=BatchStatus.PENDING,
        )

        job_id = jobs.enqueue(
            tasks.import_maintenance,
            batch_id=batch.id,
            sheet=data.get("sheet") or None,
            mapping=data.get("mapping") or None,
        )
        return Response(
            {"job_id": job_id, "status": jobs.RUNNING, "batch_id": batch.id},
            status=status.HTTP_202_ACCEPTED,
        )


class FoulingKeywordViewSet(viewsets.ModelViewSet):
    """오염 키워드 사전 (관리자 전용, FR-A-07)."""

    queryset = FoulingKeyword.objects.all()
    serializer_class = FoulingKeywordSerializer
    permission_classes = [IsAdminRole]
    search_fields = ["keyword"]

    def get_queryset(self):
        qs = super().get_queryset()
        if category := self.request.query_params.get("category"):
            qs = qs.filter(category=category)
        return qs

    def perform_create(self, serializer) -> None:
        serializer.save(created_by=self.request.user)

    @action(detail=False, methods=["post"], url_path="restore-defaults")
    def restore_defaults(self, request: Request) -> Response:
        """기본 시드 복원 (specs/10 §7 — 사전이 비었을 때 되살린다)."""
        existing = set(FoulingKeyword.objects.values_list("keyword", "category"))
        rows = [
            FoulingKeyword(keyword=keyword, category=category, created_by=request.user)
            for keyword, category in DEFAULT_KEYWORDS
            if (keyword, category) not in existing
        ]
        FoulingKeyword.objects.bulk_create(rows)
        return Response({"restored": len(rows), "total": FoulingKeyword.objects.count()})
