"""사용자 관리 API (specs/15 §3, specs/01 §5).

삭제는 **비활성화(soft delete)가 기본**이고, 분석 이력이 없는 계정만 물리 삭제할 수 있다.
마지막 활성 관리자는 삭제·비활성화·역할 변경이 모두 막힌다.
"""

from __future__ import annotations

from django.db.models import Q
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from accounts.models import LoginHistory, Role, User
from accounts.permissions import IsAdminRole
from accounts.serializers import (
    LoginHistorySerializer,
    ResetPasswordSerializer,
    UserListSerializer,
    UserSerializer,
)
from common import audit
from common.audit import AuditedModelMixin
from common.exceptions import Conflict, LastAdminProtected
from common.models import AuditAction

TARGET_USER = "User"


def last_active_admin(exclude_pk: int | None = None) -> bool:
    """이 사용자가 마지막 활성 관리자인지."""
    queryset = User.objects.filter(role=Role.ADMIN, is_active=True)
    if exclude_pk is not None:
        queryset = queryset.exclude(pk=exclude_pk)
    return not queryset.exists()


class UserViewSet(AuditedModelMixin, viewsets.ModelViewSet):
    queryset = User.objects.all()
    permission_classes = [IsAdminRole]
    search_fields = ["employee_no", "full_name"]
    ordering_fields = ["employee_no", "full_name", "last_login_at", "created_at"]
    audit_target_type = TARGET_USER

    def get_serializer_class(self):
        return UserListSerializer if self.action == "list" else UserSerializer

    def audit_label(self, instance) -> str:
        return f"{instance.full_name}({instance.employee_no})"

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        if role := params.get("role"):
            queryset = queryset.filter(role=role)
        if (flag := params.get("is_active")) is not None:
            queryset = queryset.filter(is_active=flag.lower() in {"1", "true", "yes"})
        if search := params.get("search"):
            queryset = queryset.filter(
                Q(employee_no__icontains=search) | Q(full_name__icontains=search)
            )
        return queryset

    def perform_update(self, serializer) -> None:
        instance = self.get_object()
        data = serializer.validated_data
        becoming_non_admin = data.get("role", instance.role) != Role.ADMIN
        becoming_inactive = data.get("is_active", instance.is_active) is False

        if instance.role == Role.ADMIN and instance.is_active:
            if (becoming_non_admin or becoming_inactive) and last_active_admin(instance.pk):
                raise LastAdminProtected()

        # 자기 자신의 역할을 낮출 수 없다 (specs/01 §5)
        if instance.pk == self.request.user.pk and becoming_non_admin:
            raise Conflict(
                code="CANNOT_DEMOTE_SELF",
                message="자기 자신의 역할을 일반 사용자로 낮출 수 없습니다.",
            )

        super().perform_update(serializer)

    def destroy(self, request: Request, *args, **kwargs) -> Response:
        """기본은 비활성화. `?hard=true` 이고 이력이 없을 때만 물리 삭제한다."""
        instance = self.get_object()

        if instance.role == Role.ADMIN and instance.is_active and last_active_admin(instance.pk):
            raise LastAdminProtected()
        if instance.pk == request.user.pk:
            raise Conflict(
                code="CANNOT_DELETE_SELF", message="자기 자신의 계정은 삭제할 수 없습니다."
            )

        hard = request.query_params.get("hard", "").lower() in {"1", "true", "yes"}
        if hard:
            if instance.analysis_runs.exists():
                raise Conflict(
                    code="USER_HAS_HISTORY",
                    message=(
                        "분석 이력이 있는 계정은 물리 삭제할 수 없습니다. " "비활성화를 사용하세요."
                    ),
                )
            self.perform_destroy(instance)
            return Response(status=status.HTTP_204_NO_CONTENT)

        before = audit.snapshot(instance)
        instance.is_active = False
        instance.save(update_fields=["is_active", "updated_at"])
        audit.record(
            request=request,
            action=AuditAction.UPDATE,
            target_type=TARGET_USER,
            target_id=instance.pk,
            target_label=self.audit_label(instance),
            before={"is_active": before.get("is_active")},
            after={"is_active": False},
        )
        return Response(
            {"deactivated": True, "note": "비활성화했습니다. 물리 삭제는 ?hard=true 로 요청하세요."}
        )

    @action(detail=True, methods=["post"], url_path="reset-password")
    def reset_password(self, request: Request, pk: str | None = None) -> Response:
        """관리자가 새 비밀번호를 지정한다 → must_change_password=True."""
        user = self.get_object()
        serializer = ResetPasswordSerializer(data=request.data)
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
    """GET /api/login-histories/ (관리자) — specs/01 §7."""

    queryset = LoginHistory.objects.select_related("user")
    serializer_class = LoginHistorySerializer
    permission_classes = [IsAdminRole]
    search_fields = ["attempted_employee_no"]
    ordering_fields = ["created_at"]

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        if (flag := params.get("success")) is not None:
            queryset = queryset.filter(success=flag.lower() in {"1", "true", "yes"})
        if employee_no := params.get("employee_no"):
            queryset = queryset.filter(attempted_employee_no__icontains=employee_no)
        return queryset
