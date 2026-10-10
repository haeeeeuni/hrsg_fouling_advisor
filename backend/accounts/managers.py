"""User 매니저.

ID(username)는 소문자로 정규화한다. 가입 경로(create_user)의 기본 상태는 승인 대기다.
"""

from typing import Any

from django.contrib.auth.models import BaseUserManager

from common.constants import APPROVAL_APPROVED, APPROVAL_PENDING, ROLE_ADMIN, ROLE_USER


class UserManager(BaseUserManager):
    use_in_migrations = True

    @classmethod
    def normalize_username(cls, username: str) -> str:
        return (username or "").strip().lower()

    def get_by_natural_key(self, username: str) -> Any:
        # Django /admin/ 로그인 폼도 대소문자 구분 없이 받는다.
        return self.get(username=self.normalize_username(username))

    def _create_user(
        self, username: str, full_name: str, password: str | None, **extra: Any
    ) -> Any:
        if not username:
            raise ValueError("ID 는 필수입니다.")
        if not full_name:
            raise ValueError("성명은 필수입니다.")

        user = self.model(
            username=self.normalize_username(username), full_name=full_name.strip(), **extra
        )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(
        self, username: str, full_name: str, password: str | None = None, **extra: Any
    ) -> Any:
        extra.setdefault("role", ROLE_USER)
        extra.setdefault("approval_status", APPROVAL_PENDING)
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create_user(username, full_name, password, **extra)

    def create_superuser(
        self, username: str, full_name: str, password: str | None = None, **extra: Any
    ) -> Any:
        extra.setdefault("role", ROLE_ADMIN)
        extra.setdefault("approval_status", APPROVAL_APPROVED)
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)

        if extra.get("is_staff") is not True:
            raise ValueError("슈퍼유저는 is_staff=True 여야 합니다.")
        if extra.get("is_superuser") is not True:
            raise ValueError("슈퍼유저는 is_superuser=True 여야 합니다.")

        return self._create_user(username, full_name, password, **extra)
