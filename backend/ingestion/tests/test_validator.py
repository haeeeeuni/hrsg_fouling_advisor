"""업로드 검증 (specs/03 §4). DB 불필요."""

import pandas as pd
import pytest

from ingestion.services.transform import mapping_specs_from_rows
from ingestion.services.validator import ValueValidator, validate_structure
from units.standard_fields import DEFAULT_PHYSICAL_RANGES, resolve_ranges

NOW = pd.Timestamp("2024-06-01 00:00:00")
RANGES = resolve_ranges(DEFAULT_PHYSICAL_RANGES, rated_power_mw=160.0)

FULL_ROWS = [
    {"standard_field": "timestamp", "source_column": "ts"},
    {"standard_field": "gt_power_mw", "source_column": "pw"},
    {"standard_field": "ambient_temp_c", "source_column": "amb"},
    {"standard_field": "gt_exhaust_temp_c", "source_column": "exh"},
    {"standard_field": "stack_temp_c", "source_column": "stk"},
    {"standard_field": "duct_burner_on", "source_column": "db", "bool_rule": "BOOL"},
    {"standard_field": "exhaust_flow", "source_column": "flw"},
    {"standard_field": "hrsg_gas_dp_kpa", "source_column": "dp"},
]
HEADER = ["ts", "pw", "amb", "exh", "stk", "db", "flw", "dp"]


def specs(rows=None):
    return mapping_specs_from_rows(rows or FULL_ROWS)


def codes(items):
    return {item["code"] for item in items}


# --- 구조 검증 (specs/03 §4.1) ---


def test_valid_structure_has_no_errors():
    assert validate_structure(HEADER, specs(), [], has_rows=True) == []


def test_empty_file_is_an_error():
    errors = validate_structure(HEADER, specs(), [], has_rows=False)

    assert codes(errors) == {"EMPTY_FILE"}


def test_ac_03_1_missing_source_column_names_the_standard_field():
    """AC-03-1: 어떤 표준 항목이 어떤 원본 컬럼을 찾지 못했는지 구체적으로 표시한다."""
    errors = validate_structure([c for c in HEADER if c != "stk"], specs(), [], has_rows=True)

    missing = next(e for e in errors if e["code"] == "MISSING_SOURCE_COLUMN")
    assert {"standard_field": "stack_temp_c", "source_column": "stk"} in missing["missing"]


def test_duplicate_header_is_an_error():
    errors = validate_structure(HEADER, specs(), ["pw"], has_rows=True)

    assert "DUPLICATE_HEADER" in codes(errors)


def test_unmapped_required_field_is_an_error():
    rows = [r for r in FULL_ROWS if r["standard_field"] != "stack_temp_c"]
    errors = validate_structure(HEADER, specs(rows), [], has_rows=True)

    assert "REQUIRED_FIELD_UNMAPPED" in codes(errors)


# --- 값 검증 (specs/03 §4.2) ---


def frame(**overrides):
    base = {
        "ts": ["2024-01-01 00:00:00", "2024-01-01 00:10:00", "2024-01-01 00:20:00"],
        "pw": ["150", "151", "152"],
        "amb": ["10", "10", "10"],
        "exh": ["600", "600", "600"],
        "stk": ["110", "111", "112"],
        "db": ["0", "0", "1"],
        "flw": ["400", "400", "400"],
        "dp": ["3.0", "3.1", "3.2"],
    }
    base.update(overrides)
    return pd.DataFrame(base)


def run(chunk, rows=None):
    validator = ValueValidator(ranges=RANGES, now=NOW)
    validator.process(chunk, specs(rows), row_offset=0)
    return validator


def test_clean_chunk_produces_no_issues():
    validator = run(frame())

    report = validator.build_report([])
    assert report["row_valid"] == 3
    assert report["row_errors"] == []
    assert report["is_loadable"] is True


def test_ac_03_2_unparseable_timestamp_row_is_dropped_and_counted():
    """AC-03-2: 파싱 실패 행이 제외되고 건수가 리포트에 표시된다."""
    validator = run(frame(ts=["2024-01-01 00:00:00", "쓰레기", "2024-01-01 00:20:00"]))

    report = validator.build_report([])
    assert report["row_valid"] == 2
    assert report["row_dropped"] == 1
    issue = next(i for i in report["row_errors"] if i["code"] == "TIMESTAMP_PARSE_ERROR")
    assert issue["count"] == 1
    assert issue["sample_rows"] == [3]  # 헤더 1행 + 2번째 데이터 행
    # 행 단위 오류는 적재를 막지 않는다.
    assert report["is_loadable"] is True


def test_future_timestamp_row_is_dropped():
    validator = run(frame(ts=["2024-01-01 00:00:00", "2030-01-01 00:00:00", "2024-01-01 00:20:00"]))

    report = validator.build_report([])
    assert report["row_valid"] == 2
    assert "FUTURE_TIMESTAMP" in codes(report["row_errors"])


def test_numeric_parse_error_is_a_warning_and_cell_becomes_nan():
    validator = run(frame(pw=["150", "I/O Timeout", "152"]))

    report = validator.build_report([])
    assert report["row_valid"] == 3  # 행은 살아있다
    assert "NUMERIC_PARSE_ERROR" in codes(report["warnings"])


def test_out_of_range_value_is_a_warning():
    validator = run(frame(stk=["110", "9999", "112"]))

    report = validator.build_report([])
    assert report["row_valid"] == 3
    assert "OUT_OF_RANGE" in codes(report["warnings"])


def test_gt_power_range_uses_rated_multiplier():
    # 정격 160MW × 1.2 = 192 초과
    validator = run(frame(pw=["150", "250", "152"]))

    assert "OUT_OF_RANGE" in codes(validator.build_report([])["warnings"])


def test_duplicate_timestamp_is_a_warning():
    validator = run(frame(ts=["2024-01-01 00:00:00", "2024-01-01 00:00:00", "2024-01-01 00:20:00"]))

    report = validator.build_report([])
    assert "TIMESTAMP_DUPLICATE" in codes(report["warnings"])
    assert report["row_duplicated"] == 1


def test_out_of_order_timestamp_is_a_warning():
    validator = run(frame(ts=["2024-01-01 00:20:00", "2024-01-01 00:00:00", "2024-01-01 00:10:00"]))

    assert "TIMESTAMP_OUT_OF_ORDER" in codes(validator.build_report([])["warnings"])


def test_period_and_interval_are_estimated():
    report = run(frame()).build_report([])

    assert report["period"]["start"].startswith("2024-01-01T00:00")
    assert report["period"]["end"].startswith("2024-01-01T00:20")
    assert report["estimated_interval_min"] == pytest.approx(10.0)


def test_missing_rate_is_reported_per_column():
    validator = run(frame(dp=["3.0", "", "3.2"]))

    report = validator.build_report([])
    assert report["missing_rate"]["hrsg_gas_dp_kpa"] == pytest.approx(33.33, abs=0.01)


def test_structure_errors_block_loading():
    report = run(frame()).build_report([{"code": "DUPLICATE_HEADER", "message": "x", "count": 1}])

    assert report["is_loadable"] is False


def test_all_rows_dropped_means_not_loadable():
    validator = run(frame(ts=["쓰레기", "쓰레기", "쓰레기"]))

    assert validator.build_report([])["is_loadable"] is False


def test_row_numbers_account_for_chunk_offset():
    validator = ValueValidator(ranges=RANGES, now=NOW)
    validator.process(
        frame(ts=["2024-01-01 00:00:00", "쓰레기", "2024-01-01 00:20:00"]), specs(), row_offset=100
    )

    issue = next(
        i for i in validator.build_report([])["row_errors"] if i["code"] == "TIMESTAMP_PARSE_ERROR"
    )
    assert issue["sample_rows"] == [103]
