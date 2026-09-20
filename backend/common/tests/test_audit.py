"""감사 로그 (specs/13 §7). 일부 DB 불필요."""

import pytest

from common import audit

# --- 스냅샷 (DB 불필요) ---


def test_sensitive_fields_are_never_snapshotted():
    """비밀번호는 감사 로그에도 남기지 않는다 (AGENTS.md §7)."""

    class Fake:
        class _meta:
            fields = []

    obj = Fake()
    obj.password = "secret"
    obj.username = "kim"

    result = audit.snapshot(obj, fields=["password", "username"])

    assert "password" not in result
    assert result["username"] == "kim"


def test_snapshot_of_none_is_empty():
    assert audit.snapshot(None) == {}


def test_jsonify_handles_common_types():
    from datetime import date, datetime
    from decimal import Decimal

    assert audit._jsonify(None) is None
    assert audit._jsonify(3) == 3
    assert audit._jsonify("a") == "a"
    assert audit._jsonify(Decimal("1.5")) == 1.5
    assert audit._jsonify(date(2024, 1, 1)) == "2024-01-01"
    assert audit._jsonify(datetime(2024, 1, 1, 9)) == "2024-01-01T09:00:00"
    assert audit._jsonify({"a": 1}) == {"a": 1}


def test_client_ip_prefers_forwarded_header():
    class Req:
        META = {"HTTP_X_FORWARDED_FOR": "1.2.3.4, 5.6.7.8", "REMOTE_ADDR": "9.9.9.9"}

    assert audit.client_ip(Req()) == "1.2.3.4"


def test_client_ip_falls_back_to_remote_addr():
    class Req:
        META = {"REMOTE_ADDR": "9.9.9.9"}

    assert audit.client_ip(Req()) == "9.9.9.9"


def test_client_ip_of_none():
    assert audit.client_ip(None) is None


# --- 기록 (DB 필요) ---


@pytest.mark.django_db
def test_record_creates_log(admin_user):
    class Req:
        user = admin_user
        META = {"REMOTE_ADDR": "10.0.0.1"}

    log = audit.record(
        request=Req(),
        action="UPDATE",
        target_type="Setting",
        target_id="fouling_threshold",
        target_label="오염도 임계치",
        before={"value": "60"},
        after={"value": "50"},
    )

    assert log is not None
    assert log.actor == admin_user
    assert log.ip == "10.0.0.1"
    assert log.before == {"value": "60"}


@pytest.mark.django_db
def test_record_without_request_has_no_actor():
    log = audit.record(request=None, action="CREATE", target_type="Unit", target_id=1)

    assert log.actor is None
    assert log.ip is None


@pytest.mark.django_db
def test_audit_log_api_is_admin_only(api, normal_user):
    api.force_authenticate(normal_user)

    assert api.get("/api/audit-logs/").status_code == 403


@pytest.mark.django_db
def test_audit_log_api_lists_and_filters(api, admin_user):
    class Req:
        user = admin_user
        META = {}

    audit.record(request=Req(), action="UPDATE", target_type="Setting", target_id="a")
    audit.record(request=Req(), action="CREATE", target_type="Unit", target_id="1")
    api.force_authenticate(admin_user)

    assert api.get("/api/audit-logs/").data["count"] == 2
    assert api.get("/api/audit-logs/", {"target_type": "Unit"}).data["count"] == 1
    assert api.get("/api/audit-logs/", {"action": "UPDATE"}).data["count"] == 1


@pytest.mark.django_db
def test_audit_log_includes_actor_name(api, admin_user):
    class Req:
        user = admin_user
        META = {}

    audit.record(request=Req(), action="CREATE", target_type="Unit", target_id="1")
    api.force_authenticate(admin_user)

    row = api.get("/api/audit-logs/").data["results"][0]
    assert row["actor_name"] == admin_user.full_name
    assert row["action_label"] == "생성"
