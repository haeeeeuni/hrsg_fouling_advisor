"""체크리스트 API (specs/10 §5·§6).

요청 건은 **만든 사람만** 본다(CHK-4). 남의 요청 건은 404 — 존재 여부도 알리지 않는다(specs/10 §1).
"""

from __future__ import annotations

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response

from accounts.permissions import IsAdminRole
from checklist import rules, services
from checklist.models import ChecklistTemplateItem, DataRequest, RequestStatus
from checklist.serializers import (
    ItemUpdateSerializer,
    RequestDetailSerializer,
    RequestItemSerializer,
    RequestSerializer,
    TemplateItemSerializer,
)
from common import audit
from common.audit import AuditedModelMixin, DeactivateOnDeleteMixin
from common.exceptions import ValidationError
from common.models import AuditAction

XLSX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
MAX_IMPORT_MB = 5


class DataRequestViewSet(viewsets.ModelViewSet):
    serializer_class = RequestSerializer

    def get_queryset(self):
        queryset = DataRequest.objects.filter(owner=self.request.user)
        status_filter = self.request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        elif self.action == "list":
            # 보관한 건은 기본 목록에서 숨긴다. ?status=ARCHIVED 로 따로 본다.
            queryset = queryset.exclude(status=RequestStatus.ARCHIVED)
        return queryset

    def get_serializer_class(self):
        return RequestDetailSerializer if self.action == "retrieve" else RequestSerializer

    def create(self, request: Request) -> Response:
        serializer = RequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        created = services.create_request(
            owner=request.user,
            title=data["title"],
            memo=data.get("memo", ""),
            due_date=data.get("due_date"),
        )
        return Response(RequestDetailSerializer(created).data, status=status.HTTP_201_CREATED)

    def perform_update(self, serializer) -> None:
        previous = serializer.instance.status
        instance = serializer.save()
        # 보관 해제는 체크 상태에 맞게 진행 중·완료로 되돌린다.
        if previous == RequestStatus.ARCHIVED and instance.status != RequestStatus.ARCHIVED:
            instance.status = RequestStatus.IN_PROGRESS
            instance.save(update_fields=["status"])
            services.refresh_status(instance)
        elif instance.status != RequestStatus.ARCHIVED:
            services.refresh_status(instance)

    @action(detail=True, methods=["patch"], url_path=r"items/(?P<item_id>\d+)")
    def update_item(self, request: Request, pk: str | None = None, item_id: str | None = None):
        data_request = self.get_object()
        item = get_object_or_404(data_request.items, pk=item_id)
        serializer = ItemUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.update_item(
            item,
            state=serializer.validated_data.get("state"),
            memo=serializer.validated_data.get("memo"),
        )
        data_request.refresh_from_db()
        return Response(
            {
                "item": RequestItemSerializer(item).data,
                "request": RequestSerializer(data_request).data,
            }
        )

    @action(detail=True, methods=["post"], url_path="sync-template")
    def sync_template(self, request: Request, pk: str | None = None) -> Response:
        data_request = self.get_object()
        added = services.sync_template(data_request)
        data_request.refresh_from_db()
        return Response({"added": added, "request": RequestDetailSerializer(data_request).data})

    @action(detail=True, methods=["get"], url_path="email-text")
    def email_text(self, request: Request, pk: str | None = None) -> Response:
        lang = request.query_params.get("lang", rules.LANG_KO)
        scope = request.query_params.get("scope", rules.SCOPE_PENDING)
        if lang not in (rules.LANG_KO, rules.LANG_EN) or scope not in (
            rules.SCOPE_PENDING,
            rules.SCOPE_ALL,
        ):
            raise ValidationError(message="lang 은 ko·en, scope 는 pending·all 중 하나여야 합니다.")
        return Response({"text": services.email_text(self.get_object(), lang=lang, scope=scope)})


class TemplateItemViewSet(DeactivateOnDeleteMixin, AuditedModelMixin, viewsets.ModelViewSet):
    """관리자 — 항목 템플릿 (specs/07 CHK-6). 삭제는 사용 중지다."""

    queryset = ChecklistTemplateItem.objects.all().order_by("order", "id")
    serializer_class = TemplateItemSerializer
    permission_classes = [IsAdminRole]
    pagination_class = None
    audit_target_type = "ChecklistTemplateItem"

    def perform_create(self, serializer) -> None:
        if serializer.validated_data.get("order") in (None, 0):
            serializer.validated_data["order"] = services.next_order()
        super().perform_create(serializer)

    @action(detail=False, methods=["post"])
    def reorder(self, request: Request) -> Response:
        """{"ids": [...]} 순서대로 10, 20, 30 … 을 매긴다."""
        ids = request.data.get("ids")
        if not isinstance(ids, list) or not ids:
            raise ValidationError(message="ids 목록이 필요합니다.")
        items = {item.id: item for item in ChecklistTemplateItem.objects.filter(pk__in=ids)}
        if len(items) != len(set(ids)):
            raise ValidationError(message="없는 항목이 섞여 있습니다.")
        for index, item_id in enumerate(ids, start=1):
            items[item_id].order = index * 10
        ChecklistTemplateItem.objects.bulk_update(items.values(), ["order"])
        audit.record(
            request=request,
            action=AuditAction.UPDATE,
            target_type=self.audit_target_type,
            target_label="순서 변경",
            after={"ids": ids},
        )
        return Response(TemplateItemSerializer(self.get_queryset(), many=True).data)

    @action(detail=False, methods=["get"])
    def export(self, request: Request) -> HttpResponse:
        response = HttpResponse(services.export_template_xlsx(), content_type=XLSX_CONTENT_TYPE)
        response["Content-Disposition"] = 'attachment; filename="checklist_items.xlsx"'
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
        counts = services.import_template_xlsx(upload.read())
        audit.record(
            request=request,
            action=AuditAction.UPDATE,
            target_type=self.audit_target_type,
            target_label=f"xlsx 가져오기({upload.name})",
            after=counts,
        )
        return Response(counts)
