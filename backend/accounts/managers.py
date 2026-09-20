"""User 매니저.

기본 UserManager 는 username 을 요구하므로, employee_no 기반으로 새로 정의한다.
"""

from typing import Any

from django.contrib.auth.models import BaseUserManager

from common.constants import ROLE_ADMIN, ROLE_USER


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(
        self, employee_no: str, full_name: str, password: str | None, **extra: Any
    ) -> Any:
        if not employee_no:
            raise ValueError("사번은 필수입니다.")
        if not full_name:
            raise ValueError("성명은 필수입니다.")

        user = self.model(employee_no=employee_no.strip(), full_name=full_name.strip(), **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(
        self, employee_no: str, full_name: str, password: str | None = None, **extra: Any
    ) -> Any:
        extra.setdefault("role", ROLE_USER)
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create_user(employee_no, full_name, password, **extra)

    def create_superuser(
        self, employee_no: str, full_name: str, password: str | None = None, **extra: Any
    ) -> Any:
        extra.setdefault("role", ROLE_ADMIN)
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)

        if extra.get("is_staff") is not True:
            raise ValueError("슈퍼유저는 is_staff=True 여야 합니다.")
        if extra.get("is_superuser") is not True:
            raise ValueError("슈퍼유저는 is_superuser=True 여야 합니다.")

        return self._create_user(employee_no, full_name, password, **extra)
