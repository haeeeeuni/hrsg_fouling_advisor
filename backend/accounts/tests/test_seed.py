"""seed_defaults — 기본 관리자와 설정 시드 (specs/01 AC-01-4·5, specs/08 AC-08-6)."""

import pytest
from django.core.management import call_command

from accounts.models import ApprovalStatus, Role, User
from common.models import Setting
from common.setting_defaults import SETTING_DEFS

pytestmark = pytest.mark.django_db


def seed():
    call_command("seed_defaults", verbosity=0)


def test_empty_db_gets_default_admin(api):
    """AC-01-4"""
    seed()

    admin = User.objects.get(username="admin")
    assert admin.role == Role.ADMIN
    assert admin.approval_status == ApprovalStatus.APPROVED
    assert admin.must_change_password is True

    res = api.post("/api/auth/login/", {"username": "admin", "password": "admin1234!"})
    assert res.status_code == 200
    assert res.data["user"]["must_change_password"] is True


def test_seed_is_idempotent():
    """AC-01-5 · AC-08-6"""
    seed()
    seed()

    assert User.objects.filter(username="admin").count() == 1
    assert Setting.objects.count() == len(SETTING_DEFS)


def test_deleted_admin_is_not_recreated_when_another_admin_exists(admin_user):
    """AC-01-5 — 지운 기본 계정이 재시작 때마다 되살아나면 안 된다."""
    seed()

    assert not User.objects.filter(username="admin").exists()


def test_pending_admin_role_does_not_block_seed(pending_user):
    """승인 대기인 관리자 역할 계정은 '활성 관리자'가 아니다."""
    pending_user.role = Role.ADMIN
    pending_user.save()

    seed()

    assert User.objects.filter(username="admin", role=Role.ADMIN).exists()


def test_existing_non_admin_named_admin_is_left_alone(user_password):
    User.objects.create_user(
        username="admin", full_name="동명이인", organization="x", password=user_password
    )

    seed()

    assert User.objects.get(username="admin").role == Role.USER


def test_seed_does_not_overwrite_admin_changes(seeded):
    Setting.objects.filter(key="login_max_failures").update(value="7")

    seed()

    assert Setting.objects.get(key="login_max_failures").value == "7"


def test_seed_refreshes_metadata():
    seed()
    Setting.objects.filter(key="login_max_failures").update(label="옛 이름")

    seed()

    assert Setting.objects.get(key="login_max_failures").label != "옛 이름"
