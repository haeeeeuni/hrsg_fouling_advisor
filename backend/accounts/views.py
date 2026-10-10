"""인증·가입 API (specs/01, specs/10 §2).

View는 HTTP 입출력·권한·직렬화만 담당하고 도메인 로직은 services.py 에 둔다(AGENTS.md §3).
"""

import logging

from django.contrib.auth import login as django_login
from django.contrib.auth import logout as django_logout
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.debug import sensitive_post_parameters
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import USERNAME_VALIDATOR, User
from accounts.permissions import IsApprovedUser
from accounts.serializers import (
    ChangePasswordSerializer,
    LoginSerializer,
    MeSerializer,
    MeUpdateSerializer,
    SignupSerializer,
)
from accounts.services import authenticate_user, check_lockout, mark_logged_in, record_attempt
from common.constants import (
    CREDENTIAL_FAILURES,
    FAIL_INACTIVE,
    FAIL_LOCKED,
    FAIL_PENDING,
    FAIL_REJECTED,
)
from common.exceptions import (
    AccountInactive,
    AccountPending,
    AccountRejected,
    LoginFailed,
    LoginLocked,
)

logger = logging.getLogger(__name__)

# 세션에 사용자를 붙일 때 쓰는 백엔드. 실제 검증은 services.authenticate_user 가 한다.
SESSION_BACKEND = "django.contrib.auth.backends.ModelBackend"


def _is_usable(user) -> bool:
    return bool(user and user.is_authenticated and user.is_active and user.is_approved)


class CsrfView(APIView):
    """SPA 부팅 시 CSRF 쿠키를 받기 위한 엔드포인트."""

    permission_classes = [AllowAny]

    def get(self, request: Request) -> Response:
        return Response({"csrf_token": get_token(request._request)})


@method_decorator(sensitive_post_parameters("password", "password_confirm"), name="dispatch")
class SignupView(APIView):
    """POST /api/auth/signup/ — 가입 신청. 상태는 승인 대기, 자동 로그인하지 않는다(AUTH-2)."""

    permission_classes = [AllowAny]
    throttle_scope = "signup"

    def post(self, request: Request) -> Response:
        serializer = SignupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        logger.info("signup requested user_id=%s", user.pk)
        return Response(
            {
                "username": user.username,
                "approval_status": user.approval_status,
                "message": "가입 신청이 접수되었습니다. 관리자 승인 후 로그인할 수 있습니다.",
            },
            status=status.HTTP_201_CREATED,
        )


class UsernameAvailableView(APIView):
    """GET /api/auth/username-available/?username= — 가입 화면의 ID 중복 확인."""

    permission_classes = [AllowAny]
    throttle_scope = "username_check"

    def get(self, request: Request) -> Response:
        username = (request.query_params.get("username") or "").strip().lower()
        try:
            USERNAME_VALIDATOR(username)
        except Exception as exc:  # noqa: BLE001 - Django ValidationError 의 메시지만 쓴다.
            messages = getattr(exc, "messages", [str(exc)])
            return Response({"username": username, "available": False, "reason": messages[0]})
        if User.objects.filter(username=username).exists():
            return Response(
                {"username": username, "available": False, "reason": "이미 사용 중인 ID 입니다."}
            )
        return Response({"username": username, "available": True, "reason": ""})


# 오류 리포트에 비밀번호가 찍히지 않게 한다 (AGENTS.md §7).
# DRF 의 Request 는 HttpRequest 가 아니라 post() 에 직접 걸면 TypeError 가 난다.
@method_decorator(sensitive_post_parameters("password"), name="dispatch")
class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "login"  # IP 기준 분당 10회

    def post(self, request: Request) -> Response:
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        username = serializer.validated_data["username"]
        password = serializer.validated_data["password"]

        lock = check_lockout(username)
        if lock.locked:
            record_attempt(
                request._request, username=username, success=False, fail_reason=FAIL_LOCKED
            )
            raise LoginLocked(details={"retry_after_sec": lock.retry_after_sec})

        user, fail_reason = authenticate_user(username=username, password=password)
        if fail_reason:
            record_attempt(
                request._request,
                username=username,
                success=False,
                user=user,
                fail_reason=fail_reason,
            )
            # 상태 안내는 비밀번호가 맞았을 때만 나간다. 그 외에는 통일 메시지(AUTH-7).
            if fail_reason in CREDENTIAL_FAILURES:
                raise LoginFailed()
            if fail_reason == FAIL_PENDING:
                raise AccountPending()
            if fail_reason == FAIL_REJECTED:
                raise AccountRejected(
                    message=f"가입이 반려되었습니다(사유: {user.rejection_reason}).",
                    details={"reason": user.rejection_reason},
                )
            if fail_reason == FAIL_INACTIVE:
                raise AccountInactive()
            raise LoginFailed()

        django_login(request._request, user, backend=SESSION_BACKEND)
        mark_logged_in(user)
        record_attempt(request._request, username=username, success=True, user=user)
        logger.info("login success user_id=%s", user.pk)

        return Response({"authenticated": True, "user": MeSerializer(user).data})


class LogoutView(APIView):
    # 승인이 취소된 세션도 로그아웃은 할 수 있어야 한다.
    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        user_id = getattr(request.user, "pk", None)
        django_logout(request._request)
        logger.info("logout user_id=%s", user_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    """GET 은 공개 — 로그인 상태를 알려 준다. PATCH 는 본인 정보 수정."""

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsApprovedUser()]

    def get(self, request: Request) -> Response:
        user = request.user
        if not _is_usable(user):
            # 로그인 후 승인 취소·비활성화된 세션은 여기서 끊는다.
            if user is not None and getattr(user, "is_authenticated", False):
                django_logout(request._request)
            return Response({"authenticated": False, "user": None})
        return Response({"authenticated": True, "user": MeSerializer(user).data})

    def patch(self, request: Request) -> Response:
        serializer = MeUpdateSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"authenticated": True, "user": MeSerializer(request.user).data})


@method_decorator(sensitive_post_parameters("current_password", "new_password"), name="dispatch")
class ChangePasswordView(APIView):
    permission_classes = [IsApprovedUser]

    def post(self, request: Request) -> Response:
        user = request.user
        serializer = ChangePasswordSerializer(data=request.data, context={"user": user})
        serializer.is_valid(raise_exception=True)

        if not user.check_password(serializer.validated_data["current_password"]):
            raise LoginFailed(
                message="현재 비밀번호가 올바르지 않습니다.",
                code="INVALID_CURRENT_PASSWORD",
            )

        user.set_password(serializer.validated_data["new_password"])
        user.must_change_password = False
        user.save(update_fields=["password", "must_change_password", "updated_at"])

        # 비밀번호 변경 후에도 현재 세션은 유지한다.
        django_login(request._request, user, backend=SESSION_BACKEND)
        logger.info("password changed user_id=%s", user.pk)

        return Response(status=status.HTTP_204_NO_CONTENT)
