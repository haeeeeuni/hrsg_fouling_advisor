"""seed_defaults 테스트 (AC-01-1, AC-01-2, AC-18-4)."""

import pytest
from django.core.management import call_command

from accounts.models import Role, User
from units.models import Setting
from units.setting_defaults import SETTING_DEFS

pytestmark = pytest.mark.django_db


def seed():
    call_command("seed_defaults", verbosity=0)


def test_ac_01_1_default_admin_can_log_in_on_first_boot(api):
    """AC-01-1: 계정이 없는 상태에서 처음 기동하면 관리자/ADM01/qwer 로 로그인할 수 있다."""
    assert User.objects.count() == 0

    seed()

    res = api.post(
        "/api/auth/login/",
        {"employee_no": "ADM01", "full_name": "관리자", "password": "qwer"},
        format="json",
    )

    assert res.status_code == 200
    assert res.data["role"] == Role.ADMIN
    assert res.data["is_admin"] is True
    # 최초 비밀번호 변경을 유도하는 배너 조건(specs/01 §4)
    assert res.data["must_change_password"] is True


def test_ac_01_2_rerun_does_not_create_second_admin():
    """AC-01-2: 이미 관리자 계정이 있으면 새 계정을 만들지 않는다."""
    seed()
    seed()
    seed()

    assert User.objects.filter(role=Role.ADMIN).count() == 1


def test_existing_admin_is_not_overwritten():
    User.objects.create_user(
        employee_no="Z0001", full_name="기존관리자", password="pw1234", role=Role.ADMIN
    )

    seed()

    assert User.objects.filter(role=Role.ADMIN).count() == 1
    assert not User.objects.filter(employee_no="ADM01").exists()


def test_ac_18_4_seeding_twice_creates_no_duplicates():
    """AC-18-4: seed_defaults 를 두 번 실행해도 데이터가 중복되지 않는다."""
    seed()
    first_count = Setting.objects.count()

    seed()

    assert Setting.objects.count() == first_count == len(SETTING_DEFS)
    assert User.objects.count() == 1


def test_seed_does_not_revert_admin_edited_values():
    """관리자가 바꾼 현재값을 시드가 되돌리면 안 된다."""
    seed()
    row = Setting.objects.get(key="max_upload_mb")
    row.value = "500"
    row.save(update_fields=["value"])

    seed()

    row.refresh_from_db()
    assert row.value == "500"  # 현재값 보존
    assert row.default_value == "200"  # 기본값은 코드 정의 그대로


def test_seed_refreshes_metadata_only():
    seed()
    row = Setting.objects.get(key="session_timeout_hours")
    row.label = "손으로 바꾼 라벨"
    row.save(update_fields=["label"])

    seed()

    row.refresh_from_db()
    assert row.label == "세션 만료 시간"


def test_settings_only_skips_admin_creation():
    call_command("seed_defaults", "--settings-only", verbosity=0)

    assert Setting.objects.count() == len(SETTING_DEFS)
    assert User.objects.count() == 0


def test_seeded_rows_carry_full_metadata():
    seed()

    row = Setting.objects.get(key="report_retention_days")
    assert row.category == "SYSTEM"
    assert row.value_type == "INT"
    assert row.label
    assert row.unit_label == "일"
    assert row.min_value == 1
