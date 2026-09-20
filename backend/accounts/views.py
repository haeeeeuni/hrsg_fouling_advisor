"""인증 API (specs/15 §2).

View는 HTTP 입출력·권한·직렬화만 담당하고 도메인 로직은 services.py 에 둔다(AGENTS.md §3).
"""

import logging

from django.contrib.auth import login as django_login
from django.contrib.auth import logout as django_logout
from django.middleware.csrf import get_token
from django.views.decorators.debug import sensitive_post_parameters
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.serializers import ChangePasswordSerializer, LoginSerializer, MeSerializer
from accounts.services import (
    authenticate_user,
    check_lockout,
    mark_logged_in,
    record_attempt,
)
from common.constants import FAIL_INACTIVE, FAIL_LOCKED
from common.exceptions import AccountInactive, LoginFailed, LoginLocked

logger = logging.getLogger(__name__)


class CsrfView(APIView):
    """SPA 부팅 시 CSRF 쿠키를 받기 위한 엔드포인트."""

    permission_classes = [AllowAny]

    def get(self, request: Request) -> Response:
        return Response({"csrf_token": get_token(request._request)})


class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "login"  # specs/15 §13 — IP 기준 분당 10회

    @sensitive_post_parameters("password")
    def post(self, request: Request) -> Response:
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        employee_no = serializer.validated_data["employee_no"]
        full_name = serializer.validated_data["full_name"]
        password = serializer.validated_data["password"]

        lock = check_lockout(employee_no)
        if lock.locked:
            record_attempt(
                request._request,
                employee_no=employee_no,
                full_name_input=full_name,
                success=False,
                fail_reason=FAIL_LOCKED,
            )
            raise LoginLocked(details={"retry_after_sec": lock.retry_after_sec})

        user, fail_reason = authenticate_user(
            employee_no=employee_no, full_name=full_name, password=password
        )

        if user is None:
            record_attempt(
                request._request,
                employee_no=employee_no,
                full_name_input=full_name,
                success=False,
                fail_reason=fail_reason,
            )
            # 비활성 계정만 사유를 구분해 알리고, 나머지는 통일 메시지를 쓴다(specs/01 §3.2).
            if fail_reason == FAIL_INACTIVE:
                raise AccountInactive()
            raise LoginFailed()

        django_login(request._request, user, backend="accounts.backends.EmployeeNoBackend")
        mark_logged_in(user)
        record_attempt(
            request._request,
            employee_no=employee_no,
            full_name_input=full_name,
            success=True,
            user=user,
        )
        logger.info("login success user_id=%s", user.pk)

        return Response(MeSerializer(user).data, status=status.HTTP_200_OK)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        user_id = request.user.pk
        django_logout(request._request)
        logger.info("logout user_id=%s", user_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        return Response(MeSerializer(request.user).data)


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    @sensitive_post_parameters("current_password", "new_password")
    def post(self, request: Request) -> Response:
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        if not user.check_password(serializer.validated_data["current_password"]):
            raise LoginFailed(
                message="현재 비밀번호가 올바르지 않습니다.",
                code="INVALID_CURRENT_PASSWORD",
            )

        user.set_password(serializer.validated_data["new_password"])
        user.must_change_password = False
        user.save(update_fields=["password", "must_change_password", "updated_at"])

        # 비밀번호 변경 후에도 현재 세션은 유지한다.
        django_login(request._request, user, backend="accounts.backends.EmployeeNoBackend")
        logger.info("password changed user_id=%s", user.pk)

        return Response(status=status.HTTP_204_NO_CONTENT)
