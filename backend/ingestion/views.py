"""업로드 API (specs/15 §5).

검증(validate)과 적재(commit)는 분리한다. 검증 통과 전에는 DB에 저장하지 않는다(specs/03 §2).
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

from django.conf import settings
from django.db import transaction
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from accounts.permissions import IsAdminRole
from common import jobs
from common.exceptions import Conflict, DomainError, NotFound, ValidationError
from ingestion import tasks
from ingestion.models import BatchStatus, Measurement, UploadBatch, UploadKind
from ingestion.serializers import (
    CommitSerializer,
    OperationUploadSerializer,
    UploadBatchListSerializer,
    UploadBatchSerializer,
)
from ingestion.services import reader
from units.models import Unit
from units.settings_resolver import get_setting

logger = logging.getLogger(__name__)


class FileTooLarge(DomainError):
    code = "FILE_TOO_LARGE"
    message = "파일 크기가 허용치를 초과했습니다."
    status_code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE


class UploadBatchViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = UploadBatch.objects.select_related("unit", "uploaded_by")
    permission_classes = [IsAuthenticated]
    ordering_fields = ["uploaded_at", "status"]

    def get_serializer_class(self):
        return UploadBatchListSerializer if self.action == "list" else UploadBatchSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        if unit_id := params.get("unit_id"):
            qs = qs.filter(unit_id=unit_id)
        if kind := params.get("kind"):
            qs = qs.filter(kind=kind)
        if batch_status := params.get("status"):
            qs = qs.filter(status=batch_status)
        return qs

    # --- 운전 데이터 검증 ---

    @action(
        detail=False,
        methods=["post"],
        url_path="operation/validate",
        parser_classes=[MultiPartParser, FormParser],
    )
    def validate_operation(self, request: Request) -> Response:
        serializer = OperationUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        unit = _get_unit(serializer.validated_data["unit_id"])
        upload = serializer.validated_data["file"]

        if not unit.is_active:
            raise ValidationError(message="비활성 호기에는 업로드할 수 없습니다.")
        if not unit.is_mapping_complete:
            raise ValidationError(
                code="UNIT_MAPPING_INCOMPLETE",
                message="컬럼 매핑이 완료되지 않은 호기입니다.",
                details={"problems": unit.mapping_problems()},
            )

        max_mb = get_setting("max_upload_mb", unit.id)
        if upload.size > max_mb * 1024 * 1024:
            raise FileTooLarge(details={"max_upload_mb": max_mb, "size_bytes": upload.size})

        if not str(upload.name).lower().endswith(".csv"):
            raise ValidationError(
                code="UNSUPPORTED_FILE_TYPE",
                message="운전 데이터는 .csv 파일만 업로드할 수 있습니다.",
            )

        stored_path = _store_upload(upload)
        checksum = reader.file_checksum(stored_path)

        # 같은 호기에 동일 파일 재업로드는 확인을 받는다 (specs/03 §5).
        if not serializer.validated_data.get("confirm_duplicate_file"):
            previous = UploadBatch.objects.filter(
                unit=unit, checksum=checksum, status=BatchStatus.LOADED
            ).first()
            if previous is not None:
                stored_path.unlink(missing_ok=True)
                raise Conflict(
                    code="DUPLICATE_FILE",
                    message="같은 파일이 이미 적재되어 있습니다. 계속하려면 확인이 필요합니다.",
                    details={
                        "previous_batch_id": previous.id,
                        "uploaded_at": str(previous.uploaded_at),
                    },
                )

        batch = UploadBatch.objects.create(
            unit=unit,
            kind=UploadKind.OPERATION,
            uploaded_by=request.user,
            original_filename=upload.name[:255],
            stored_path=str(stored_path),
            file_size_bytes=upload.size,
            checksum=checksum,
            status=BatchStatus.PENDING,
        )

        job_id = jobs.enqueue(tasks.validate_upload, batch_id=batch.id)
        return Response(
            {"job_id": job_id, "status": jobs.RUNNING, "batch_id": batch.id},
            status=status.HTTP_202_ACCEPTED,
        )

    # --- 적재 ---

    @action(detail=True, methods=["post"], url_path="commit")
    def commit(self, request: Request, pk: str | None = None) -> Response:
        batch = self.get_object()
        serializer = CommitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if batch.status != BatchStatus.VALIDATED:
            raise Conflict(
                code="VALIDATION_NOT_PASSED",
                message="검증을 통과한 배치만 적재할 수 있습니다.",
                details={"status": batch.status},
            )

        job_id = jobs.enqueue(
            tasks.commit_upload,
            batch_id=batch.id,
            duplicate_policy=serializer.validated_data["duplicate_policy"],
        )
        return Response(
            {"job_id": job_id, "status": jobs.RUNNING, "batch_id": batch.id},
            status=status.HTTP_202_ACCEPTED,
        )

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request: Request, pk: str | None = None) -> Response:
        batch = self.get_object()
        if batch.status == BatchStatus.LOADED:
            raise Conflict(message="이미 적재된 배치는 취소할 수 없습니다.")
        Path(batch.stored_path).unlink(missing_ok=True)
        batch.status = BatchStatus.CANCELED
        batch.save(update_fields=["status"])
        return Response(status=status.HTTP_204_NO_CONTENT)

    # --- 롤백 (관리자) ---

    def get_permissions(self):
        if self.action == "destroy":
            return [IsAdminRole()]
        return [IsAuthenticated()]

    @transaction.atomic
    def destroy(self, request: Request, *args, **kwargs) -> Response:
        """배치 롤백 — 해당 배치로 적재된 Measurement 를 삭제한다 (specs/03 §6)."""
        batch = self.get_object()
        deleted, _ = Measurement.objects.filter(upload_batch=batch).delete()
        Path(batch.stored_path).unlink(missing_ok=True)
        batch.status = BatchStatus.CANCELED
        batch.row_loaded = 0
        batch.save(update_fields=["status", "row_loaded"])
        logger.info("upload batch rolled back batch_id=%s rows=%s", batch.id, deleted)
        return Response({"deleted_rows": deleted}, status=status.HTTP_200_OK)


def _get_unit(unit_id: int) -> Unit:
    unit = Unit.objects.filter(pk=unit_id).first()
    if unit is None:
        raise NotFound(message="호기를 찾을 수 없습니다.")
    return unit


def _store_upload(upload) -> Path:
    """업로드 원본을 미디어 루트 밖 별도 경로에 저장한다 (specs/18 §2).

    원본 파일명은 로그·경로에 남기지 않고 UUID 로 저장한다(AGENTS.md §7).
    """
    root = Path(settings.UPLOAD_ROOT)
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{uuid.uuid4().hex}.csv"
    with path.open("wb") as fp:
        for block in upload.chunks():
            fp.write(block)
    return path
