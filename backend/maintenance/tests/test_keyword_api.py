"""오염 키워드 사전 API (specs/10 §3)."""

import pytest

URL = "/api/fouling-keywords/"

pytestmark = pytest.mark.django_db


def test_duplicate_keyword_in_same_category_explains_why(api, admin_user):
    api.force_authenticate(admin_user)
    payload = {"keyword": "중복확인키워드", "category": "CLEANING", "weight": 1.0}
    assert api.post(URL, payload, format="json").status_code == 201

    res = api.post(URL, payload, format="json")

    assert res.status_code == 400
    # 기본 문구("keyword, category 은/는 반드시 고유해야 합니다")가 아니라 이유가 전해지는 문구여야 한다.
    assert res.data["error"]["details"]["non_field_errors"] == ["같은 분류에 이미 등록된 키워드입니다."]


def test_same_keyword_in_another_category_is_allowed(api, admin_user):
    api.force_authenticate(admin_user)
    api.post(URL, {"keyword": "분류별키워드", "category": "CLEANING"}, format="json")

    res = api.post(URL, {"keyword": "분류별키워드", "category": "EXCLUDE"}, format="json")

    assert res.status_code == 201
