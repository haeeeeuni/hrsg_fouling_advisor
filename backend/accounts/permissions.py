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
        # is_authenticated 는 비활성 사용자에게도 True 다. 세션 복원 단계에서도
        # 걸러지지만, 권한 판정에서 한 번 더 막는다(비활성화 직후 살아 있는 세션 차단).
        return bool(
            user
            and user.is_authenticated
            and user.is_active
            and getattr(user, "is_admin_role", False)
        )
