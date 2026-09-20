"""권한 테스트 (AC-01-5, AC-15-2).

관리자 전용 API는 Phase 6에서 추가되므로, 여기서는 IsAdminRole 권한 클래스 자체를
임시 뷰에 붙여 검증한다. 실제 /api/settings/ 에 대한 403 검증은 Phase 6에서 추가한다.
"""

import pytest
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework.views import APIView

from accounts.permissions import IsAdminRole

pytestmark = pytest.mark.django_db


class _AdminOnlyView(APIView):
    """관리자 전용 엔드포인트를 흉내 낸 임시 뷰."""

    permission_classes = [IsAdminRole]

    def get(self, request):
        return Response({"ok": True})


@pytest.fixture
def view():
    return _AdminOnlyView.as_view()


@pytest.fixture
def factory():
    return APIRequestFactory()


def test_ac_15_1_anonymous_gets_401(view, factory):
    res = view(factory.get("/dummy/"))
    res.render()

    assert res.status_code == 401
    assert res.data["error"]["code"] == "NOT_AUTHENTICATED"


def test_ac_01_5_normal_user_gets_403(view, factory, normal_user):
    request = factory.get("/dummy/")
    force_authenticate(request, user=normal_user)

    res = view(request)
    res.render()

    assert res.status_code == 403
    assert res.data["error"]["code"] == "PERMISSION_DENIED"


def test_admin_role_is_allowed(view, factory, admin_user):
    request = factory.get("/dummy/")
    force_authenticate(request, user=admin_user)

    res = view(request)
    res.render()

    assert res.status_code == 200


def test_is_staff_alone_does_not_grant_app_permission(view, factory, normal_user):
    """specs/01 §2 — 앱 권한은 role 로만 판정한다. is_staff/is_superuser 는 /admin/ 전용."""
    normal_user.is_staff = True
    normal_user.is_superuser = True
    normal_user.save(update_fields=["is_staff", "is_superuser"])

    request = factory.get("/dummy/")
    force_authenticate(request, user=normal_user)

    res = view(request)
    res.render()

    assert res.status_code == 403


def test_inactive_admin_is_rejected(view, factory, admin_user):
    admin_user.is_active = False
    admin_user.save(update_fields=["is_active"])

    request = factory.get("/dummy/")
    force_authenticate(request, user=admin_user)

    res = view(request)
    res.render()

    assert res.status_code in (401, 403)
