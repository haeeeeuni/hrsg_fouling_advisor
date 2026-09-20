"""호기·컬럼 매핑 API (specs/15 §4). PostgreSQL 필요."""

import pytest

from units.models import ColumnMapping, Unit

pytestmark = pytest.mark.django_db

UNITS_URL = "/api/units/"


@pytest.fixture
def unit(db):
    return Unit.objects.create(code="U1", name="1호기 HRSG", rated_power_mw=160, min_load_mw=60)


def login(api, user):
    api.force_authenticate(user=user)
    return api


def full_mapping_payload():
    return {
        "mappings": [
            {"standard_field": "timestamp", "source_column": "시각"},
            {"standard_field": "gt_power_mw", "source_column": "GT출력(MW)"},
            {"standard_field": "ambient_temp_c", "source_column": "대기온도(℃)"},
            {"standard_field": "gt_exhaust_temp_c", "source_column": "GT배기온도(℃)"},
            {"standard_field": "stack_temp_c", "source_column": "스택온도(℃)"},
            {
                "standard_field": "duct_burner_on",
                "source_column": "덕트버너상태",
                "bool_rule": "BOOL",
            },
            {"standard_field": "exhaust_flow", "source_column": "배기유량(kg/s)"},
            {"standard_field": "hrsg_gas_dp_kpa", "source_column": "HRSG가스차압(kPa)"},
        ]
    }


# --- 권한 (AC-15-1, AC-15-2) ---


def test_anonymous_cannot_list_units(api):
    assert api.get(UNITS_URL).status_code == 401


def test_normal_user_can_list_units(api, normal_user, unit):
    assert login(api, normal_user).get(UNITS_URL).status_code == 200


def test_normal_user_cannot_create_unit(api, normal_user):
    res = login(api, normal_user).post(
        UNITS_URL,
        {"code": "U2", "name": "2호기", "rated_power_mw": 160, "min_load_mw": 60},
        format="json",
    )

    assert res.status_code == 403
    assert res.data["error"]["code"] == "PERMISSION_DENIED"


def test_admin_can_create_unit(api, admin_user):
    res = login(api, admin_user).post(
        UNITS_URL,
        {"code": "U2", "name": "2호기", "rated_power_mw": 160, "min_load_mw": 60},
        format="json",
    )

    assert res.status_code == 201
    assert res.data["is_mapping_complete"] is False


def test_normal_user_cannot_read_column_mappings(api, normal_user, unit):
    res = login(api, normal_user).get(f"/api/units/{unit.id}/column-mappings/")

    assert res.status_code == 403


# --- 호기 검증 ---


def test_min_load_must_be_below_rated(api, admin_user):
    res = login(api, admin_user).post(
        UNITS_URL,
        {"code": "U3", "name": "3호기", "rated_power_mw": 100, "min_load_mw": 120},
        format="json",
    )

    assert res.status_code == 400
    assert "min_load_mw" in res.data["error"]["details"]


def test_duplicate_code_is_rejected(api, admin_user, unit):
    res = login(api, admin_user).post(
        UNITS_URL,
        {"code": "U1", "name": "중복", "rated_power_mw": 160, "min_load_mw": 60},
        format="json",
    )

    assert res.status_code == 400


# --- 매핑 (AC-02-1 ~ AC-02-4) ---


def test_ac_02_1_incomplete_mapping_marks_unit_incomplete(api, admin_user, unit):
    res = login(api, admin_user).put(
        f"/api/units/{unit.id}/column-mappings/",
        {"mappings": [{"standard_field": "timestamp", "source_column": "시각"}]},
        format="json",
    )

    assert res.status_code == 200
    assert res.data["is_mapping_complete"] is False
    assert {p["code"] for p in res.data["problems"]} >= {"REQUIRED_FIELD_UNMAPPED"}


def test_complete_mapping_marks_unit_complete(api, admin_user, unit):
    res = login(api, admin_user).put(
        f"/api/units/{unit.id}/column-mappings/", full_mapping_payload(), format="json"
    )

    assert res.status_code == 200
    assert res.data["is_mapping_complete"] is True
    assert res.data["problems"] == []


def test_ac_02_2_backpressure_only_unit_is_complete(api, admin_user, unit):
    payload = full_mapping_payload()
    payload["mappings"] = [
        m for m in payload["mappings"] if m["standard_field"] != "hrsg_gas_dp_kpa"
    ] + [{"standard_field": "gt_backpressure_kpa", "source_column": "GT배압(kPa)"}]

    res = login(api, admin_user).put(
        f"/api/units/{unit.id}/column-mappings/", payload, format="json"
    )

    assert res.data["is_mapping_complete"] is True


def test_ac_02_4_saving_mapping_creates_version_history(api, admin_user, unit):
    client = login(api, admin_user)
    client.put(f"/api/units/{unit.id}/column-mappings/", full_mapping_payload(), format="json")
    client.put(f"/api/units/{unit.id}/column-mappings/", full_mapping_payload(), format="json")

    res = client.get(f"/api/units/{unit.id}/column-mappings/versions/")

    assert res.status_code == 200
    assert [row["version"] for row in res.data] == [2, 1]
    assert len(res.data[0]["snapshot"]) == 8


def test_put_replaces_previous_mappings(api, admin_user, unit):
    client = login(api, admin_user)
    client.put(f"/api/units/{unit.id}/column-mappings/", full_mapping_payload(), format="json")
    client.put(
        f"/api/units/{unit.id}/column-mappings/",
        {"mappings": [{"standard_field": "timestamp", "source_column": "TS"}]},
        format="json",
    )

    assert ColumnMapping.objects.filter(unit=unit).count() == 1


def test_duplicate_standard_field_is_rejected(api, admin_user, unit):
    res = login(api, admin_user).put(
        f"/api/units/{unit.id}/column-mappings/",
        {
            "mappings": [
                {"standard_field": "timestamp", "source_column": "a"},
                {"standard_field": "timestamp", "source_column": "b"},
            ]
        },
        format="json",
    )

    assert res.status_code == 400


def test_threshold_rule_requires_threshold(api, admin_user, unit):
    res = login(api, admin_user).put(
        f"/api/units/{unit.id}/column-mappings/",
        {
            "mappings": [
                {
                    "standard_field": "duct_burner_on",
                    "source_column": "db",
                    "bool_rule": "THRESHOLD",
                }
            ]
        },
        format="json",
    )

    assert res.status_code == 400


def test_unknown_standard_field_is_rejected(api, admin_user, unit):
    res = login(api, admin_user).put(
        f"/api/units/{unit.id}/column-mappings/",
        {"mappings": [{"standard_field": "nope", "source_column": "a"}]},
        format="json",
    )

    assert res.status_code == 400


# --- 표준 항목 목록 / 데이터 요약 ---


def test_standard_fields_endpoint_marks_requirement(api, normal_user):
    res = login(api, normal_user).get("/api/standard-fields/")

    assert res.status_code == 200
    by_key = {row["key"]: row for row in res.data}
    assert by_key["stack_temp_c"]["requirement"] == "REQUIRED"
    assert by_key["gt_backpressure_kpa"]["requirement"] == "ALTERNATIVE"
    assert by_key["humidity_pct"]["requirement"] == "OPTIONAL"
    assert by_key["fuel_flow"]["substitutes"] == ["exhaust_flow"]


def test_data_summary_is_empty_for_new_unit(api, normal_user, unit):
    res = login(api, normal_user).get(f"/api/units/{unit.id}/data-summary/")

    assert res.status_code == 200
    assert res.data["row_count"] == 0
    assert res.data["period"]["start"] is None


# --- 삭제 보호 (specs/02 §2) ---


def test_unit_without_data_can_be_deleted(api, admin_user, unit):
    assert login(api, admin_user).delete(f"{UNITS_URL}{unit.id}/").status_code == 204


def test_unit_with_upload_batches_cannot_be_deleted(api, admin_user, unit):
    from ingestion.models import UploadBatch

    UploadBatch.objects.create(unit=unit, original_filename="x.csv")

    res = login(api, admin_user).delete(f"{UNITS_URL}{unit.id}/")

    assert res.status_code == 409
    assert res.data["error"]["code"] == "UNIT_HAS_DATA"
