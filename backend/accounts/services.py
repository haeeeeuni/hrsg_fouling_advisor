"""인증·가입 도메인 로직 (specs/01 §3~§6).

로그인 잠금 규칙, 이력 기록, 승인 처리를 뷰에서 분리한다.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta

from django.http import HttpRequest
from django.utils import timezone

from accounts.models import ApprovalStatus, LoginHistory, Role, User
from common.constants import (
    CREDENTIAL_FAILURES,
    FAIL_BAD_PASSWORD,
    FAIL_INACTIVE,
    FAIL_LOCKED,
    FAIL_NOT_FOUND,
    FAIL_PENDING,
    FAIL_REJECTED,
)
from common.settings_resolver import get_setting

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


def check_lockout(username: str) -> LockState:
    """연속 실패 횟수가 임계치에 도달했고 잠금 시간이 지나지 않았으면 잠금 상태를 반환한다.

    specs/01 AUTH-8 — ID·비밀번호가 틀린 시도만 센다. 승인 대기·반려·비활성은 비밀번호가
    맞았다는 뜻이므로 세지 않고, 잠긴 상태에서의 시도(LOCKED)도 세지 않는다
    (세면 잠긴 동안 재시도할 때마다 해제 시각이 계속 밀린다).
    """
    max_failures: int = get_setting("login_max_failures")
    lockout_minutes: int = get_setting("login_lockout_minutes")

    recent = (
        LoginHistory.objects.filter(attempted_username=username)
        .exclude(fail_reason=FAIL_LOCKED)
        .order_by("-created_at")
        .values_list("success", "fail_reason", "created_at")
    )

    consecutive: list = []
    for success, fail_reason, created_at in recent[: max_failures * 3]:
        if success or fail_reason not in CREDENTIAL_FAILURES:
            break
        consecutive.append(created_at)
        if len(consecutive) >= max_failures:
            break

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
    username: str,
    success: bool,
    user: User | None = None,
    fail_reason: str = "",
) -> None:
    LoginHistory.objects.create(
        user=user,
        attempted_username=username[:150],
        success=success,
        fail_reason=fail_reason,
        ip=client_ip(request),
        user_agent=request.META.get("HTTP_USER_AGENT", "")[:1000],
    )


def authenticate_user(*, username: str, password: str) -> tuple[User | None, str]:
    """ID·비밀번호를 검증하고, 맞으면 승인·활성 상태를 본다.

    Returns: (user, fail_reason). 성공 시 fail_reason 은 빈 문자열.
    상태 사유(PENDING/REJECTED/INACTIVE)일 때도 user 를 돌려준다 — 반려 사유를 알리기 위해서다.
    상태 확인을 비밀번호 확인 **뒤에** 두는 것이 핵심이다(specs/01 AUTH-7, 계정 존재 노출 방지).
    """
    user = User.objects.filter(username=username).first()
    if user is None:
        # 존재하지 않는 ID 도 해시 비교 시간만큼 걸리게 해 응답 시간으로 존재 여부가 새지 않게 한다.
        User().set_password(password)
        return None, FAIL_NOT_FOUND

    if not user.check_password(password):
        return None, FAIL_BAD_PASSWORD

    if user.approval_status == ApprovalStatus.PENDING:
        return user, FAIL_PENDING
    if user.approval_status == ApprovalStatus.REJECTED:
        return user, FAIL_REJECTED
    if not user.is_active:
        return user, FAIL_INACTIVE

    return user, ""


def mark_logged_in(user: User) -> None:
    user.last_login_at = timezone.now()
    user.save(update_fields=["last_login_at", "updated_at"])


def active_admins():
    return User.objects.filter(
        role=Role.ADMIN, approval_status=ApprovalStatus.APPROVED, is_active=True
    )


def is_last_active_admin(user: User) -> bool:
    """이 사용자가 마지막 활성 관리자인지 (specs/01 AUTH-11)."""
    if not (user.role == Role.ADMIN and user.is_approved and user.is_active):
        return False
    return not active_admins().exclude(pk=user.pk).exists()


def approve(user: User, *, by: User) -> None:
    user.approval_status = ApprovalStatus.APPROVED
    user.approved_by = by
    user.approved_at = timezone.now()
    user.rejection_reason = ""
    user.save(
        update_fields=[
            "approval_status",
            "approved_by",
            "approved_at",
            "rejection_reason",
            "updated_at",
        ]
    )


def reject(user: User, *, by: User, reason: str) -> None:
    user.approval_status = ApprovalStatus.REJECTED
    user.approved_by = by
    user.approved_at = timezone.now()
    user.rejection_reason = reason
    user.save(
        update_fields=[
            "approval_status",
            "approved_by",
            "approved_at",
            "rejection_reason",
            "updated_at",
        ]
    )


def has_activity(user: User) -> bool:
    """물리 삭제를 막아야 하는 활동 기록이 있는지 (specs/01 §7).

    기준은 대화(N5)·데이터 요청 건(N3)이다. 대화는 N5 에서 여기에 더한다.
    """
    return user.data_requests.exists()
