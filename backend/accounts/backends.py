"""인증 백엔드.

Django 의 ModelBackend 는 USERNAME_FIELD 하나만 확인하지만, 이 시스템은
성명 + 사번 + 비밀번호 3요소를 검증한다(specs/01 §3.1). 실제 3요소 검증은
accounts.services.authenticate_user 가 수행하고, 여기서는 세션 로그인에 필요한
백엔드 인터페이스만 제공한다.
"""

from typing import Any

from django.contrib.auth.backends import BaseBackend
from django.http import HttpRequest

from accounts.models import User
from accounts.services import authenticate_user


class EmployeeNoBackend(BaseBackend):
    def authenticate(
        self,
        request: HttpRequest | None = None,
        employee_no: str | None = None,
        full_name: str | None = None,
        password: str | None = None,
        **kwargs: Any,
    ) -> User | None:
        if not (employee_no and full_name and password):
            return None
        user, _ = authenticate_user(employee_no=employee_no, full_name=full_name, password=password)
        return user

    def get_user(self, user_id: int) -> User | None:
        return User.objects.filter(pk=user_id).first()

    def user_can_authenticate(self, user: User) -> bool:
        return bool(user.is_active)
