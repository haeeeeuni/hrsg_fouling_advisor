"""권한 클래스 (specs/01 §9).

기본 권한은 IsApprovedUser(REST_FRAMEWORK 설정). 관리자 전용 API에는 IsAdminRole 을
**명시적으로** 지정한다(AGENTS.md §6). 프론트 라우터 가드는 UX용일 뿐이며
서버에서 반드시 재검증한다.
"""

from typing import Any

from rest_framework.permissions import BasePermission
from rest_framework.request import Request


def _is_approved_active(user: Any) -> bool:
    # is_authenticated 는 비활성 사용자에게도 True 다. 승인 상태·활성 여부가 로그인 후에 바뀌어도
    # 살아 있는 세션이 즉시 막히도록 요청마다 다시 본다.
    return bool(
        user and user.is_authenticated and user.is_active and getattr(user, "is_approved", False)
    )


class IsApprovedUser(BasePermission):
    """로그인 + 승인됨 + 활성."""

    message = "승인된 사용자만 이용할 수 있습니다."

    def has_permission(self, request: Request, view: Any) -> bool:
        return _is_approved_active(request.user)


class IsAdminRole(BasePermission):
    """role == 'ADMIN' 이고 승인·활성 상태인 사용자만 허용한다.

    Django 의 is_staff / is_superuser 는 /admin/ 접근용이며 여기서 쓰지 않는다.
    """

    message = "관리자 권한이 필요합니다."

    def has_permission(self, request: Request, view: Any) -> bool:
        user = request.user
        return _is_approved_active(user) and getattr(user, "is_admin_role", False)
