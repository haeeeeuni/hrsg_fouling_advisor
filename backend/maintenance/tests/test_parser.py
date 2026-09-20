"""정비 이력 파일 파싱 (specs/10 §2). DB 불필요."""

import pandas as pd
import pytest

from maintenance.services import parser

ROWS = [
    [
        "2023-06-14",
        "U1",
        "계획정비",
        "HRSG 전열면 화학세정 시행",
        "차압 상승",
        28000000,
        2,
        "정비2팀",
    ],
    ["2023-03-02", "U1", "점검", "GT 연소기 육안 점검", "이상 없음", 0, 1, "정비1팀"],
]
HEADER = ["작업일", "호기", "작업구분", "제목", "내용", "비용", "소요일수", "작업자"]


@pytest.fixture
def csv_path(tmp_path):
    path = tmp_path / "maint.csv"
    pd.DataFrame(ROWS, columns=HEADER).to_csv(path, index=False, encoding="utf-8-sig")
    return path


@pytest.fixture
def xlsx_path(tmp_path):
    path = tmp_path / "maint.xlsx"
    pd.DataFrame(ROWS, columns=HEADER).to_excel(path, index=False)
    return path


def test_normalize_header():
    assert parser.normalize_header("작업 일") == "작업일"
    assert parser.normalize_header("Work_Date") == "workdate"
    assert parser.normalize_header("비용(원)") == "비용원"


def test_auto_map_matches_korean_aliases():
    mapping = parser.auto_map(HEADER)

    assert mapping["work_date"] == "작업일"
    assert mapping["title"] == "제목"
    assert mapping["cost"] == "비용"


def test_auto_map_matches_english_aliases():
    mapping = parser.auto_map(["Date", "Title", "Description", "Worker"])

    assert mapping["work_date"] == "Date"
    assert mapping["title"] == "Title"


def test_csv_is_parsed(csv_path):
    result = parser.parse(csv_path)

    assert result.is_ok
    assert len(result.rows) == 2
    assert result.rows[0]["title"] == "HRSG 전열면 화학세정 시행"
    assert result.rows[0]["cost"] == 28000000
    assert str(result.rows[0]["work_date"]) == "2023-06-14"


def test_xlsx_is_parsed(xlsx_path):
    result = parser.parse(xlsx_path)

    assert result.is_ok
    assert len(result.rows) == 2
    assert result.sheets  # 시트 목록을 돌려준다


def test_missing_required_field_is_an_error(tmp_path):
    path = tmp_path / "bad.csv"
    pd.DataFrame([["a", "b"]], columns=["알수없음", "기타"]).to_csv(path, index=False)

    result = parser.parse(path)

    assert not result.is_ok
    assert result.errors[0]["code"] == "REQUIRED_FIELD_UNMAPPED"
    assert "work_date" in result.errors[0]["fields"]


def test_unparseable_dates_are_skipped_with_warning(tmp_path):
    path = tmp_path / "mixed.csv"
    rows = [*ROWS, ["쓰레기", "U1", "", "제목", "", 0, 0, ""]]
    pd.DataFrame(rows, columns=HEADER).to_csv(path, index=False)

    result = parser.parse(path)

    assert len(result.rows) == 2
    assert result.warnings[0]["code"] == "DATE_PARSE_ERROR"
    assert result.warnings[0]["count"] == 1


def test_empty_file_is_an_error(tmp_path):
    path = tmp_path / "empty.csv"
    pd.DataFrame(columns=HEADER).to_csv(path, index=False)

    assert not parser.parse(path).is_ok


def test_explicit_mapping_overrides_auto(tmp_path):
    path = tmp_path / "custom.csv"
    pd.DataFrame([["2024-01-01", "직접 지정 제목"]], columns=["ColA", "ColB"]).to_csv(
        path, index=False
    )

    result = parser.parse(path, mapping={"work_date": "ColA", "title": "ColB"})

    assert result.is_ok
    assert result.rows[0]["title"] == "직접 지정 제목"


def test_broken_file_reports_parse_error(tmp_path):
    path = tmp_path / "broken.xlsx"
    path.write_bytes(b"not an excel file")

    result = parser.parse(path)

    assert not result.is_ok
    assert result.errors[0]["code"] == "EXCEL_PARSE_ERROR"
