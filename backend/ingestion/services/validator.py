"""업로드 검증 (specs/03 §4).

구조 검증(§4.1)과 값 검증(§4.2)을 분리한다.

TODO(질문): specs/03 §4.4 는 "오류가 1건이라도 있으면 적재 버튼 비활성화"라고 하지만,
§4.2 의 행 단위 '오류'(TIMESTAMP_PARSE_ERROR / FUTURE_TIMESTAMP)는 처리가 "해당 행 제외"이고
AC-03-2 도 "파싱 실패 행이 제외되고 건수가 리포트에 표시된다"를 요구한다. 두 서술이 충돌한다.
가장 단순한 해석으로 **구조 검증 오류만 적재를 차단**하고, 행 단위 오류는 해당 행만 제외한 뒤
적재를 진행하도록 구현했다. 명세 확정 시 이 주석과 `is_loadable` 판정을 함께 고친다.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

import pandas as pd

from ingestion.services.transform import MappingSpec, apply_mapping
from units.standard_fields import NUMERIC_FIELDS, TIMESTAMP, check_required

MAX_SAMPLE_ROWS = 10


@dataclass
class Issue:
    code: str
    message: str
    count: int = 0
    sample_rows: list[int] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)

    def add(self, row_number: int) -> None:
        self.count += 1
        if len(self.sample_rows) < MAX_SAMPLE_ROWS:
            self.sample_rows.append(row_number)

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "code": self.code,
            "message": self.message,
            "count": self.count,
            "sample_rows": self.sample_rows,
        }
        payload.update(self.extra)
        return payload


class IssueBag:
    def __init__(self) -> None:
        self._issues: dict[str, Issue] = {}

    def get(self, code: str, message: str) -> Issue:
        if code not in self._issues:
            self._issues[code] = Issue(code=code, message=message)
        return self._issues[code]

    def add(self, code: str, message: str, row_number: int) -> None:
        self.get(code, message).add(row_number)

    def as_list(self) -> list[dict[str, Any]]:
        return [issue.to_dict() for issue in self._issues.values() if issue.count]

    def total(self) -> int:
        return sum(issue.count for issue in self._issues.values())


# --- 구조 검증 (specs/03 §4.1) ---


def validate_structure(
    header: list[str],
    specs: list[MappingSpec],
    duplicate_headers: list[str],
    has_rows: bool,
) -> list[dict[str, Any]]:
    """적재를 차단하는 구조 오류 목록."""
    errors: list[dict[str, Any]] = []

    if not has_rows:
        errors.append({"code": "EMPTY_FILE", "message": "데이터 행이 없습니다.", "count": 1})
        return errors

    if duplicate_headers:
        errors.append(
            {
                "code": "DUPLICATE_HEADER",
                "message": "동일한 컬럼명이 중복되어 있습니다.",
                "count": len(duplicate_headers),
                "columns": duplicate_headers,
            }
        )

    mapped_fields = {spec.standard_field for spec in specs}
    for problem in check_required(mapped_fields):
        errors.append({**problem, "count": len(problem.get("fields", []))})

    header_set = set(header)
    missing = [
        {"standard_field": spec.standard_field, "source_column": spec.source_column}
        for spec in specs
        if spec.source_column not in header_set
    ]
    if missing:
        errors.append(
            {
                "code": "MISSING_SOURCE_COLUMN",
                "message": "매핑된 원본 컬럼이 파일 헤더에 없습니다.",
                "count": len(missing),
                # 어떤 표준 항목이 어떤 컬럼을 기대했는지 구체적으로 알린다(AC-03-1).
                "missing": missing,
            }
        )

    return errors


# --- 값 검증 (specs/03 §4.2) ---


@dataclass
class ChunkResult:
    frame: pd.DataFrame  # 유효 행만 남은 표준 항목 DataFrame
    row_total: int
    row_dropped: int


class ValueValidator:
    """청크를 순회하며 값 검증 결과를 누적한다."""

    def __init__(self, ranges: dict[str, tuple], now: pd.Timestamp) -> None:
        self.ranges = ranges
        self.future_limit = now + timedelta(days=1)  # specs/03 §4.2
        self.errors = IssueBag()
        self.warnings = IssueBag()

        self.row_total = 0
        self.row_valid = 0
        self.row_dropped = 0
        self.duplicate_count = 0
        self.out_of_order_count = 0

        self._seen_timestamps: set[pd.Timestamp] = set()
        self._last_timestamp: pd.Timestamp | None = None
        self._null_counts: dict[str, int] = defaultdict(int)
        self._period_start: pd.Timestamp | None = None
        self._period_end: pd.Timestamp | None = None
        self._interval_samples: list[float] = []

    def process(
        self, chunk: pd.DataFrame, specs: list[MappingSpec], row_offset: int
    ) -> ChunkResult:
        frame = apply_mapping(chunk, specs)
        n = len(frame)
        self.row_total += n

        # 파일 기준 행 번호(헤더가 1행이므로 +2)
        row_numbers = pd.Series(range(row_offset + 2, row_offset + 2 + n), index=frame.index)

        # 1) 타임스탬프 — 해석 실패/미래 시각은 행 제외
        ts = (
            frame[TIMESTAMP] if TIMESTAMP in frame.columns else pd.Series(pd.NaT, index=frame.index)
        )
        bad_ts = ts.isna()
        for row_number in row_numbers[bad_ts]:
            self.errors.add(
                "TIMESTAMP_PARSE_ERROR", "타임스탬프 해석에 실패했습니다.", int(row_number)
            )

        future = ts.notna() & (ts > self.future_limit)
        for row_number in row_numbers[future]:
            self.errors.add("FUTURE_TIMESTAMP", "미래 시각이 포함되어 있습니다.", int(row_number))

        drop = bad_ts | future
        self.row_dropped += int(drop.sum())
        frame = frame[~drop].copy()
        row_numbers = row_numbers[~drop]

        if frame.empty:
            return ChunkResult(frame=frame, row_total=n, row_dropped=int(drop.sum()))

        # 2) 숫자 변환 실패 — 경고, 해당 셀 NaN
        for column in frame.columns:
            if column not in NUMERIC_FIELDS:
                continue
            source = self._source_column(specs, column)
            raw_present = (
                chunk.loc[frame.index, source].notna() if source in chunk.columns else False
            )
            failed = frame[column].isna() & raw_present
            for row_number in row_numbers[failed]:
                self.warnings.add(
                    "NUMERIC_PARSE_ERROR", "숫자로 변환할 수 없는 값이 있습니다.", int(row_number)
                )

        # 3) 물리 범위 초과 — 경고, 해당 셀 NaN
        for column, (low, high) in self.ranges.items():
            if column not in frame.columns:
                continue
            values = frame[column]
            outside = pd.Series(False, index=frame.index)
            if low is not None:
                outside |= values < low
            if high is not None:
                outside |= values > high
            outside &= values.notna()
            if outside.any():
                for row_number in row_numbers[outside]:
                    self.warnings.add(
                        "OUT_OF_RANGE", "물리적 허용 범위를 벗어난 값이 있습니다.", int(row_number)
                    )
                frame.loc[outside, column] = pd.NA

        # 4) 중복 / 역순 — 경고
        ts = frame[TIMESTAMP]
        duplicated = ts.isin(self._seen_timestamps) | ts.duplicated(keep="last")
        self.duplicate_count += int(duplicated.sum())
        for row_number in row_numbers[duplicated]:
            self.warnings.add(
                "TIMESTAMP_DUPLICATE", "동일 시각이 중복되어 있습니다.", int(row_number)
            )
        self._seen_timestamps.update(ts.tolist())

        if self._last_timestamp is not None and not ts.empty and ts.iloc[0] < self._last_timestamp:
            self.out_of_order_count += 1
        decreasing = ts.diff() < pd.Timedelta(0)
        self.out_of_order_count += int(decreasing.sum())
        if self.out_of_order_count:
            self.warnings.get(
                "TIMESTAMP_OUT_OF_ORDER", "시간 역순 행이 있습니다. 정렬 후 적재합니다."
            ).count = self.out_of_order_count
        if not ts.empty:
            self._last_timestamp = ts.iloc[-1]

        # 5) 결측률 / 기간 / 주기 추정
        for column in frame.columns:
            self._null_counts[column] += int(frame[column].isna().sum())

        chunk_min, chunk_max = ts.min(), ts.max()
        self._period_start = min(filter(None, [self._period_start, chunk_min]), default=chunk_min)
        self._period_end = max(filter(None, [self._period_end, chunk_max]), default=chunk_max)

        if len(self._interval_samples) < 2000:
            deltas = ts.sort_values().diff().dt.total_seconds().dropna()
            self._interval_samples.extend(deltas[deltas > 0].head(2000).tolist())

        self.row_valid += len(frame)
        return ChunkResult(frame=frame, row_total=n, row_dropped=int(drop.sum()))

    @staticmethod
    def _source_column(specs: list[MappingSpec], standard_field: str) -> str:
        for spec in specs:
            if spec.standard_field == standard_field:
                return spec.source_column
        return ""

    def estimated_interval_min(self) -> float | None:
        if not self._interval_samples:
            return None
        median = pd.Series(self._interval_samples).median()
        return round(median / 60, 2)

    def missing_rate(self) -> dict[str, float]:
        if not self.row_valid:
            return {}
        return {
            column: round(count / self.row_valid * 100, 2)
            for column, count in sorted(self._null_counts.items())
        }

    def build_report(self, structure_errors: list[dict[str, Any]]) -> dict[str, Any]:
        """검증 리포트 (specs/03 §4.4, specs/15 §5)."""
        return {
            "row_total": self.row_total,
            "row_valid": self.row_valid,
            "row_dropped": self.row_dropped,
            "row_duplicated": self.duplicate_count,
            "period": {
                "start": self._period_start.isoformat() if self._period_start is not None else None,
                "end": self._period_end.isoformat() if self._period_end is not None else None,
            },
            "estimated_interval_min": self.estimated_interval_min(),
            # 구조 오류만 적재를 차단한다(모듈 docstring 의 TODO(질문) 참조).
            "errors": structure_errors,
            "row_errors": self.errors.as_list(),
            "warnings": self.warnings.as_list(),
            "missing_rate": self.missing_rate(),
            "is_loadable": not structure_errors and self.row_valid > 0,
        }
