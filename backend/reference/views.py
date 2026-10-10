"""참조 데이터 관리자 API (specs/06, specs/10 §6). 전부 관리자 전용이다."""

from __future__ import annotations

from django.http import HttpResponse
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response

from accounts.permissions import IsAdminRole
from calculator import runner
from common import audit
from common.audit import AuditedModelMixin
from common.exceptions import Conflict, ValidationError
from common.models import AuditAction
from reference import services
from reference.models import CalcParameterSet, CleaningMethod, GtModel, SmpPrice
from reference.param_defs import describe
from reference.serializers import (
    CalcParameterSetSerializer,
    CleaningMethodSerializer,
    GtModelSerializer,
    ParamsInputSerializer,
    SmpPriceSerializer,
)

MAX_IMPORT_MB = 5
XLSX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class DeactivateOnDeleteMixin:
    """참조값은 지우지 않고 사용 중지한다(specs/06). 과거 결과가 가리키던 대상이 사라지지 않게."""

    def perform_destroy(self, instance) -> None:
        if not instance.is_active:
            return
        instance.is_active = False
        instance.save(update_fields=["is_active", "updated_at"])
        audit.record(
            request=self.request,
            action=AuditAction.UPDATE,
            target_type=self.audit_target_type,
            target_id=instance.pk,
            target_label=str(instance),
            before={"is_active": True},
            after={"is_active": False},
        )


# DeactivateOnDeleteMixin 을 먼저 둔다 — AuditedModelMixin 의 삭제 기록(DELETE)보다 앞서야
# 비활성화만 남는다.
class GtModelViewSet(DeactivateOnDeleteMixin, AuditedModelMixin, viewsets.ModelViewSet):
    queryset = GtModel.objects.all()
    serializer_class = GtModelSerializer
    permission_classes = [IsAdminRole]
    pagination_class = None
    audit_target_type = "GtModel"

    def get_queryset(self):
        queryset = super().get_queryset()
        if (flag := self.request.query_params.get("is_active")) is not None:
            queryset = queryset.filter(is_active=flag.lower() in {"1", "true", "yes"})
        return queryset

    @action(detail=False, methods=["get"])
    def template(self, request: Request) -> HttpResponse:
        response = HttpResponse(services.gt_template_xlsx(), content_type=XLSX_CONTENT_TYPE)
        response["Content-Disposition"] = 'attachment; filename="gt_models.xlsx"'
        return response

    @action(detail=False, methods=["post"], parser_classes=[MultiPartParser], url_path="import")
    def import_xlsx(self, request: Request) -> Response:
        upload = request.FILES.get("file")
        if upload is None:
            raise ValidationError(message="xlsx 파일을 선택해 주세요.", code="FILE_REQUIRED")
        if not upload.name.lower().endswith(".xlsx"):
            raise ValidationError(message="xlsx 파일만 가져올 수 있습니다.", code="INVALID_FILE")
        if upload.size > MAX_IMPORT_MB * 1024 * 1024:
            raise ValidationError(message=f"{MAX_IMPORT_MB}MB 이하 파일만 가져올 수 있습니다.")

        counts = services.import_gt_models(upload.read())
        audit.record(
            request=request,
            action=AuditAction.UPDATE,
            target_type=self.audit_target_type,
            target_label=f"xlsx 가져오기({upload.name})",
            after=counts,
        )
        return Response(counts)


class CleaningMethodViewSet(DeactivateOnDeleteMixin, AuditedModelMixin, viewsets.ModelViewSet):
    queryset = CleaningMethod.objects.all()
    serializer_class = CleaningMethodSerializer
    permission_classes = [IsAdminRole]
    pagination_class = None
    audit_target_type = "CleaningMethod"


class SmpPriceViewSet(
    AuditedModelMixin,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """SMP 이력. 수정은 하지 않고 새 기준일로 등록한다(이력 보존)."""

    queryset = SmpPrice.objects.select_related("created_by")
    serializer_class = SmpPriceSerializer
    permission_classes = [IsAdminRole]
    audit_target_type = "SmpPrice"

    def perform_create(self, serializer) -> None:
        serializer.validated_data["created_by"] = self.request.user
        super().perform_create(serializer)


class CalcParameterSetViewSet(viewsets.ReadOnlyModelViewSet):
    """버전 목록·새 버전·되돌리기·미리보기 (specs/06 REF-5)."""

    queryset = CalcParameterSet.objects.select_related("created_by")
    serializer_class = CalcParameterSetSerializer
    permission_classes = [IsAdminRole]
    pagination_class = None

    def list(self, request: Request, *args, **kwargs) -> Response:
        response = super().list(request, *args, **kwargs)
        return Response({"definitions": describe(), "results": response.data})

    def create(self, request: Request) -> Response:
        serializer = ParamsInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        before = CalcParameterSet.objects.filter(is_active=True).first()
        param_set = services.create_param_version(
            serializer.validated_data["params"],
            note=serializer.validated_data["note"],
            user=request.user,
        )
        audit.record(
            request=request,
            action=AuditAction.CREATE,
            target_type="CalcParameterSet",
            target_id=param_set.pk,
            target_label=param_set.version_label,
            before={"version": before.version_label, "params": before.params} if before else None,
            after={"version": param_set.version_label, "params": param_set.params},
        )
        return Response(CalcParameterSetSerializer(param_set).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def activate(self, request: Request, pk: str | None = None) -> Response:
        param_set = self.get_object()
        if param_set.is_active:
            raise Conflict(code="ALREADY_ACTIVE", message="이미 활성 버전입니다.")
        before = CalcParameterSet.objects.filter(is_active=True).first()
        services.activate_param_version(param_set)
        audit.record(
            request=request,
            action=AuditAction.ACTIVATE,
            target_type="CalcParameterSet",
            target_id=param_set.pk,
            target_label=param_set.version_label,
            before={"active": before.version_label if before else None},
            after={"active": param_set.version_label},
        )
        return Response(CalcParameterSetSerializer(param_set).data)

    @action(detail=False, methods=["post"])
    def preview(self, request: Request) -> Response:
        """후보 파라미터로 예시 입력을 계산해 현재 활성값과 나란히 보여 준다(저장하지 않는다)."""
        serializer = ParamsInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(runner.preview_params(serializer.validated_data["params"]))
