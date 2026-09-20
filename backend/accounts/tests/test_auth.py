"""인증 API 테스트 (specs/01 §9, specs/15 §14)."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import LoginHistory, Role, User

pytestmark = pytest.mark.django_db

LOGIN_URL = "/api/auth/login/"
ME_URL = "/api/auth/me/"
LOGOUT_URL = "/api/auth/logout/"
CHANGE_PW_URL = "/api/auth/change-password/"


def login(api, employee_no="A1234", full_name="홍길동", password="pw1234"):
    return api.post(
        LOGIN_URL,
        {"employee_no": employee_no, "full_name": full_name, "password": password},
        format="json",
    )


# --- AC-01-1 / AC-01-2 는 test_seed.py 참조 ---


def test_login_success_returns_profile(api, normal_user, user_password):
    res = login(api, password=user_password)

    assert res.status_code == 200
    assert res.data["employee_no"] == "A1234"
    assert res.data["full_name"] == "홍길동"
    assert res.data["role"] == Role.USER
    assert res.data["is_admin"] is False

    normal_user.refresh_from_db()
    assert normal_user.last_login_at is not None
    assert LoginHistory.objects.filter(user=normal_user, success=True).count() == 1


def test_ac_01_3_wrong_full_name_fails_even_with_correct_credentials(
    api, normal_user, user_password
):
    """AC-01-3: 성명이 틀리면 사번·비밀번호가 맞아도 로그인에 실패한다."""
    res = login(api, full_name="임꺽정", password=user_password)

    assert res.status_code == 400
    assert res.data["error"]["code"] == "LOGIN_FAILED"
    # 계정 존재 여부가 드러나지 않는 통일 메시지여야 한다.
    assert res.data["error"]["message"] == "성명, 사번 또는 비밀번호가 올바르지 않습니다."


def test_full_name_compared_ignoring_spaces(api, normal_user, user_password):
    res = login(api, full_name=" 홍 길 동 ", password=user_password)
    assert res.status_code == 200


def test_unknown_employee_no_uses_same_message(api, db):
    res = login(api, employee_no="ZZ999", full_name="없는사람", password="whatever")

    assert res.status_code == 400
    assert res.data["error"]["message"] == "성명, 사번 또는 비밀번호가 올바르지 않습니다."


def test_inactive_account_gets_distinct_message(api, normal_user, user_password):
    normal_user.is_active = False
    normal_user.save(update_fields=["is_active"])

    res = login(api, password=user_password)

    assert res.status_code == 400
    assert res.data["error"]["code"] == "ACCOUNT_INACTIVE"
    assert "비활성화된 계정" in res.data["error"]["message"]


def test_lockout_after_consecutive_failures(api, normal_user, seeded):
    """specs/01 §3.2 — 연속 실패가 임계치에 도달하면 해당 사번을 일시 차단한다."""
    for _ in range(5):
        assert login(api, password="wrong").status_code == 400

    res = login(api, password="pw1234")  # 올바른 비밀번호여도 잠금이 우선한다.

    assert res.status_code == 429
    assert res.data["error"]["code"] == "LOGIN_LOCKED"
    assert res.data["error"]["details"]["retry_after_sec"] > 0


def test_lockout_expires_after_window(api, normal_user, seeded, user_password):
    for _ in range(5):
        login(api, password="wrong")

    # 실패 이력을 잠금 시간(5분) 이전으로 되돌린다.
    LoginHistory.objects.all().update(created_at=timezone.now() - timedelta(minutes=6))

    assert login(api, password=user_password).status_code == 200


def test_successful_login_resets_failure_streak(api, normal_user, seeded, user_password):
    for _ in range(4):
        login(api, password="wrong")
    assert login(api, password=user_password).status_code == 200

    api.post(LOGOUT_URL)
    for _ in range(4):
        login(api, password="wrong")

    # 성공 이후로 다시 4회이므로 아직 잠기지 않아야 한다.
    assert login(api, password=user_password).status_code == 200


# --- AC-15-1: 비인증 401 ---


@pytest.mark.parametrize("url", [ME_URL, LOGOUT_URL, CHANGE_PW_URL])
def test_ac_15_1_unauthenticated_requests_get_401(api, db, url):
    res = api.get(url) if url == ME_URL else api.post(url, {}, format="json")

    assert res.status_code == 401
    assert res.data["error"]["code"] == "NOT_AUTHENTICATED"


def test_me_returns_current_user(api, normal_user, user_password):
    login(api, password=user_password)

    res = api.get(ME_URL)

    assert res.status_code == 200
    assert res.data["employee_no"] == "A1234"


def test_logout_clears_session(api, normal_user, user_password):
    login(api, password=user_password)

    assert api.post(LOGOUT_URL).status_code == 204
    assert api.get(ME_URL).status_code == 401


# --- 비밀번호 변경 (specs/01 §6) ---


def test_change_password_clears_must_change_flag(api, normal_user, user_password):
    normal_user.must_change_password = True
    normal_user.save(update_fields=["must_change_password"])
    login(api, password=user_password)

    res = api.post(
        CHANGE_PW_URL,
        {"current_password": user_password, "new_password": "newpw123"},
        format="json",
    )

    assert res.status_code == 204
    normal_user.refresh_from_db()
    assert normal_user.check_password("newpw123")
    assert normal_user.must_change_password is False
    # 변경 후에도 세션이 유지된다.
    assert api.get(ME_URL).status_code == 200


def test_change_password_rejects_wrong_current(api, normal_user, user_password):
    login(api, password=user_password)

    res = api.post(
        CHANGE_PW_URL,
        {"current_password": "nope", "new_password": "newpw123"},
        format="json",
    )

    assert res.status_code == 400
    assert res.data["error"]["code"] == "INVALID_CURRENT_PASSWORD"
    normal_user.refresh_from_db()
    assert normal_user.check_password(user_password)


def test_change_password_enforces_min_length_4(api, normal_user, user_password):
    """specs/01 §6 — MinimumLengthValidator(4) 만 활성화한다."""
    login(api, password=user_password)

    res = api.post(
        CHANGE_PW_URL,
        {"current_password": user_password, "new_password": "ab"},
        format="json",
    )

    assert res.status_code == 400
    assert res.data["error"]["code"] == "VALIDATION_ERROR"
    assert "new_password" in res.data["error"]["details"]


def test_short_but_valid_password_qwer_is_accepted(db):
    """기본 관리자 비밀번호 'qwer'(4자)가 정책상 허용되어야 한다."""
    from django.contrib.auth.password_validation import validate_password

    validate_password("qwer")  # 예외가 나지 않아야 한다.


# --- 에러 포맷 (AC-15-3) ---


def test_ac_15_3_error_format_is_consistent(api, db):
    res = api.post(LOGIN_URL, {"employee_no": "A1234"}, format="json")

    assert res.status_code == 400
    assert set(res.data.keys()) == {"error"}
    assert res.data["error"]["code"] == "VALIDATION_ERROR"
    assert "full_name" in res.data["error"]["details"]


def test_csrf_endpoint_is_public(api, db):
    res = api.get("/api/auth/csrf/")

    assert res.status_code == 200
    assert res.data["csrf_token"]


def test_login_history_records_failure_reason(api, normal_user):
    login(api, password="wrong")

    history = LoginHistory.objects.get()
    assert history.success is False
    assert history.fail_reason == "BAD_PASSWORD"
    assert history.attempted_employee_no == "A1234"


def test_employee_no_is_normalized_to_uppercase(api, db, user_password):
    User.objects.create_user(employee_no="C9999", full_name="이순신", password=user_password)

    res = login(api, employee_no="c9999", full_name="이순신", password=user_password)

    assert res.status_code == 200


def test_login_url_name_resolves():
    assert reverse("auth-login") == LOGIN_URL
