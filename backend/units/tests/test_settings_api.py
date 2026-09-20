"""설정 관리 API (specs/15 §10, specs/13 §9). PostgreSQL 필요."""

import pytest

from common.models import AuditLog
from units.models import Setting, Unit, UnitSetting

pytestmark = pytest.mark.django_db

URL = "/api/settings/"


@pytest.fixture
def unit(db):
    return Unit.objects.create(code="U1", name="1호기", rated_power_mw=160, min_load_mw=60)


# --- 권한 (AC-15-2) ---


def test_anonymous_gets_401(api, seeded):
    assert api.get(URL).status_code == 401


def test_ac_15_2_normal_user_cannot_patch_settings(api, normal_user, seeded):
    api.force_authenticate(normal_user)

    res = api.patch(URL, {"fouling_threshold": 55}, format="json")

    assert res.status_code == 403
    assert res.data["error"]["code"] == "PERMISSION_DENIED"


def test_normal_user_cannot_read_settings(api, normal_user, seeded):
    api.force_authenticate(normal_user)

    assert api.get(URL).status_code == 403


# --- 조회 ---


def test_admin_lists_settings_with_metadata(api, admin_user, seeded):
    api.force_authenticate(admin_user)

    res = api.get(URL)

    assert res.status_code == 200
    rows = {row["key"]: row for row in res.data["results"]}
    threshold = rows["fouling_threshold"]
    assert threshold["value"] == 60
    assert threshold["default"] == 60
    assert threshold["label"]
    assert threshold["is_modified"] is False
    assert "FOULING" in res.data["categories"]


def test_category_filter(api, admin_user, seeded):
    api.force_authenticate(admin_user)

    res = api.get(URL, {"category": "BENEFIT"})

    assert all(row["category"] == "BENEFIT" for row in res.data["results"])


# --- 변경 (AC-13-1) ---


def test_admin_updates_setting(api, admin_user, seeded):
    api.force_authenticate(admin_user)

    res = api.patch(URL, {"fouling_threshold": 50}, format="json")

    assert res.status_code == 200
    assert "fouling_threshold" in res.data["updated"]
    assert Setting.objects.get(key="fouling_threshold").value == "50"
    assert "다음 분석부터 적용" in res.data["notice"]


def test_update_records_who_changed_it(api, admin_user, seeded):
    api.force_authenticate(admin_user)

    api.patch(URL, {"fouling_threshold": 50}, format="json")

    assert Setting.objects.get(key="fouling_threshold").updated_by == admin_user


def test_ac_13_5_change_is_audited_with_before_and_after(api, admin_user, seeded):
    """AC-13-5: 설정 변경이 감사 로그에 변경 전후 값과 함께 남는다."""
    api.force_authenticate(admin_user)

    api.patch(URL, {"fouling_threshold": 50}, format="json")

    log = AuditLog.objects.filter(target_type="Setting").latest("created_at")
    assert log.actor == admin_user
    assert log.before["fouling_threshold"] == "60"
    assert log.after["fouling_threshold"] == "50"


def test_unchanged_value_is_not_audited(api, admin_user, seeded):
    api.force_authenticate(admin_user)

    api.patch(URL, {"fouling_threshold": 60}, format="json")

    assert not AuditLog.objects.filter(target_type="Setting").exists()


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        ({"fouling_threshold": 150}, "SETTING_OUT_OF_RANGE"),
        ({"weight_dp": 0.8, "weight_stack_temp": 0.4}, "INVALID_WEIGHTS"),
        ({"grade_caution_min": 70}, "INVALID_GRADE_BOUNDARY"),
        ({"no_such_key": 1}, "UNKNOWN_SETTING"),
    ],
)
def test_invalid_updates_are_rejected(api, admin_user, seeded, payload, code):
    api.force_authenticate(admin_user)

    res = api.patch(URL, payload, format="json")

    assert res.status_code == 400
    assert res.data["error"]["code"] == code


def test_rejected_update_changes_nothing(api, admin_user, seeded):
    api.force_authenticate(admin_user)

    api.patch(URL, {"fouling_threshold": 55, "grade_caution_min": 70}, format="json")

    assert Setting.objects.get(key="fouling_threshold").value == "60"


# --- 기본값 복원 ---


def test_restore_defaults_by_key(api, admin_user, seeded):
    api.force_authenticate(admin_user)
    api.patch(URL, {"fouling_threshold": 50}, format="json")

    res = api.post(f"{URL}restore-defaults/", {"keys": ["fouling_threshold"]}, format="json")

    assert res.data["restored"] == ["fouling_threshold"]
    assert Setting.objects.get(key="fouling_threshold").value == "60"


def test_restore_defaults_by_category(api, admin_user, seeded):
    api.force_authenticate(admin_user)
    api.patch(URL, {"fouling_threshold": 50, "sigma_ref": 8}, format="json")

    res = api.post(f"{URL}restore-defaults/", {"category": "FOULING"}, format="json")

    assert set(res.data["restored"]) == {"fouling_threshold", "sigma_ref"}


def test_restore_requires_target(api, admin_user, seeded):
    api.force_authenticate(admin_user)

    assert api.post(f"{URL}restore-defaults/", {}, format="json").status_code == 400


# --- 호기별 오버라이드 (AC-13-2, AC-14-4) ---


def test_ac_13_2_unit_override_wins_over_global(api, admin_user, seeded, unit):
    api.force_authenticate(admin_user)
    api.patch(URL, {"fouling_threshold": 50}, format="json")

    res = api.put(f"/api/units/{unit.id}/settings/", {"fouling_threshold": 40}, format="json")

    assert res.status_code == 200
    effective = api.get(f"{URL}effective/", {"unit_id": unit.id}).data["settings"]
    assert effective["fouling_threshold"] == 40
    assert api.get(f"{URL}effective/").data["settings"]["fouling_threshold"] == 50


def test_unit_settings_show_inherited_values(api, admin_user, seeded, unit):
    api.force_authenticate(admin_user)
    api.put(f"/api/units/{unit.id}/settings/", {"sigma_ref": 8}, format="json")

    res = api.get(f"/api/units/{unit.id}/settings/")

    rows = {row["key"]: row for row in res.data["settings"]}
    assert rows["sigma_ref"]["is_overridden"] is True
    assert rows["sigma_ref"]["effective_value"] == 8
    assert rows["sigma_ref"]["global_value"] == 6.0
    assert rows["fouling_threshold"]["is_overridden"] is False


def test_override_is_validated_too(api, admin_user, seeded, unit):
    api.force_authenticate(admin_user)

    res = api.put(f"/api/units/{unit.id}/settings/", {"fouling_threshold": 999}, format="json")

    assert res.status_code == 400
    assert res.data["error"]["code"] == "SETTING_OUT_OF_RANGE"


def test_deleting_override_restores_inheritance(api, admin_user, seeded, unit):
    api.force_authenticate(admin_user)
    api.put(f"/api/units/{unit.id}/settings/", {"fouling_threshold": 40}, format="json")

    res = api.delete(f"/api/units/{unit.id}/settings/fouling_threshold/")

    assert res.status_code == 204
    assert not UnitSetting.objects.filter(unit=unit, key="fouling_threshold").exists()
    assert (
        api.get(f"{URL}effective/", {"unit_id": unit.id}).data["settings"]["fouling_threshold"]
        == 60
    )


def test_deleting_missing_override_is_404(api, admin_user, seeded, unit):
    api.force_authenticate(admin_user)

    assert api.delete(f"/api/units/{unit.id}/settings/sigma_ref/").status_code == 404


def test_unit_override_is_audited(api, admin_user, seeded, unit):
    api.force_authenticate(admin_user)

    api.put(f"/api/units/{unit.id}/settings/", {"fouling_threshold": 40}, format="json")

    assert AuditLog.objects.filter(target_type="UnitSetting").exists()


# --- effective (인증 사용자) ---


def test_normal_user_can_read_effective_settings(api, normal_user, seeded, unit):
    """분석 실행에 필요하므로 일반 사용자도 최종 적용값은 볼 수 있다."""
    api.force_authenticate(normal_user)

    res = api.get(f"{URL}effective/", {"unit_id": unit.id})

    assert res.status_code == 200
    assert res.data["settings"]["fouling_threshold"] == 60
