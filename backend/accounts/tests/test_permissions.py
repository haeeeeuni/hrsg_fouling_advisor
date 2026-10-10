"""권한 전수 검사 (specs/10 AC-10-1·2, specs/08 AC-08-1).

새 엔드포인트를 만들면 아래 목록에 추가한다. 빠뜨리면 권한 구멍이 테스트에 걸리지 않는다.
"""

import pytest

pytestmark = pytest.mark.django_db

# (메서드, 경로) — 승인된 사용자 이상만
USER_ENDPOINTS = [
    ("patch", "/api/auth/me/"),
    ("post", "/api/auth/password/"),
    ("get", "/api/jobs/some-job-id/"),
    ("get", "/api/calculator/options/"),
    ("post", "/api/calculator/loss/"),
    ("post", "/api/calculator/methods/"),
    ("post", "/api/calculator/pinch-approach/"),
    ("get", "/api/checklist/requests/"),
    ("post", "/api/checklist/requests/"),
]

# (메서드, 경로) — 관리자만. {pk} 는 존재하는 사용자로 바뀐다.
ADMIN_ENDPOINTS = [
    ("get", "/api/admin/overview/"),
    ("get", "/api/admin/users/"),
    ("get", "/api/admin/users/{pk}/"),
    ("patch", "/api/admin/users/{pk}/"),
    ("delete", "/api/admin/users/{pk}/"),
    ("post", "/api/admin/users/{pk}/approve/"),
    ("post", "/api/admin/users/{pk}/reject/"),
    ("post", "/api/admin/users/{pk}/reset-password/"),
    ("get", "/api/admin/login-histories/"),
    ("get", "/api/admin/audit-logs/"),
    ("get", "/api/admin/settings/"),
    ("patch", "/api/admin/settings/"),
    ("post", "/api/admin/settings/login_max_failures/reset/"),
    ("get", "/api/admin/gt-models/"),
    ("post", "/api/admin/gt-models/"),
    ("get", "/api/admin/gt-models/template/"),
    ("post", "/api/admin/gt-models/import/"),
    ("get", "/api/admin/cleaning-methods/"),
    ("post", "/api/admin/cleaning-methods/"),
    ("get", "/api/admin/smp-prices/"),
    ("post", "/api/admin/smp-prices/"),
    ("get", "/api/admin/calc-parameter-sets/"),
    ("post", "/api/admin/calc-parameter-sets/"),
    ("post", "/api/admin/calc-parameter-sets/preview/"),
    ("get", "/api/admin/checklist-items/"),
    ("post", "/api/admin/checklist-items/"),
    ("post", "/api/admin/checklist-items/reorder/"),
    ("get", "/api/admin/checklist-items/export/"),
    ("post", "/api/admin/checklist-items/import/"),
]

PUBLIC_ENDPOINTS = [
    ("get", "/api/auth/csrf/"),
    ("get", "/api/auth/me/"),
    ("get", "/api/auth/username-available/?username=abcd"),
    ("get", "/api/health/live/"),
    ("get", "/api/health/ready/"),
]


def call(api, method, path, user):
    return getattr(api, method)(path.format(pk=user.pk), {}, format="json")


@pytest.mark.parametrize(("method", "path"), USER_ENDPOINTS + ADMIN_ENDPOINTS)
def test_anonymous_gets_401(api, normal_user, method, path):
    assert call(api, method, path, normal_user).status_code == 401


@pytest.mark.parametrize(("method", "path"), USER_ENDPOINTS + ADMIN_ENDPOINTS)
def test_pending_user_is_refused(api, pending_user, method, path):
    """AC-01-8 · AC-10-2 — 승인 대기 세션은 어떤 업무 API 도 못 쓴다."""
    api.force_authenticate(pending_user)

    assert call(api, method, path, pending_user).status_code == 403


@pytest.mark.parametrize(("method", "path"), ADMIN_ENDPOINTS)
def test_normal_user_gets_403_on_admin_api(api, normal_user, method, path):
    api.force_authenticate(normal_user)

    assert call(api, method, path, normal_user).status_code == 403


@pytest.mark.parametrize(("method", "path"), ADMIN_ENDPOINTS)
def test_pending_admin_role_is_refused(api, pending_user, method, path):
    """역할이 ADMIN 이어도 승인되지 않았으면 관리자 API 를 못 쓴다."""
    pending_user.role = "ADMIN"
    pending_user.save()
    api.force_authenticate(pending_user)

    assert call(api, method, path, pending_user).status_code == 403


@pytest.mark.parametrize(("method", "path"), PUBLIC_ENDPOINTS)
def test_public_endpoints_are_open(api, method, path):
    assert getattr(api, method)(path).status_code == 200


def test_error_format_is_uniform(api):
    """AC-10-5"""
    body = api.get("/api/admin/users/").data

    assert set(body) == {"error"}
    assert {"code", "message"} <= set(body["error"])
