"""세정 이력 API (specs/15 §7). PostgreSQL 필요."""

import pytest
from django.utils import timezone

from maintenance.models import CleaningEvent, CleaningSource
from units.models import Unit

pytestmark = pytest.mark.django_db

URL = "/api/cleaning-events/"


@pytest.fixture
def unit(db):
    return Unit.objects.create(code="U1", name="1호기", rated_power_mw=160, min_load_mw=60)


def payload(unit, **extra):
    return {
        "unit": unit.id,
        "cleaned_at": "2024-06-14T09:00:00+09:00",
        "method": "CHEMICAL",
        "cost": 28_000_000,
        "outage_days": 2,
        **extra,
    }


def test_anonymous_cannot_list(api, unit):
    assert api.get(URL).status_code == 401


def test_normal_user_can_list(api, normal_user, unit):
    api.force_authenticate(normal_user)

    assert api.get(URL).status_code == 200


def test_normal_user_cannot_create(api, normal_user, unit):
    api.force_authenticate(normal_user)

    res = api.post(URL, payload(unit), format="json")

    assert res.status_code == 403


def test_admin_can_create(api, admin_user, unit):
    api.force_authenticate(admin_user)

    res = api.post(URL, payload(unit), format="json")

    assert res.status_code == 201
    event = CleaningEvent.objects.get()
    assert event.source == CleaningSource.MANUAL
    assert event.created_by == admin_user


def test_end_before_start_is_rejected(api, admin_user, unit):
    api.force_authenticate(admin_user)

    res = api.post(URL, payload(unit, cleaned_end_at="2024-06-13T09:00:00+09:00"), format="json")

    assert res.status_code == 400
    assert "cleaned_end_at" in res.data["error"]["details"]


def test_negative_cost_is_rejected(api, admin_user, unit):
    api.force_authenticate(admin_user)

    res = api.post(URL, payload(unit, cost=-1), format="json")

    assert res.status_code == 400


def test_duplicate_date_is_allowed_but_warned(api, admin_user, unit):
    api.force_authenticate(admin_user)
    api.post(URL, payload(unit), format="json")

    res = api.post(URL, payload(unit), format="json")

    assert res.status_code == 201
    assert "warning" in res.data
    assert CleaningEvent.objects.count() == 2


def test_filter_by_unit(api, normal_user, admin_user, unit):
    other = Unit.objects.create(code="U2", name="2호기", rated_power_mw=160, min_load_mw=60)
    CleaningEvent.objects.create(unit=unit, cleaned_at=timezone.now())
    CleaningEvent.objects.create(unit=other, cleaned_at=timezone.now())
    api.force_authenticate(normal_user)

    res = api.get(URL, {"unit_id": unit.id})

    assert res.data["count"] == 1


def test_admin_can_delete(api, admin_user, unit):
    """specs/10 §4 — 삭제는 영향 범위를 함께 알려야 하므로 204 가 아니라 200 + 본문이다."""
    event = CleaningEvent.objects.create(unit=unit, cleaned_at=timezone.now())
    api.force_authenticate(admin_user)

    res = api.delete(f"{URL}{event.id}/")

    assert res.status_code == 200
    assert res.data["deleted"] is True
    assert "impact" in res.data
    assert res.data["note"]
    assert not CleaningEvent.objects.filter(pk=event.id).exists()
