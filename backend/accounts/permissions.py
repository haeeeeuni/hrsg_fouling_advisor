"""권한 클래스.

관리자 전용 API에는 IsAdminRole 을 **명시적으로** 지정한다(AGENTS.md §7, specs/13 §2).
프론트 라우터 가드는 UX용일 뿐이며 서버에서 반드시 재검증한다.
"""

from typing import Any

from rest_framework.permissions import BasePermission
from rest_framework.request import Request


class IsAdminRole(BasePermission):
    """role == 'ADMIN' 인 사용자만 허용한다.

    Django 의 is_staff / is_superuser 는 /admin/ 접근용이며 여기서 쓰지 않는다.
    """

    message = "관리자 권한이 필요합니다."

    def has_permission(self, request: Request, view: Any) -> bool:
        user = request.user
        return bool(user and user.is_authenticated and getattr(user, "is_admin_role", False))
