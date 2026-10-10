"""설정값 조회·검증·관리 API (specs/08 ADM-4, AC-08-2·3)."""

import pytest

from common.models import AuditLog, Setting
from common.setting_defaults import SETTING_DEF_BY_KEY, SETTING_DEFS, TYPE_INT
from common.settings_resolver import get_effective_settings, get_setting
from common.settings_validation import SettingValidationError, validate

SETTINGS = "/api/admin/settings/"

# --- 정의·검증 (DB 불필요) ---


def test_every_definition_has_label_and_valid_range():
    for definition in SETTING_DEFS:
        assert definition.label, definition.key
        if definition.min_value is not None and definition.max_value is not None:
            assert definition.min_value <= definition.max_value, definition.key
            if definition.value_type == TYPE_INT:
                assert definition.min_value <= definition.default <= definition.max_value


def test_validate_coerces_strings():
    assert validate({"login_max_failures": "7"}) == {"login_max_failures": 7}


@pytest.mark.parametrize("raw", [2, 21, "abc", True, 5.5, None])
def test_validate_rejects_bad_values(raw):
    with pytest.raises(SettingValidationError):
        validate({"login_max_failures": raw})


def test_validate_rejects_unknown_key():
    with pytest.raises(SettingValidationError) as exc:
        validate({"no_such_key": 1})

    assert exc.value.code == "UNKNOWN_SETTING"


# --- 조회 (DB) ---


@pytest.mark.django_db
def test_resolver_falls_back_to_seed_default_without_row():
    assert get_setting("login_max_failures") == SETTING_DEF_BY_KEY["login_max_failures"].default


@pytest.mark.django_db
def test_resolver_reads_db_value(seeded):
    Setting.objects.filter(key="login_max_failures").update(value="9")

    assert get_setting("login_max_failures") == 9
    assert get_effective_settings()["login_max_failures"] == 9


# --- API ---


@pytest.fixture
def as_admin(api, admin_user, seeded):
    api.force_authenticate(admin_user)
    return api


@pytest.mark.django_db
def test_list_groups_by_category(as_admin):
    res = as_admin.get(SETTINGS)

    keys = {row["key"] for row in res.data["results"]}
    assert keys == {d.key for d in SETTING_DEFS}
    assert {"code": "AUTH", "label": "인증"} in res.data["categories"]


@pytest.mark.django_db
def test_patch_saves_and_audits(as_admin):
    res = as_admin.patch(SETTINGS, {"login_max_failures": 7}, format="json")

    assert res.status_code == 200
    assert res.data["updated"] == ["login_max_failures"]
    assert get_setting("login_max_failures") == 7
    log = AuditLog.objects.get(target_type="Setting")
    assert log.before == {"login_max_failures": "5"}
    assert log.after == {"login_max_failures": "7"}


@pytest.mark.django_db
def test_out_of_range_is_not_saved(as_admin):
    """AC-08-2"""
    res = as_admin.patch(SETTINGS, {"login_max_failures": 100}, format="json")

    assert res.status_code == 400
    assert res.data["error"]["code"] == "SETTING_OUT_OF_RANGE"
    assert "최댓값" in res.data["error"]["message"]
    assert get_setting("login_max_failures") == 5


@pytest.mark.django_db
def test_partial_failure_saves_nothing(as_admin):
    res = as_admin.patch(
        SETTINGS, {"login_lockout_minutes": 10, "login_max_failures": 0}, format="json"
    )

    assert res.status_code == 400
    assert get_setting("login_lockout_minutes") == 5


@pytest.mark.django_db
def test_reset_to_default(as_admin):
    as_admin.patch(SETTINGS, {"login_max_failures": 7}, format="json")

    res = as_admin.post(f"{SETTINGS}login_max_failures/reset/")

    assert res.status_code == 200
    assert res.data["value"] == 5
    assert res.data["is_modified"] is False
    assert AuditLog.objects.filter(action="RESTORE").count() == 1


@pytest.mark.django_db
def test_reset_unknown_key_is_404(as_admin):
    assert as_admin.post(f"{SETTINGS}nope/reset/").status_code == 404
