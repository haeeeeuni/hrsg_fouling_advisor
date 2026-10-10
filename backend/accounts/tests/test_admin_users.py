"""가입 승인·사용자 관리 (specs/01 AC-01-3·7, specs/08 AC-08-3)."""

import pytest

from accounts.models import ApprovalStatus, Role, User
from common.models import AuditLog

pytestmark = pytest.mark.django_db

USERS = "/api/admin/users/"
LOGIN = "/api/auth/login/"


def url(user, suffix=""):
    return f"{USERS}{user.pk}/{suffix}"


@pytest.fixture
def as_admin(api, admin_user):
    api.force_authenticate(admin_user)
    return api


# --- 승인·반려 ---


def test_pending_filter_lists_signups(as_admin, pending_user, normal_user):
    res = as_admin.get(USERS, {"approval_status": "PENDING"})

    assert [row["username"] for row in res.data["results"]] == ["newbie"]
    assert res.data["results"][0]["approval_status_label"] == "승인 대기"


def test_approve_lets_user_log_in(api, as_admin, pending_user, admin_user, user_password):
    """AC-01-3"""
    res = as_admin.post(url(pending_user, "approve/"))

    assert res.status_code == 200
    pending_user.refresh_from_db()
    assert pending_user.approval_status == ApprovalStatus.APPROVED
    assert pending_user.approved_by == admin_user
    assert pending_user.approved_at is not None

    api.force_authenticate(None)
    login = api.post(LOGIN, {"username": "newbie", "password": user_password}, format="json")
    assert login.status_code == 200


def test_reject_requires_reason(as_admin, pending_user):
    assert as_admin.post(url(pending_user, "reject/"), {}, format="json").status_code == 400
    assert (
        as_admin.post(url(pending_user, "reject/"), {"reason": "  "}, format="json").status_code
        == 400
    )

    res = as_admin.post(url(pending_user, "reject/"), {"reason": "소속 불명"}, format="json")

    assert res.status_code == 200
    pending_user.refresh_from_db()
    assert pending_user.approval_status == ApprovalStatus.REJECTED
    assert pending_user.rejection_reason == "소속 불명"


def test_rejected_user_can_be_approved_later(as_admin, pending_user):
    """AUTH-5 — 반려를 되돌리는 방법은 승인이다."""
    as_admin.post(url(pending_user, "reject/"), {"reason": "확인 필요"}, format="json")

    res = as_admin.post(url(pending_user, "approve/"))

    assert res.status_code == 200
    pending_user.refresh_from_db()
    assert pending_user.approval_status == ApprovalStatus.APPROVED
    assert pending_user.rejection_reason == ""


def test_only_pending_can_be_rejected(as_admin, normal_user):
    res = as_admin.post(url(normal_user, "reject/"), {"reason": "x"}, format="json")

    assert res.status_code == 409


def test_approving_twice_conflicts(as_admin, normal_user):
    assert as_admin.post(url(normal_user, "approve/")).status_code == 409


def test_approval_is_audited(as_admin, pending_user):
    as_admin.post(url(pending_user, "approve/"))

    log = AuditLog.objects.get(action="APPROVE")
    assert log.target_id == str(pending_user.pk)
    assert log.after == {"approval_status": "APPROVED"}


def test_overview_counts_pending(as_admin, pending_user):
    assert as_admin.get("/api/admin/overview/").data["pending_signups"] == 1


# --- 사용자 수정 ---


def test_admin_can_promote_user(as_admin, normal_user):
    res = as_admin.patch(url(normal_user), {"role": "ADMIN"}, format="json")

    assert res.status_code == 200
    normal_user.refresh_from_db()
    assert normal_user.role == Role.ADMIN


def test_username_and_approval_are_read_only_in_update(as_admin, pending_user):
    as_admin.patch(
        url(pending_user), {"username": "hacker", "approval_status": "APPROVED"}, format="json"
    )

    pending_user.refresh_from_db()
    assert pending_user.username == "newbie"
    assert pending_user.approval_status == ApprovalStatus.PENDING


def test_users_cannot_be_created_through_admin_api(as_admin):
    res = as_admin.post(USERS, {"username": "direct"}, format="json")

    assert res.status_code == 405


def test_last_admin_cannot_be_demoted_or_deactivated(as_admin, admin_user):
    """AC-01-7"""
    assert as_admin.patch(url(admin_user), {"is_active": False}, format="json").status_code == 409
    assert as_admin.delete(url(admin_user)).status_code == 409


def test_cannot_demote_self_even_with_other_admins(as_admin, admin_user, normal_user):
    normal_user.role = Role.ADMIN
    normal_user.save()

    res = as_admin.patch(url(admin_user), {"role": "USER"}, format="json")

    assert res.status_code == 409
    assert res.data["error"]["code"] == "CANNOT_DEMOTE_SELF"


def test_pending_admin_does_not_count_as_active_admin(as_admin, admin_user, pending_user):
    """승인 대기 상태의 관리자 역할 계정은 '마지막 관리자' 판정에 들어가지 않는다."""
    pending_user.role = Role.ADMIN
    pending_user.save()

    res = as_admin.patch(url(admin_user), {"is_active": False}, format="json")

    assert res.status_code == 409


def test_delete_deactivates_by_default(as_admin, normal_user):
    res = as_admin.delete(url(normal_user))

    assert res.data["deactivated"] is True
    normal_user.refresh_from_db()
    assert normal_user.is_active is False


def test_hard_delete(as_admin, pending_user):
    res = as_admin.delete(url(pending_user) + "?hard=true")

    assert res.status_code == 204
    assert not User.objects.filter(pk=pending_user.pk).exists()


def test_reset_password_forces_change(as_admin, normal_user):
    res = as_admin.post(url(normal_user, "reset-password/"), {"new_password": "reset-pass-3"})

    assert res.status_code == 200
    normal_user.refresh_from_db()
    assert normal_user.check_password("reset-pass-3")
    assert normal_user.must_change_password is True
    log = AuditLog.objects.get(target_id=str(normal_user.pk))
    assert "reset-pass-3" not in str(log.after)


def test_search_and_filters(as_admin, normal_user, pending_user):
    assert as_admin.get(USERS, {"search": "발전"}).data["count"] == 1
    assert as_admin.get(USERS, {"role": "ADMIN"}).data["count"] == 1
    assert as_admin.get(USERS, {"is_active": "true"}).data["count"] == 3


def test_login_histories(api, as_admin, normal_user):
    api.post(LOGIN, {"username": "hong", "password": "wrong-pass-1"}, format="json")

    res = as_admin.get("/api/admin/login-histories/", {"username": "hong"})

    assert res.data["count"] == 1
    assert res.data["results"][0]["fail_reason"] == "BAD_PASSWORD"
