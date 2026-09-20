"""호기·컬럼 매핑 API (specs/15 §4)."""

from __future__ import annotations

import tempfile
from pathlib import Path

from django.db import transaction
from django.db.models import Max
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsAdminRole
from common import audit
from common.audit import AuditedModelMixin
from common.exceptions import Conflict, ValidationError
from common.models import AuditAction
from ingestion.models import Measurement
from ingestion.services import reader
from ingestion.services.transform import apply_mapping, mapping_specs_from_rows
from units.models import ColumnMapping, ColumnMappingVersion, Unit
from units.serializers import (
    ColumnMappingBulkSerializer,
    ColumnMappingSerializer,
    ColumnMappingVersionSerializer,
    MappingPreviewRequestSerializer,
    StandardFieldSerializer,
    UnitSerializer,
)

PREVIEW_ROWS = 20


class StandardFieldListView(APIView):
    """GET /api/standard-fields/ — 표준 항목 정의 (인증 사용자 전체)."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        data = StandardFieldSerializer(StandardFieldSerializer.all_fields(), many=True).data
        return Response(data)


class UnitViewSet(AuditedModelMixin, viewsets.ModelViewSet):
    queryset = Unit.objects.all().prefetch_related("column_mappings")
    serializer_class = UnitSerializer
    audit_target_type = "Unit"
    search_fields = ["code", "name", "plant_name"]
    ordering_fields = ["code", "name", "created_at"]

    def get_permissions(self):
        # 조회는 인증 사용자, 생성·수정·삭제는 관리자 (specs/15 §4)
        if self.action in {"list", "retrieve", "data_summary"}:
            return [IsAuthenticated()]
        return [IsAdminRole()]

    def get_queryset(self):
        qs = super().get_queryset()
        is_active = self.request.query_params.get("is_active")
        if is_active is not None:
            qs = qs.filter(is_active=is_active.lower() in {"1", "true", "yes"})
        return qs

    def audit_label(self, instance: Unit) -> str:
        return f"{instance.code} {instance.name}"

    def perform_destroy(self, instance: Unit) -> None:
        # 운전 데이터·분석 이력이 있으면 물리 삭제 불가 (specs/02 §2)
        if instance.measurements.exists() or instance.upload_batches.exists():
            raise Conflict(
                code="UNIT_HAS_DATA",
                message="데이터가 있는 호기는 삭제할 수 없습니다. 비활성화를 사용하세요.",
            )
        super().perform_destroy(instance)

    @action(detail=True, methods=["get"], url_path="data-summary")
    def data_summary(self, request: Request, pk: str | None = None) -> Response:
        """GET /api/units/{id}/data-summary/ — 누적 데이터 기간·행수."""
        unit = self.get_object()
        agg = Measurement.objects.filter(unit=unit).aggregate(
            first=Max("timestamp"), last=Max("timestamp")
        )
        first = (
            Measurement.objects.filter(unit=unit)
            .order_by("timestamp")
            .values_list("timestamp", flat=True)
            .first()
        )
        return Response(
            {
                "unit_id": unit.id,
                "row_count": Measurement.objects.filter(unit=unit).count(),
                "period": {"start": first, "end": agg["last"]},
                "is_mapping_complete": unit.is_mapping_complete,
                "last_upload_at": unit.upload_batches.order_by("-uploaded_at")
                .values_list("uploaded_at", flat=True)
                .first(),
            }
        )


class ColumnMappingView(APIView):
    """GET/PUT /api/units/{unit_id}/column-mappings/ (관리자)."""

    permission_classes = [IsAdminRole]

    def get(self, request: Request, unit_id: int) -> Response:
        unit = _get_unit(unit_id)
        return Response(
            {
                "mappings": ColumnMappingSerializer(unit.column_mappings.all(), many=True).data,
                "is_mapping_complete": unit.is_mapping_complete,
                "problems": unit.mapping_problems(),
            }
        )

    @transaction.atomic
    def put(self, request: Request, unit_id: int) -> Response:
        unit = _get_unit(unit_id)
        serializer = ColumnMappingBulkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        rows = serializer.validated_data["mappings"]

        unit.column_mappings.all().delete()
        ColumnMapping.objects.bulk_create([ColumnMapping(unit=unit, **row) for row in rows])

        # 변경 이력을 남긴다 — 과거 분석의 재현성을 위해 (specs/02 §5.5)
        next_version = (unit.mapping_versions.aggregate(m=Max("version"))["m"] or 0) + 1
        ColumnMappingVersion.objects.create(
            unit=unit,
            version=next_version,
            snapshot=ColumnMappingSerializer(unit.column_mappings.all(), many=True).data,
            created_by=request.user,
        )

        unit.refresh_from_db()
        audit.record(
            request=request,
            action=AuditAction.UPDATE,
            target_type="ColumnMapping",
            target_id=unit.id,
            target_label=f"{unit.code} 매핑 v{next_version}",
            before={"version": next_version - 1},
            after={"version": next_version, "mappings": rows},
        )
        return Response(
            {
                "mappings": ColumnMappingSerializer(unit.column_mappings.all(), many=True).data,
                "is_mapping_complete": unit.is_mapping_complete,
                "problems": unit.mapping_problems(),
                "version": next_version,
            }
        )


class ColumnMappingVersionListView(APIView):
    permission_classes = [IsAdminRole]

    def get(self, request: Request, unit_id: int) -> Response:
        unit = _get_unit(unit_id)
        versions = unit.mapping_versions.select_related("created_by")[:50]
        return Response(ColumnMappingVersionSerializer(versions, many=True).data)


class ColumnMappingPreviewView(APIView):
    """POST /api/units/{unit_id}/column-mappings/preview/ — 상위 20행 변환 미리보기."""

    permission_classes = [IsAdminRole]

    def post(self, request: Request, unit_id: int) -> Response:
        unit = _get_unit(unit_id)
        serializer = MappingPreviewRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        upload = serializer.validated_data["file"]

        rows = serializer.validated_data.get("mappings")
        if rows is None:
            rows = list(
                unit.column_mappings.values(
                    "standard_field",
                    "source_column",
                    "scale_factor",
                    "offset",
                    "bool_rule",
                    "bool_threshold",
                )
            )
        specs = mapping_specs_from_rows([dict(row) for row in rows])

        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
            for block in upload.chunks():
                tmp.write(block)
            tmp_path = Path(tmp.name)

        try:
            encoding = reader.detect_encoding(tmp_path)
            delimiter = reader.detect_delimiter(tmp_path, encoding)
            header = reader.read_header(tmp_path, encoding, delimiter)

            usecols = [s.source_column for s in specs if s.source_column in header]
            chunk = next(
                reader.iter_chunks(
                    tmp_path, encoding, delimiter, usecols=usecols, chunk_size=PREVIEW_ROWS
                ),
                None,
            )
            if chunk is None:
                raise ValidationError(message="미리볼 데이터 행이 없습니다.", code="EMPTY_FILE")

            converted = apply_mapping(chunk.head(PREVIEW_ROWS), specs)
            preview = [
                {
                    key: (None if _is_missing(value) else _jsonify(value))
                    for key, value in record.items()
                }
                for record in converted.to_dict(orient="records")
            ]
            return Response(
                {
                    "header": header,
                    "encoding": encoding,
                    "delimiter": delimiter,
                    "missing_source_columns": [
                        s.source_column for s in specs if s.source_column not in header
                    ],
                    "rows": preview,
                }
            )
        finally:
            tmp_path.unlink(missing_ok=True)


def _get_unit(unit_id: int) -> Unit:
    unit = Unit.objects.filter(pk=unit_id).first()
    if unit is None:
        from common.exceptions import NotFound

        raise NotFound(message="호기를 찾을 수 없습니다.")
    return unit


def _is_missing(value) -> bool:
    import pandas as pd

    return value is None or (not isinstance(value, bool) and pd.isna(value))


def _jsonify(value):
    import pandas as pd

    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, bool):
        return value
    return float(value) if isinstance(value, (int, float)) else value
