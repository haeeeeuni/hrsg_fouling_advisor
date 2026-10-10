"""사용자 관리·가입 승인 API (specs/01 §4·§7, specs/10 §6).

사용자 생성은 회원가입으로만 한다. 삭제는 **비활성화(soft delete)가 기본**이다.
마지막 활성 관리자는 삭제·비활성화·역할 변경이 모두 막힌다.
"""

from __future__ import annotations

from django.db.models import Q
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import ApprovalStatus, LoginHistory, Role, User
from accounts.permissions import IsAdminRole
from accounts.serializers import (
    AdminUserSerializer,
    LoginHistorySerializer,
    RejectSerializer,
    ResetPasswordSerializer,
)
from accounts.services import approve, has_activity, is_last_active_admin, reject
from common import audit
from common.audit import AuditedModelMixin
from common.exceptions import Conflict, LastAdminProtected
from common.models import AuditAction

TARGET_USER = "User"
TRUTHY = {"1", "true", "yes"}


class UserViewSet(
    AuditedModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    queryset = User.objects.select_related("approved_by")
    serializer_class = AdminUserSerializer
    permission_classes = [IsAdminRole]
    ordering_fields = ["username", "full_name", "last_login_at", "created_at"]
    audit_target_type = TARGET_USER

    def audit_label(self, instance) -> str:
        return f"{instance.full_name}({instance.username})"

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        if role := params.get("role"):
            queryset = queryset.filter(role=role)
        if approval := params.get("approval_status"):
            queryset = queryset.filter(approval_status=approval)
        if (flag := params.get("is_active")) is not None:
            queryset = queryset.filter(is_active=flag.lower() in TRUTHY)
        if search := params.get("search"):
            queryset = queryset.filter(
                Q(username__icontains=search)
                | Q(full_name__icontains=search)
                | Q(organization__icontains=search)
            )
        return queryset

    def perform_update(self, serializer) -> None:
        instance = self.get_object()
        data = serializer.validated_data
        becoming_non_admin = data.get("role", instance.role) != Role.ADMIN
        becoming_inactive = data.get("is_active", instance.is_active) is False

        if (becoming_non_admin or becoming_inactive) and is_last_active_admin(instance):
            raise LastAdminProtected()

        # 자기 자신의 역할을 낮출 수 없다 (specs/01 AUTH-11)
        if instance.pk == self.request.user.pk and becoming_non_admin:
            raise Conflict(
                code="CANNOT_DEMOTE_SELF",
                message="자기 자신의 역할을 일반 사용자로 낮출 수 없습니다.",
            )

        super().perform_update(serializer)

    def destroy(self, request: Request, *args, **kwargs) -> Response:
        """기본은 비활성화. `?hard=true` 이고 활동 기록이 없을 때만 물리 삭제한다."""
        instance = self.get_object()

        if is_last_active_admin(instance):
            raise LastAdminProtected()
        if instance.pk == request.user.pk:
            raise Conflict(
                code="CANNOT_DELETE_SELF", message="자기 자신의 계정은 삭제할 수 없습니다."
            )

        if request.query_params.get("hard", "").lower() in TRUTHY:
            if has_activity(instance):
                raise Conflict(
                    code="USER_HAS_HISTORY",
                    message=(
                        "활동 기록이 있는 계정은 물리 삭제할 수 없습니다. 비활성화를 사용하세요."
                    ),
                )
            self.perform_destroy(instance)
            return Response(status=status.HTTP_204_NO_CONTENT)

        was_active = instance.is_active
        instance.is_active = False
        instance.save(update_fields=["is_active", "updated_at"])
        audit.record(
            request=request,
            action=AuditAction.UPDATE,
            target_type=TARGET_USER,
            target_id=instance.pk,
            target_label=self.audit_label(instance),
            before={"is_active": was_active},
            after={"is_active": False},
        )
        return Response(
            {"deactivated": True, "note": "비활성화했습니다. 물리 삭제는 ?hard=true 로 요청하세요."}
        )

    @action(detail=True, methods=["post"])
    def approve(self, request: Request, pk: str | None = None) -> Response:
        """승인 대기·반려 → 승인 (specs/01 AUTH-4·AUTH-5)."""
        user = self.get_object()
        if user.approval_status == ApprovalStatus.APPROVED:
            raise Conflict(code="ALREADY_APPROVED", message="이미 승인된 사용자입니다.")

        before = user.approval_status
        approve(user, by=request.user)
        audit.record(
            request=request,
            action=AuditAction.APPROVE,
            target_type=TARGET_USER,
            target_id=user.pk,
            target_label=self.audit_label(user),
            before={"approval_status": before},
            after={"approval_status": user.approval_status},
        )
        return Response(AdminUserSerializer(user).data)

    @action(detail=True, methods=["post"])
    def reject(self, request: Request, pk: str | None = None) -> Response:
        """승인 대기 → 반려. 사유 필수 (specs/01 AUTH-4)."""
        user = self.get_object()
        if user.approval_status != ApprovalStatus.PENDING:
            raise Conflict(
                code="NOT_PENDING", message="승인 대기 중인 사용자만 반려할 수 있습니다."
            )
        serializer = RejectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        reject(user, by=request.user, reason=serializer.validated_data["reason"])
        audit.record(
            request=request,
            action=AuditAction.REJECT,
            target_type=TARGET_USER,
            target_id=user.pk,
            target_label=self.audit_label(user),
            before={"approval_status": ApprovalStatus.PENDING},
            after={"approval_status": user.approval_status, "reason": user.rejection_reason},
        )
        return Response(AdminUserSerializer(user).data)

    @action(detail=True, methods=["post"], url_path="reset-password")
    def reset_password(self, request: Request, pk: str | None = None) -> Response:
        """관리자가 새 비밀번호를 지정한다 → must_change_password=True."""
        user = self.get_object()
        serializer = ResetPasswordSerializer(data=request.data, context={"user": user})
        serializer.is_valid(raise_exception=True)

        user.set_password(serializer.validated_data["new_password"])
        user.must_change_password = True
        user.save(update_fields=["password", "must_change_password", "updated_at"])

        # 비밀번호는 감사 로그에도 남기지 않는다 (AGENTS.md §7)
        audit.record(
            request=request,
            action=AuditAction.UPDATE,
            target_type=TARGET_USER,
            target_id=user.pk,
            target_label=self.audit_label(user),
            after={"password_reset": True, "must_change_password": True},
        )
        return Response({"reset": True, "must_change_password": True})


class LoginHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    """GET /api/admin/login-histories/"""

    queryset = LoginHistory.objects.select_related("user")
    serializer_class = LoginHistorySerializer
    permission_classes = [IsAdminRole]
    ordering_fields = ["created_at"]

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        if (flag := params.get("success")) is not None:
            queryset = queryset.filter(success=flag.lower() in TRUTHY)
        if username := params.get("username"):
            queryset = queryset.filter(attempted_username__icontains=username)
        return queryset


class AdminOverviewView(APIView):
    """GET /api/admin/overview/ — 관리자가 지금 손봐야 할 것 (specs/08 ADM-3).

    마일스톤마다 항목이 늘어난다(색인 실패, LLM 키, 임시값 등).
    """

    permission_classes = [IsAdminRole]

    def get(self, request: Request) -> Response:
        return Response(
            {
                "pending_signups": User.objects.filter(
                    approval_status=ApprovalStatus.PENDING
                ).count(),
            }
        )
