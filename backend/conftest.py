"""pytest 공통 픽스처."""

import pytest
from django.test import override_settings
from rest_framework.test import APIClient

from accounts.models import ApprovalStatus, Role, User


@pytest.fixture
def api() -> APIClient:
    # enforce_csrf_checks=False: CSRF 자체는 별도 테스트에서 확인한다.
    return APIClient()


@pytest.fixture
def user_password() -> str:
    return "pass-word-1"


@pytest.fixture
def normal_user(db, user_password: str) -> User:
    return User.objects.create_user(
        username="hong",
        full_name="홍길동",
        organization="발전운영팀",
        password=user_password,
        approval_status=ApprovalStatus.APPROVED,
    )


@pytest.fixture
def pending_user(db, user_password: str) -> User:
    return User.objects.create_user(
        username="newbie",
        full_name="신입",
        organization="협력사",
        password=user_password,
    )


@pytest.fixture
def admin_user(db, user_password: str) -> User:
    return User.objects.create_user(
        username="kimadmin",
        full_name="김관리",
        organization="기술지원팀",
        password=user_password,
        role=Role.ADMIN,
        approval_status=ApprovalStatus.APPROVED,
    )


@pytest.fixture
def seeded(db):
    """seed_defaults 를 1회 실행한 상태."""
    from django.core.management import call_command

    call_command("seed_defaults", verbosity=0)


@pytest.fixture(autouse=True)
def clear_throttle_cache():
    """테스트마다 스로틀 카운터를 비운다.

    로그인 스로틀은 IP 기준 분당 10회다. 테스트는 모두 같은 IP 라 비우지 않으면
    앞선 테스트가 쓴 횟수가 누적돼 뒤 테스트가 429 를 받는다.
    스로틀 자체를 끄면 한도 검증이 사라지므로 카운터만 초기화한다.
    """
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()


@pytest.fixture(autouse=True)
def celery_eager():
    """Celery 워커 없이 태스크를 즉시 실행한다.

    `current_app.conf` 에 직접 대입하거나 `conf.update()` 를 써도 **먹히지 않는다**.
    Celery 앱이 `config_from_object("django.conf:settings")` 로 읽기 때문에
    Django settings 값이 우선한다. settings 쪽을 덮어써야 한다.

    EAGER_PROPAGATES 는 끈다. 켜면 태스크 예외가 apply_async 를 뚫고 나와 뷰가 500 이 되는데,
    실제 운영에서는 뷰가 이미 202 를 돌려준 뒤 워커가 실패를 DB 에 기록한다.
    켜두면 "실패가 FAILED 로 기록되는가"를 검증할 수 없다.
    """
    with override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=False):
        yield
