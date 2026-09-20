"""인증 관련 도메인 로직 (specs/01 §3).

로그인 잠금 규칙과 이력 기록을 뷰에서 분리한다.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta

from django.http import HttpRequest
from django.utils import timezone

from accounts.models import LoginHistory, User
from common.constants import (
    FAIL_BAD_PASSWORD,
    FAIL_INACTIVE,
    FAIL_LOCKED,
    FAIL_NAME_MISMATCH,
    FAIL_NOT_FOUND,
)
from units.settings_resolver import get_setting

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LockState:
    locked: bool
    retry_after_sec: int = 0


def client_ip(request: HttpRequest) -> str | None:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR") or None


def check_lockout(employee_no: str) -> LockState:
    """연속 실패 횟수가 임계치에 도달했고 잠금 시간이 지나지 않았으면 잠금 상태를 반환한다.

    specs/01 §3.2 — 실패 5회 연속 시 5분간 해당 사번 로그인 차단(임계치는 설정값).
    """
    max_failures: int = get_setting("login_max_failures")
    lockout_minutes: int = get_setting("login_lockout_minutes")

    # 잠금 상태에서의 시도(FAIL_LOCKED)는 연속 실패로 세지 않는다.
    # 그렇지 않으면 잠긴 동안 재시도할 때마다 해제 시각이 계속 밀린다.
    recent = list(
        LoginHistory.objects.filter(attempted_employee_no=employee_no)
        .exclude(fail_reason=FAIL_LOCKED)
        .order_by("-created_at")
        .values_list("success", "created_at")[: max_failures + 1]
    )

    consecutive: list = []
    for success, created_at in recent:
        if success:
            break
        consecutive.append(created_at)

    if len(consecutive) < max_failures:
        return LockState(locked=False)

    # 가장 최근 실패 시각 기준으로 잠금 해제 시각을 계산한다.
    unlock_at = consecutive[0] + timedelta(minutes=lockout_minutes)
    now = timezone.now()
    if now >= unlock_at:
        return LockState(locked=False)

    return LockState(locked=True, retry_after_sec=int((unlock_at - now).total_seconds()))


def record_attempt(
    request: HttpRequest,
    *,
    employee_no: str,
    full_name_input: str,
    success: bool,
    user: User | None = None,
    fail_reason: str = "",
) -> None:
    LoginHistory.objects.create(
        user=user,
        attempted_employee_no=employee_no[:20],
        full_name_input=full_name_input[:50],
        success=success,
        fail_reason=fail_reason,
        ip=client_ip(request),
        user_agent=request.META.get("HTTP_USER_AGENT", "")[:1000],
    )


def authenticate_user(
    *, employee_no: str, full_name: str, password: str
) -> tuple[User | None, str]:
    """성명·사번·비밀번호 3요소를 검증한다.

    Returns: (user, fail_reason). 성공 시 fail_reason 은 빈 문자열.
    specs/01 §3.2 의 순서를 그대로 따른다.
    """
    user = User.objects.filter(employee_no=employee_no).first()
    if user is None:
        return None, FAIL_NOT_FOUND

    # 성명은 공백 제거 후 정확히 일치해야 한다.
    if user.full_name.replace(" ", "") != full_name.replace(" ", ""):
        return None, FAIL_NAME_MISMATCH

    if not user.is_active:
        return None, FAIL_INACTIVE

    if not user.check_password(password):
        return None, FAIL_BAD_PASSWORD

    return user, ""


def mark_logged_in(user: User) -> None:
    user.last_login_at = timezone.now()
    user.save(update_fields=["last_login_at", "updated_at"])
