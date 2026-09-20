"""사용자 관리 API (specs/15 §3, specs/01 §9). PostgreSQL 필요."""

import pytest

from accounts.models import Role, User
from common.models import AuditLog

pytestmark = pytest.mark.django_db

URL = "/api/users/"


def payload(**extra):
    return {
        "employee_no": "C1111",
        "full_name": "신규사용자",
        "role": "USER",
        "department": "발전운영팀",
        "initial_password": "pw1234",
        **extra,
    }


# --- 권한 ---


def test_anonymous_gets_401(api, db):
    assert api.get(URL).status_code == 401


def test_normal_user_gets_403(api, normal_user):
    api.force_authenticate(normal_user)

    assert api.get(URL).status_code == 403


def test_admin_can_list(api, admin_user, normal_user):
    api.force_authenticate(admin_user)

    res = api.get(URL)

    assert res.status_code == 200
    assert res.data["count"] == 2


# --- 생성 ---


def test_admin_creates_user_with_forced_password_change(api, admin_user):
    api.force_authenticate(admin_user)

    res = api.post(URL, payload(), format="json")

    assert res.status_code == 201
    user = User.objects.get(employee_no="C1111")
    assert user.must_change_password is True
    assert user.check_password("pw1234")


def test_initial_password_is_required(api, admin_user):
    api.force_authenticate(admin_user)
    body = payload()
    body.pop("initial_password")

    res = api.post(URL, body, format="json")

    assert res.status_code == 400
    assert "initial_password" in res.data["error"]["details"]


def test_duplicate_employee_no_is_rejected(api, admin_user, normal_user):
    api.force_authenticate(admin_user)

    res = api.post(URL, payload(employee_no="A1234"), format="json")

    assert res.status_code == 400


def test_employee_no_is_uppercased(api, admin_user):
    api.force_authenticate(admin_user)

    api.post(URL, payload(employee_no="c1111"), format="json")

    assert User.objects.filter(employee_no="C1111").exists()


def test_creation_is_audited(api, admin_user):
    api.force_authenticate(admin_user)

    api.post(URL, payload(), format="json")

    log = AuditLog.objects.filter(target_type="User", action="CREATE").latest("created_at")
    assert log.actor == admin_user
    assert "신규사용자" in log.target_label
    # 비밀번호는 감사 로그에도 남지 않는다 (AGENTS.md §7)
    assert "password" not in (log.after or {})


# --- 수정 ---


def test_employee_no_cannot_be_changed(api, admin_user, normal_user):
    api.force_authenticate(admin_user)

    res = api.patch(f"{URL}{normal_user.id}/", {"employee_no": "Z9999"}, format="json")

    assert res.status_code == 400


def test_other_fields_can_be_updated(api, admin_user, normal_user):
    api.force_authenticate(admin_user)

    res = api.patch(f"{URL}{normal_user.id}/", {"department": "정비팀"}, format="json")

    assert res.status_code == 200
    normal_user.refresh_from_db()
    assert normal_user.department == "정비팀"


def test_update_is_audited_with_changed_fields_only(api, admin_user, normal_user):
    api.force_authenticate(admin_user)

    api.patch(f"{URL}{normal_user.id}/", {"department": "정비팀"}, format="json")

    log = AuditLog.objects.filter(target_type="User", action="UPDATE").latest("created_at")
    assert log.before == {"department": "발전운영팀"}
    assert log.after == {"department": "정비팀"}


# --- AC-01-6 : 마지막 관리자 보호 ---


def test_ac_01_6_last_admin_cannot_be_deactivated(api, admin_user):
    """AC-01-6: 마지막 관리자 계정을 비활성화하려 하면 거부된다."""
    api.force_authenticate(admin_user)

    res = api.patch(f"{URL}{admin_user.id}/", {"is_active": False}, format="json")

    assert res.status_code == 409
    assert res.data["error"]["code"] == "LAST_ADMIN_PROTECTED"


def test_last_admin_cannot_be_demoted(api, admin_user):
    api.force_authenticate(admin_user)

    res = api.patch(f"{URL}{admin_user.id}/", {"role": "USER"}, format="json")

    assert res.status_code in (409,)


def test_last_admin_cannot_be_deleted(api, admin_user):
    api.force_authenticate(admin_user)

    res = api.delete(f"{URL}{admin_user.id}/")

    assert res.status_code == 409


def test_admin_can_be_deactivated_when_another_exists(api, admin_user, user_password):
    other = User.objects.create_user(
        employee_no="B9999", full_name="다른관리자", password=user_password, role=Role.ADMIN
    )
    api.force_authenticate(admin_user)

    res = api.patch(f"{URL}{other.id}/", {"is_active": False}, format="json")

    assert res.status_code == 200


def test_cannot_demote_self(api, admin_user, user_password):
    User.objects.create_user(
        employee_no="B9999", full_name="다른관리자", password=user_password, role=Role.ADMIN
    )
    api.force_authenticate(admin_user)

    res = api.patch(f"{URL}{admin_user.id}/", {"role": "USER"}, format="json")

    assert res.status_code == 409
    assert res.data["error"]["code"] == "CANNOT_DEMOTE_SELF"


# --- 삭제 (specs/01 §5) ---


def test_delete_deactivates_by_default(api, admin_user, normal_user):
    api.force_authenticate(admin_user)

    res = api.delete(f"{URL}{normal_user.id}/")

    assert res.status_code == 200
    assert res.data["deactivated"] is True
    normal_user.refresh_from_db()
    assert normal_user.is_active is False


def test_hard_delete_removes_account_without_history(api, admin_user, normal_user):
    api.force_authenticate(admin_user)

    res = api.delete(f"{URL}{normal_user.id}/?hard=true")

    assert res.status_code == 204
    assert not User.objects.filter(pk=normal_user.pk).exists()


def test_hard_delete_is_blocked_when_analysis_history_exists(api, admin_user, normal_user):
    from django.utils import timezone

    from analysis.models import AnalysisRun
    from units.models import Unit

    unit = Unit.objects.create(code="U1", name="1호기", rated_power_mw=160, min_load_mw=60)
    AnalysisRun.objects.create(
        unit=unit,
        executed_by=normal_user,
        period_start=timezone.now(),
        period_end=timezone.now(),
    )
    api.force_authenticate(admin_user)

    res = api.delete(f"{URL}{normal_user.id}/?hard=true")

    assert res.status_code == 409
    assert res.data["error"]["code"] == "USER_HAS_HISTORY"


def test_cannot_delete_self(api, admin_user, user_password):
    User.objects.create_user(
        employee_no="B9999", full_name="다른관리자", password=user_password, role=Role.ADMIN
    )
    api.force_authenticate(admin_user)

    assert api.delete(f"{URL}{admin_user.id}/").status_code == 409


# --- 비밀번호 초기화 ---


def test_reset_password_forces_change(api, admin_user, normal_user):
    api.force_authenticate(admin_user)

    res = api.post(
        f"{URL}{normal_user.id}/reset-password/", {"new_password": "newpw99"}, format="json"
    )

    assert res.status_code == 200
    normal_user.refresh_from_db()
    assert normal_user.check_password("newpw99")
    assert normal_user.must_change_password is True


def test_reset_password_enforces_min_length(api, admin_user, normal_user):
    api.force_authenticate(admin_user)

    res = api.post(f"{URL}{normal_user.id}/reset-password/", {"new_password": "ab"}, format="json")

    assert res.status_code == 400


def test_reset_password_audit_has_no_password(api, admin_user, normal_user):
    api.force_authenticate(admin_user)

    api.post(f"{URL}{normal_user.id}/reset-password/", {"new_password": "newpw99"}, format="json")

    log = AuditLog.objects.filter(target_type="User").latest("created_at")
    assert "newpw99" not in str(log.after)
    assert log.after["password_reset"] is True


# --- 필터 ---


def test_filter_by_role_and_active(api, admin_user, normal_user):
    api.force_authenticate(admin_user)

    assert api.get(URL, {"role": "ADMIN"}).data["count"] == 1
    assert api.get(URL, {"is_active": "true"}).data["count"] == 2


def test_search_by_name(api, admin_user, normal_user):
    api.force_authenticate(admin_user)

    assert api.get(URL, {"search": "홍길동"}).data["count"] == 1


# --- 로그인 이력 (specs/01 §7) ---


def test_login_histories_are_admin_only(api, normal_user):
    api.force_authenticate(normal_user)

    assert api.get("/api/login-histories/").status_code == 403


def test_login_history_is_listed(api, admin_user, normal_user, user_password):
    api.post(
        "/api/auth/login/",
        {"employee_no": "A1234", "full_name": "홍길동", "password": user_password},
        format="json",
    )
    api.force_authenticate(admin_user)

    res = api.get("/api/login-histories/")

    assert res.data["count"] >= 1
    assert res.data["results"][0]["attempted_employee_no"] == "A1234"
