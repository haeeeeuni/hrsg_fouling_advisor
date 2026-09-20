"""샘플 데이터 → 검증 파이프라인 (specs/17 §6 1~3단계). DB 불필요.

전체 통합 테스트(업로드 → 분석 → 리포트)는 Phase 5에서 완성한다.
"""

import subprocess
import sys
from pathlib import Path

import pytest

from ingestion.services import reader
from ingestion.services.transform import mapping_specs_from_rows
from ingestion.services.validator import ValueValidator, validate_structure
from units.standard_fields import DEFAULT_PHYSICAL_RANGES, resolve_ranges

BACKEND = Path(__file__).resolve().parents[2]
SCRIPT = BACKEND / "scripts" / "generate_sample_data.py"

# 한글 헤더 → 표준 항목 (specs/17 §4.2 의 컬럼 매핑 검증 시나리오)
KOREAN_MAPPING = [
    {"standard_field": "timestamp", "source_column": "시각"},
    {"standard_field": "gt_power_mw", "source_column": "GT출력(MW)"},
    {"standard_field": "ambient_temp_c", "source_column": "대기온도(℃)"},
    {"standard_field": "gt_exhaust_temp_c", "source_column": "GT배기온도(℃)"},
    {"standard_field": "exhaust_flow", "source_column": "배기유량(kg/s)"},
    {"standard_field": "hrsg_gas_dp_kpa", "source_column": "HRSG가스차압(kPa)"},
    {"standard_field": "stack_temp_c", "source_column": "스택온도(℃)"},
    {"standard_field": "duct_burner_on", "source_column": "덕트버너상태", "bool_rule": "BOOL"},
]


def generate(tmp_path: Path, *extra: str) -> Path:
    out = tmp_path / "sample.csv"
    subprocess.run(
        [sys.executable, str(SCRIPT), "--months", "2", "--seed", "42", "--out", str(out), *extra],
        check=True,
        capture_output=True,
        cwd=BACKEND,
    )
    return out


def validate(path: Path, rows: list[dict]):
    encoding = reader.detect_encoding(path)
    delimiter = reader.detect_delimiter(path, encoding)
    header = reader.read_header(path, encoding, delimiter)
    specs = mapping_specs_from_rows(rows)

    structure = validate_structure(
        header, specs, reader.find_duplicate_headers(header), has_rows=True
    )
    import pandas as pd

    validator = ValueValidator(
        ranges=resolve_ranges(DEFAULT_PHYSICAL_RANGES, 160.0), now=pd.Timestamp("2030-01-01")
    )
    usecols = [s.source_column for s in specs if s.source_column in header]
    offset = 0
    for chunk in reader.iter_chunks(path, encoding, delimiter, usecols=usecols):
        validator.process(chunk, specs, offset)
        offset += len(chunk)
    return validator.build_report(structure)


def codes(items):
    return {item["code"] for item in items}


@pytest.fixture(scope="module")
def clean_korean(tmp_path_factory):
    return generate(tmp_path_factory.mktemp("clean"), "--korean-headers")


@pytest.fixture(scope="module")
def messy_korean(tmp_path_factory):
    return generate(tmp_path_factory.mktemp("messy"), "--korean-headers", "--messy")


def test_ac_17_5_korean_header_file_passes_validation(clean_korean):
    """AC-17-5: 한글 헤더 파일이 컬럼 매핑을 통해 정상 처리된다."""
    report = validate(clean_korean, KOREAN_MAPPING)

    assert report["errors"] == []
    assert report["is_loadable"] is True
    assert report["row_valid"] == report["row_total"]
    assert report["estimated_interval_min"] == 10.0


def test_clean_file_has_no_row_errors(clean_korean):
    report = validate(clean_korean, KOREAN_MAPPING)

    assert report["row_errors"] == []
    assert report["row_duplicated"] == 0


def test_ac_17_4_messy_file_is_caught_as_errors_and_warnings(messy_korean):
    """AC-17-4: --messy 데이터가 업로드 검증에서 오류·경고로 정확히 잡힌다."""
    report = validate(messy_korean, KOREAN_MAPPING)

    warning_codes = codes(report["warnings"])
    assert "NUMERIC_PARSE_ERROR" in warning_codes
    assert "OUT_OF_RANGE" in warning_codes
    assert "TIMESTAMP_DUPLICATE" in warning_codes
    assert "TIMESTAMP_OUT_OF_ORDER" in warning_codes
    assert report["row_duplicated"] > 0
    # 구조는 멀쩡하므로 적재 자체는 가능해야 한다.
    assert report["errors"] == []
    assert report["is_loadable"] is True


def test_messy_file_reports_missing_rate(messy_korean):
    report = validate(messy_korean, KOREAN_MAPPING)

    assert any(rate > 0 for rate in report["missing_rate"].values())


def test_ac_02_1_unmapped_unit_is_blocked_at_structure_level(clean_korean):
    """필수 항목이 빠진 매핑이면 구조 검증에서 막힌다."""
    partial = [r for r in KOREAN_MAPPING if r["standard_field"] != "stack_temp_c"]

    report = validate(clean_korean, partial)

    assert "REQUIRED_FIELD_UNMAPPED" in codes(report["errors"])
    assert report["is_loadable"] is False
