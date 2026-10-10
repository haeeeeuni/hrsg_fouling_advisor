"""회원가입·로그인·내 정보 (specs/01 AC-01-1·2·3·6·8·9)."""

import pytest

from accounts.models import ApprovalStatus, LoginHistory, User
from common.constants import FAIL_BAD_PASSWORD, FAIL_PENDING

pytestmark = pytest.mark.django_db

SIGNUP = "/api/auth/signup/"
LOGIN = "/api/auth/login/"
LOGOUT = "/api/auth/logout/"
ME = "/api/auth/me/"
PASSWORD = "/api/auth/password/"
AVAILABLE = "/api/auth/username-available/"


def signup_payload(**overrides):
    payload = {
        "username": "Park.Eng",
        "password": "good-pass-9",
        "password_confirm": "good-pass-9",
        "full_name": " 박엔지 ",
        "organization": "협력사 A",
        "signup_reason": "세정 검토",
    }
    payload.update(overrides)
    return payload


# --- 회원가입 ---


def test_signup_creates_pending_user_without_logging_in(api):
    res = api.post(SIGNUP, signup_payload(), format="json")

    assert res.status_code == 201
    assert res.data["approval_status"] == ApprovalStatus.PENDING
    user = User.objects.get(username="park.eng")  # 소문자로 저장
    assert user.full_name == "박엔지"
    assert user.approval_status == ApprovalStatus.PENDING
    assert user.role == "USER"
    # 자동 로그인하지 않는다(AUTH-2).
    assert api.get(ME).data["authenticated"] is False


def test_signup_rejects_case_only_duplicate(api, normal_user):
    """AC-01-6 — 대소문자만 다른 ID 로 가입할 수 없다."""
    res = api.post(SIGNUP, signup_payload(username="HONG"), format="json")

    assert res.status_code == 400
    assert "이미 사용 중인 ID" in res.data["error"]["details"]["username"][0]


@pytest.mark.parametrize("username", ["abc", "has space", "한글아이디", "a" * 31, "bad!char"])
def test_signup_rejects_invalid_username(api, username):
    res = api.post(SIGNUP, signup_payload(username=username), format="json")

    assert res.status_code == 400
    assert "username" in res.data["error"]["details"]


@pytest.mark.parametrize(
    ("password", "reason"),
    [("short1", "8자 미만"), ("1234567890", "숫자만")],
)
def test_signup_enforces_password_policy(api, password, reason):
    res = api.post(
        SIGNUP, signup_payload(password=password, password_confirm=password), format="json"
    )

    assert res.status_code == 400, reason
    assert "password" in res.data["error"]["details"]


def test_signup_requires_matching_confirmation(api):
    res = api.post(SIGNUP, signup_payload(password_confirm="other-pass-9"), format="json")

    assert res.status_code == 400
    assert "password_confirm" in res.data["error"]["details"]


def test_rejected_username_cannot_sign_up_again(api, pending_user, admin_user):
    pending_user.approval_status = ApprovalStatus.REJECTED
    pending_user.save()

    res = api.post(SIGNUP, signup_payload(username="newbie"), format="json")

    assert res.status_code == 400


def test_username_available(api, normal_user):
    assert api.get(AVAILABLE, {"username": "free.id"}).data["available"] is True
    taken = api.get(AVAILABLE, {"username": "Hong"}).data
    assert taken["available"] is False
    assert "이미 사용 중" in taken["reason"]
    assert api.get(AVAILABLE, {"username": "ab"}).data["available"] is False


# --- 로그인 ---


def test_login_succeeds_case_insensitively(api, normal_user, user_password):
    res = api.post(LOGIN, {"username": " HONG ", "password": user_password}, format="json")

    assert res.status_code == 200
    assert res.data["user"]["username"] == "hong"
    assert api.get(ME).data["authenticated"] is True
    normal_user.refresh_from_db()
    assert normal_user.last_login_at is not None


def test_pending_user_with_correct_password_sees_pending_notice(api, pending_user, user_password):
    """AC-01-1"""
    res = api.post(LOGIN, {"username": "newbie", "password": user_password}, format="json")

    assert res.status_code == 403
    assert res.data["error"]["code"] == "ACCOUNT_PENDING"
    assert api.get(ME).data["authenticated"] is False


def test_pending_user_with_wrong_password_sees_generic_message(api, pending_user):
    """AC-01-2 — 비밀번호가 틀리면 상태를 알려 주지 않는다."""
    res = api.post(LOGIN, {"username": "newbie", "password": "wrong-pass-1"}, format="json")

    assert res.status_code == 400
    assert res.data["error"]["code"] == "LOGIN_FAILED"
    assert res.data["error"]["message"] == "ID 또는 비밀번호가 올바르지 않습니다."


def test_unknown_user_gets_same_message_as_wrong_password(api, normal_user):
    unknown = api.post(LOGIN, {"username": "nobody", "password": "x-password-1"}, format="json")
    wrong = api.post(LOGIN, {"username": "hong", "password": "x-password-1"}, format="json")

    assert unknown.status_code == wrong.status_code == 400
    assert unknown.data == wrong.data


def test_rejected_user_sees_reason(api, pending_user, user_password):
    """AC-01-3 — 반려 사유가 로그인 시 보인다."""
    pending_user.approval_status = ApprovalStatus.REJECTED
    pending_user.rejection_reason = "소속 확인 불가"
    pending_user.save()

    res = api.post(LOGIN, {"username": "newbie", "password": user_password}, format="json")

    assert res.status_code == 403
    assert res.data["error"]["code"] == "ACCOUNT_REJECTED"
    assert "소속 확인 불가" in res.data["error"]["message"]


def test_inactive_user_cannot_log_in(api, normal_user, user_password):
    normal_user.is_active = False
    normal_user.save()

    res = api.post(LOGIN, {"username": "hong", "password": user_password}, format="json")

    assert res.status_code == 403
    assert res.data["error"]["code"] == "ACCOUNT_INACTIVE"


def test_login_attempts_are_recorded(api, pending_user, user_password):
    api.post(LOGIN, {"username": "newbie", "password": "wrong-pass-1"}, format="json")
    api.post(LOGIN, {"username": "newbie", "password": user_password}, format="json")

    reasons = list(
        LoginHistory.objects.order_by("created_at").values_list("fail_reason", flat=True)
    )
    assert reasons == [FAIL_BAD_PASSWORD, FAIL_PENDING]


def test_lockout_after_consecutive_failures(api, normal_user, user_password, seeded):
    """AC-01-9 — 5회 연속 실패 후 올바른 비밀번호도 막힌다."""
    for _ in range(5):
        api.post(LOGIN, {"username": "hong", "password": "wrong-pass-1"}, format="json")

    res = api.post(LOGIN, {"username": "hong", "password": user_password}, format="json")

    assert res.status_code == 429
    assert res.data["error"]["code"] == "LOGIN_LOCKED"
    assert res.data["error"]["details"]["retry_after_sec"] > 0


def test_status_failures_do_not_count_toward_lockout(api, pending_user, user_password, seeded):
    """승인 대기 계정이 맞는 비밀번호로 여러 번 시도해도 잠기지 않는다."""
    for _ in range(6):
        res = api.post(LOGIN, {"username": "newbie", "password": user_password}, format="json")

    assert res.data["error"]["code"] == "ACCOUNT_PENDING"


def test_login_throttle_by_ip(api, normal_user):
    codes = [
        api.post(
            LOGIN, {"username": f"x{i}user", "password": "p-assword1"}, format="json"
        ).status_code
        for i in range(11)
    ]

    assert codes[-1] == 429


# --- 세션·내 정보 ---


def test_me_is_public_and_reports_anonymous(api):
    res = api.get(ME)

    assert res.status_code == 200
    assert res.data == {"authenticated": False, "user": None}


def test_session_is_cut_when_approval_is_revoked(api, normal_user, user_password):
    """AC-01-8 — 로그인 후 승인 상태가 바뀌면 살아 있는 세션도 업무 API 를 못 쓴다."""
    api.post(LOGIN, {"username": "hong", "password": user_password}, format="json")
    normal_user.approval_status = ApprovalStatus.PENDING
    normal_user.save()

    assert api.patch(ME, {"organization": "x"}, format="json").status_code == 403
    assert api.get(ME).data["authenticated"] is False


def test_update_own_profile(api, normal_user):
    api.force_authenticate(normal_user)

    res = api.patch(ME, {"organization": "기술팀", "role": "ADMIN"}, format="json")

    assert res.status_code == 200
    normal_user.refresh_from_db()
    assert normal_user.organization == "기술팀"
    assert normal_user.role == "USER"  # 역할은 바꿀 수 없다


def test_logout(api, normal_user, user_password):
    api.post(LOGIN, {"username": "hong", "password": user_password}, format="json")

    assert api.post(LOGOUT).status_code == 204
    assert api.get(ME).data["authenticated"] is False


# --- 비밀번호 변경 ---


def test_change_password_clears_flag(api, normal_user, user_password):
    normal_user.must_change_password = True
    normal_user.save()
    api.post(LOGIN, {"username": "hong", "password": user_password}, format="json")

    res = api.post(
        PASSWORD,
        {"current_password": user_password, "new_password": "brand-new-7"},
        format="json",
    )

    assert res.status_code == 204
    normal_user.refresh_from_db()
    assert normal_user.check_password("brand-new-7")
    assert normal_user.must_change_password is False
    assert api.get(ME).data["authenticated"] is True  # 세션 유지


def test_change_password_requires_current(api, normal_user):
    api.force_authenticate(normal_user)

    res = api.post(
        PASSWORD, {"current_password": "wrong-pass-1", "new_password": "brand-new-7"}, format="json"
    )

    assert res.status_code == 400
    assert res.data["error"]["code"] == "INVALID_CURRENT_PASSWORD"


def test_change_password_applies_policy(api, normal_user, user_password):
    api.force_authenticate(normal_user)

    res = api.post(
        PASSWORD, {"current_password": user_password, "new_password": "12345678"}, format="json"
    )

    assert res.status_code == 400
