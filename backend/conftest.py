"""pytest 공통 픽스처."""

import pytest
from rest_framework.test import APIClient

from accounts.models import Role, User


@pytest.fixture
def api() -> APIClient:
    # enforce_csrf_checks=False: CSRF 자체는 별도 테스트에서 확인한다.
    return APIClient()


@pytest.fixture
def user_password() -> str:
    return "pw1234"


@pytest.fixture
def normal_user(db, user_password: str) -> User:
    return User.objects.create_user(
        employee_no="A1234",
        full_name="홍길동",
        password=user_password,
        department="발전운영팀",
    )


@pytest.fixture
def admin_user(db, user_password: str) -> User:
    return User.objects.create_user(
        employee_no="B5678",
        full_name="김관리",
        password=user_password,
        role=Role.ADMIN,
    )


@pytest.fixture
def seeded(db):
    """seed_defaults 를 1회 실행한 상태."""
    from django.core.management import call_command

    call_command("seed_defaults", verbosity=0)
