"""헬스체크 (specs/18 §3, §7). PostgreSQL 필요."""

from unittest.mock import patch

import pytest

pytestmark = pytest.mark.django_db

LIVE = "/api/health/live/"
READY = "/api/health/ready/"


def test_liveness_is_open_without_auth(api):
    """컨테이너·LB 가 인증 없이 찔러야 한다."""
    res = api.get(LIVE)

    assert res.status_code == 200
    assert res.data["status"] == "ok"


def test_readiness_is_open_without_auth(api):
    res = api.get(READY)

    assert res.status_code == 200
    assert res.data["checks"]["database"] is True


def test_readiness_reports_503_when_database_is_down():
    """DB 가 끊기면 트래픽을 받으면 안 된다."""
    from rest_framework.test import APIClient

    with patch("common.views_health._check_database", return_value=False):
        res = APIClient().get(READY)

    assert res.status_code == 503
    assert res.data["status"] == "unavailable"


def test_health_does_not_leak_internals(api):
    """버전·경로·예외 메시지가 드러나면 안 된다."""
    body = str(api.get(READY).data)

    for leaked in ("Traceback", "psycopg", "/app/", "postgres://"):
        assert leaked not in body
