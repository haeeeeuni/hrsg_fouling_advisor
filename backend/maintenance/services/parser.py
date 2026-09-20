"""정비 이력 파일 파싱 (specs/10 §2).

CSV / 엑셀(.xlsx, .xls)을 읽고, 헤더명을 정규화해 표준 항목으로 유연 매핑한다.
순수 함수 모듈 — Django 모델을 import 하지 않는다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

# 표준 항목 → 예상 원본 컬럼명 (specs/10 §2.2)
HEADER_ALIASES: dict[str, tuple[str, ...]] = {
    "work_date": ("작업일", "정비일자", "일자", "작업일자", "date", "workdate"),
    "unit_name": ("호기", "설비", "설비명", "unit", "호기명"),
    "work_type": ("작업구분", "정비유형", "구분", "유형", "worktype"),
    "title": ("제목", "작업명", "title", "subject", "작업내용요약"),
    "description": ("내용", "작업내역", "비고", "description", "note", "상세"),
    "cost": ("비용", "금액", "cost", "amount"),
    "duration_days": ("소요일수", "정지일수", "일수", "duration"),
    "worker": ("작업자", "담당", "담당자", "worker", "팀"),
}

REQUIRED_FIELDS = ("work_date", "title")

_NON_WORD = re.compile(r"[\s()\[\]{}·/\\_\-.]+")


@dataclass
class ParseResult:
    rows: list[dict[str, Any]] = field(default_factory=list)
    mapping: dict[str, str] = field(default_factory=dict)
    header: list[str] = field(default_factory=list)
    sheets: list[str] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[dict[str, Any]] = field(default_factory=list)

    @property
    def is_ok(self) -> bool:
        return not self.errors


def normalize_header(name: str) -> str:
    """공백·괄호·구분자를 제거하고 소문자화한다 (specs/10 §2.2)."""
    return _NON_WORD.sub("", str(name)).lower()


def auto_map(header: list[str]) -> dict[str, str]:
    """헤더명을 정규화한 뒤 사전 매칭한다. 실패한 항목은 결과에 없다."""
    normalized = {normalize_header(name): name for name in header}
    mapping: dict[str, str] = {}
    for field_name, aliases in HEADER_ALIASES.items():
        for alias in aliases:
            source = normalized.get(normalize_header(alias))
            if source is not None:
                mapping[field_name] = source
                break
    return mapping


def list_sheets(path: str | Path) -> list[str]:
    try:
        return pd.ExcelFile(path).sheet_names
    except Exception:  # noqa: BLE001 - CSV 등 엑셀이 아닌 경우
        return []


def read_table(
    path: str | Path, encoding: str | None = None, sheet: str | int | None = None
) -> pd.DataFrame:
    """CSV 또는 엑셀을 DataFrame 으로 읽는다. 엑셀은 첫 시트가 기본이다."""
    suffix = Path(path).suffix.lower()
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(path, sheet_name=sheet if sheet is not None else 0, dtype=object)

    from ingestion.services import reader

    detected = encoding or reader.detect_encoding(path)
    delimiter = reader.detect_delimiter(path, detected)
    return pd.read_csv(path, encoding=detected, sep=delimiter, dtype=object)


def parse(
    path: str | Path,
    sheet: str | int | None = None,
    mapping: dict[str, str] | None = None,
) -> ParseResult:
    """정비 이력 파일을 표준 항목 dict 목록으로 바꾼다."""
    result = ParseResult(sheets=list_sheets(path))

    try:
        frame = read_table(path, sheet=sheet)
    except Exception as exc:  # noqa: BLE001
        result.errors.append(
            {
                "code": "EXCEL_PARSE_ERROR",
                "message": "파일을 읽을 수 없습니다.",
                "details": {"reason": str(exc)[:300], "sheet": sheet},
            }
        )
        return result

    frame.columns = [str(c).strip() for c in frame.columns]
    result.header = list(frame.columns)
    result.mapping = mapping or auto_map(result.header)

    missing = [f for f in REQUIRED_FIELDS if f not in result.mapping]
    if missing:
        result.errors.append(
            {
                "code": "REQUIRED_FIELD_UNMAPPED",
                "message": "필수 항목을 찾을 수 없습니다. 컬럼 매핑을 확인하세요.",
                "fields": missing,
                "header": result.header,
            }
        )
        return result

    if frame.empty:
        result.errors.append({"code": "EMPTY_FILE", "message": "데이터 행이 없습니다."})
        return result

    invalid_dates = 0
    for index, row in frame.iterrows():
        work_date = pd.to_datetime(row.get(result.mapping["work_date"]), errors="coerce")
        if pd.isna(work_date):
            invalid_dates += 1
            continue

        record = {
            "work_date": work_date.date(),
            "title": _text(row.get(result.mapping["title"]))[:300],
            "work_type": _text(_lookup(row, result.mapping, "work_type"))[:50],
            "description": _text(_lookup(row, result.mapping, "description")),
            "worker": _text(_lookup(row, result.mapping, "worker"))[:100],
            "unit_name": _text(_lookup(row, result.mapping, "unit_name")),
            "cost": _number(_lookup(row, result.mapping, "cost"), integer=True),
            "duration_days": _number(_lookup(row, result.mapping, "duration_days")),
            "row_number": int(index) + 2,
        }
        if not record["title"]:
            invalid_dates += 0  # 제목 없는 행은 그대로 두고 경고만
        result.rows.append(record)

    if invalid_dates:
        result.warnings.append(
            {
                "code": "DATE_PARSE_ERROR",
                "message": "작업일을 해석할 수 없는 행을 건너뛰었습니다.",
                "count": invalid_dates,
            }
        )
    if not result.rows:
        result.errors.append({"code": "EMPTY_FILE", "message": "해석 가능한 행이 없습니다."})

    return result


def _lookup(row: pd.Series, mapping: dict[str, str], field_name: str):
    column = mapping.get(field_name)
    return row.get(column) if column else None


def _text(value: Any) -> str:
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return ""
    return str(value).strip()


def _number(value: Any, integer: bool = False) -> float | int | None:
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return None
    cleaned = str(value).replace(",", "").strip()
    if not cleaned:
        return None
    try:
        number = float(cleaned)
    except ValueError:
        return None
    return int(number) if integer else number
