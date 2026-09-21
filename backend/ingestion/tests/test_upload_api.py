"""업로드 검증·적재 API (specs/15 §5). PostgreSQL + Celery eager 필요."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from ingestion.models import BatchStatus, Measurement, UploadBatch
from units.models import ColumnMapping, Unit

pytestmark = pytest.mark.django_db

VALIDATE_URL = "/api/uploads/operation/validate/"

CSV_BODY = (
    "시각,GT출력(MW),대기온도(℃),GT배기온도(℃),배기유량(kg/s),"
    "HRSG가스차압(kPa),스택온도(℃),덕트버너상태\n"
    "2024-01-01 00:00:00,150,10,600,400,3.0,110,0\n"
    "2024-01-01 00:10:00,151,10,601,401,3.1,111,0\n"
    "2024-01-01 00:20:00,152,10,602,402,3.2,112,1\n"
)

MAPPING = [
    ("timestamp", "시각"),
    ("gt_power_mw", "GT출력(MW)"),
    ("ambient_temp_c", "대기온도(℃)"),
    ("gt_exhaust_temp_c", "GT배기온도(℃)"),
    ("exhaust_flow", "배기유량(kg/s)"),
    ("hrsg_gas_dp_kpa", "HRSG가스차압(kPa)"),
    ("stack_temp_c", "스택온도(℃)"),
    ("duct_burner_on", "덕트버너상태"),
]


@pytest.fixture
def mapped_unit(db):
    unit = Unit.objects.create(code="U1", name="1호기", rated_power_mw=160, min_load_mw=60)
    for field, column in MAPPING:
        ColumnMapping.objects.create(
            unit=unit,
            standard_field=field,
            source_column=column,
            bool_rule="BOOL" if field == "duct_burner_on" else "",
        )
    return unit


@pytest.fixture
def unmapped_unit(db):
    return Unit.objects.create(code="U9", name="9호기", rated_power_mw=160, min_load_mw=60)


def upload_file(body: str = CSV_BODY, name: str = "op.csv"):
    return SimpleUploadedFile(name, body.encode("utf-8"), content_type="text/csv")


def post_validate(api, unit, body=CSV_BODY, **extra):
    return api.post(
        VALIDATE_URL, {"unit_id": unit.id, "file": upload_file(body), **extra}, format="multipart"
    )


# --- 권한 ---


def test_anonymous_cannot_upload(api, mapped_unit):
    assert post_validate(api, mapped_unit).status_code == 401


# --- 검증 단계 ---


def test_validate_returns_202_with_job_id(api, normal_user, mapped_unit):
    api.force_authenticate(normal_user)

    res = post_validate(api, mapped_unit)

    assert res.status_code == 202
    assert res.data["job_id"]
    assert res.data["batch_id"]


def test_validate_does_not_write_measurements(api, normal_user, mapped_unit):
    """검증 통과 전에는 DB에 저장하지 않는다 (specs/03 §2)."""
    api.force_authenticate(normal_user)

    post_validate(api, mapped_unit)

    assert Measurement.objects.count() == 0
    assert UploadBatch.objects.get().status == BatchStatus.VALIDATED


def test_ac_02_1_unmapped_unit_upload_is_blocked(api, normal_user, unmapped_unit):
    """AC-02-1: 매핑 미완료 호기는 업로드가 차단된다."""
    api.force_authenticate(normal_user)

    res = post_validate(api, unmapped_unit)

    assert res.status_code == 400
    assert res.data["error"]["code"] == "UNIT_MAPPING_INCOMPLETE"
    assert res.data["error"]["details"]["problems"]


def test_inactive_unit_upload_is_blocked(api, normal_user, mapped_unit):
    mapped_unit.is_active = False
    mapped_unit.save(update_fields=["is_active"])
    api.force_authenticate(normal_user)

    assert post_validate(api, mapped_unit).status_code == 400


def test_non_csv_file_is_rejected(api, normal_user, mapped_unit):
    api.force_authenticate(normal_user)

    res = api.post(
        VALIDATE_URL,
        {"unit_id": mapped_unit.id, "file": upload_file(CSV_BODY, "op.xlsx")},
        format="multipart",
    )

    assert res.status_code == 400
    assert res.data["error"]["code"] == "UNSUPPORTED_FILE_TYPE"


# --- 적재 단계 ---


def commit(api, batch_id, **body):
    return api.post(f"/api/uploads/{batch_id}/commit/", body, format="json")


def test_commit_loads_measurements(api, normal_user, mapped_unit):
    api.force_authenticate(normal_user)
    batch_id = post_validate(api, mapped_unit).data["batch_id"]

    res = commit(api, batch_id)

    assert res.status_code == 202
    assert Measurement.objects.filter(unit=mapped_unit).count() == 3
    row = Measurement.objects.order_by("timestamp").first()
    assert row.gt_power_mw == 150
    assert row.duct_burner_on is False


def test_commit_requires_validated_status(api, normal_user, mapped_unit):
    api.force_authenticate(normal_user)
    batch = UploadBatch.objects.create(
        unit=mapped_unit, original_filename="x.csv", status=BatchStatus.PENDING
    )

    res = commit(api, batch.id)

    assert res.status_code == 409
    assert res.data["error"]["code"] == "VALIDATION_NOT_PASSED"


def test_ac_03_3_same_file_twice_does_not_duplicate_rows(api, normal_user, mapped_unit):
    """AC-03-3: 같은 파일을 두 번 적재해도 Measurement 행이 중복 증가하지 않는다."""
    api.force_authenticate(normal_user)
    first = post_validate(api, mapped_unit).data["batch_id"]
    commit(api, first)

    second = post_validate(api, mapped_unit, confirm_duplicate_file=True).data["batch_id"]
    commit(api, second)

    assert Measurement.objects.filter(unit=mapped_unit).count() == 3


def test_duplicate_file_needs_confirmation(api, normal_user, mapped_unit):
    api.force_authenticate(normal_user)
    batch_id = post_validate(api, mapped_unit).data["batch_id"]
    commit(api, batch_id)

    res = post_validate(api, mapped_unit)

    assert res.status_code == 409
    assert res.data["error"]["code"] == "DUPLICATE_FILE"


def test_ac_03_2_unparseable_rows_are_skipped_and_counted(api, normal_user, mapped_unit):
    body = CSV_BODY + "쓰레기,1,2,3,4,5,6,0\n"
    api.force_authenticate(normal_user)

    batch_id = post_validate(api, mapped_unit, body=body).data["batch_id"]
    commit(api, batch_id)

    batch = UploadBatch.objects.get(pk=batch_id)
    assert batch.row_loaded == 3
    assert batch.row_skipped == 1
    codes = {i["code"] for i in batch.validation_report["row_errors"]}
    assert "TIMESTAMP_PARSE_ERROR" in codes


def test_ac_03_5_data_summary_reflects_loaded_period(api, normal_user, mapped_unit):
    """AC-03-5: 적재 후 호기별 누적 데이터 기간이 갱신된다."""
    api.force_authenticate(normal_user)
    batch_id = post_validate(api, mapped_unit).data["batch_id"]
    commit(api, batch_id)

    res = api.get(f"/api/units/{mapped_unit.id}/data-summary/")

    assert res.data["row_count"] == 3
    assert res.data["period"]["start"] is not None


def test_overwrite_policy_updates_existing_rows(api, normal_user, mapped_unit):
    api.force_authenticate(normal_user)
    batch_id = post_validate(api, mapped_unit).data["batch_id"]
    commit(api, batch_id)

    # 정격 160MW 설비이므로 범위 안의 값을 써야 한다(999 는 OUT_OF_RANGE 로 제거된다).
    changed = CSV_BODY.replace("150,10,600,400,3.0", "155,10,600,400,3.0")
    second = post_validate(api, mapped_unit, body=changed, confirm_duplicate_file=True).data[
        "batch_id"
    ]
    commit(api, second, duplicate_policy="OVERWRITE")

    rows = list(Measurement.objects.order_by("timestamp"))
    assert rows[0].gt_power_mw == 155
    # 나머지 행은 건드리지 않는다.
    assert [r.gt_power_mw for r in rows[1:]] == [151, 152]


def test_out_of_range_value_is_dropped_with_warning(api, normal_user, mapped_unit):
    """정격을 크게 벗어난 값은 경고를 남기고 해당 셀만 비운다 (specs/03 §4.4)."""
    api.force_authenticate(normal_user)
    body = CSV_BODY.replace("150,10,600,400,3.0", "999,10,600,400,3.0")

    batch_id = post_validate(api, mapped_unit, body=body).data["batch_id"]
    commit(api, batch_id)

    batch = UploadBatch.objects.get(pk=batch_id)
    codes = {w["code"] for w in batch.validation_report["warnings"]}
    assert "OUT_OF_RANGE" in codes
    # 행 전체가 아니라 해당 셀만 비워진다.
    first = Measurement.objects.order_by("timestamp").first()
    assert first.gt_power_mw is None
    assert first.stack_temp_c == 110


def test_skip_policy_keeps_existing_rows(api, normal_user, mapped_unit):
    api.force_authenticate(normal_user)
    batch_id = post_validate(api, mapped_unit).data["batch_id"]
    commit(api, batch_id)

    changed = CSV_BODY.replace("150,10,600,400,3.0", "999,10,600,400,3.0")
    second = post_validate(api, mapped_unit, body=changed, confirm_duplicate_file=True).data[
        "batch_id"
    ]
    commit(api, second, duplicate_policy="SKIP")

    assert Measurement.objects.order_by("timestamp").first().gt_power_mw == 150


# --- 롤백 (specs/03 §6) ---


def test_only_admin_can_rollback(api, normal_user, mapped_unit):
    api.force_authenticate(normal_user)
    batch_id = post_validate(api, mapped_unit).data["batch_id"]
    commit(api, batch_id)

    assert api.delete(f"/api/uploads/{batch_id}/").status_code == 403


def test_admin_rollback_deletes_measurements(api, normal_user, admin_user, mapped_unit):
    api.force_authenticate(normal_user)
    batch_id = post_validate(api, mapped_unit).data["batch_id"]
    commit(api, batch_id)

    api.force_authenticate(admin_user)
    res = api.delete(f"/api/uploads/{batch_id}/")

    assert res.status_code == 200
    assert res.data["deleted_rows"] == 3
    assert Measurement.objects.count() == 0


def test_cancel_marks_batch_canceled(api, normal_user, mapped_unit):
    api.force_authenticate(normal_user)
    batch_id = post_validate(api, mapped_unit).data["batch_id"]

    assert api.post(f"/api/uploads/{batch_id}/cancel/").status_code == 204
    assert UploadBatch.objects.get(pk=batch_id).status == BatchStatus.CANCELED
