"""원본 컬럼 → 표준 항목 변환 (specs/02 §4).

변환식: 표준값 = 원본값 × scale_factor + offset
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from units.standard_fields import TIMESTAMP

# duct_burner_on 의 BOOL 규칙에서 참으로 보는 문자열
TRUE_TOKENS = {"1", "1.0", "true", "t", "y", "yes", "on", "run", "running"}
FALSE_TOKENS = {"0", "0.0", "false", "f", "n", "no", "off", "stop", "stopped"}


@dataclass(frozen=True)
class MappingSpec:
    """ColumnMapping 의 순수 데이터 표현. 서비스는 Django 모델을 모른다."""

    standard_field: str
    source_column: str
    scale_factor: float = 1.0
    offset: float = 0.0
    bool_rule: str = ""
    bool_threshold: float | None = None


def mapping_specs_from_rows(rows: list[dict]) -> list[MappingSpec]:
    return [
        MappingSpec(
            standard_field=row["standard_field"],
            source_column=row["source_column"],
            scale_factor=row.get("scale_factor", 1.0) or 1.0,
            offset=row.get("offset", 0.0) or 0.0,
            bool_rule=row.get("bool_rule") or "",
            bool_threshold=row.get("bool_threshold"),
        )
        for row in rows
    ]


def parse_timestamps(series: pd.Series) -> pd.Series:
    """여러 형식이 섞여 있어도 최대한 해석한다 (AC-03-2).

    해석 실패는 NaT 로 남고 validator 가 TIMESTAMP_PARSE_ERROR 로 집계한다.
    """
    return pd.to_datetime(series, errors="coerce", format="mixed")


def parse_numeric(series: pd.Series, scale_factor: float, offset: float) -> pd.Series:
    """숫자로 변환하고 단위를 환산한다.

    'Bad', 'I/O Timeout', 'N/A' 같은 문자열은 NaN 이 된다(specs/03 §4.2).
    """
    # 천단위 구분 쉼표를 제거한다(예: "1,234.5").
    cleaned = series.astype(str).str.replace(",", "", regex=False).str.strip()
    numeric = pd.to_numeric(cleaned, errors="coerce")
    return numeric * scale_factor + offset


def parse_bool(series: pd.Series, spec: MappingSpec) -> pd.Series:
    """덕트버너 상태 해석 (specs/02 §4).

    - BOOL      : 1/0, True/False, ON/OFF, Y/N 문자열
    - THRESHOLD : 값이 임계값을 초과하면 ON
    """
    # 결과는 항상 object dtype 의 True / False / None 이어야 한다.
    # (np.where 를 쓰면 float 로 떨어져 True 대신 1.0 이 나온다.)
    result = pd.Series([None] * len(series), index=series.index, dtype="object")

    if spec.bool_rule == "THRESHOLD":
        threshold = spec.bool_threshold if spec.bool_threshold is not None else 0.0
        numeric = pd.to_numeric(series.astype(str).str.strip(), errors="coerce")
        known = numeric.notna()
        result[known] = (numeric[known] > threshold).map(bool)
        return result

    tokens = series.astype(str).str.strip().str.lower()
    result[tokens.isin(TRUE_TOKENS)] = True
    result[tokens.isin(FALSE_TOKENS)] = False
    return result


def apply_mapping(chunk: pd.DataFrame, specs: list[MappingSpec]) -> pd.DataFrame:
    """원본 청크를 표준 항목 DataFrame 으로 바꾼다.

    반환 컬럼은 표준 항목명뿐이며, 원본 컬럼명은 이후 어디에도 노출되지 않는다.
    """
    out = pd.DataFrame(index=chunk.index)

    for spec in specs:
        if spec.source_column not in chunk.columns:
            continue
        raw = chunk[spec.source_column]

        if spec.standard_field == TIMESTAMP:
            out[TIMESTAMP] = parse_timestamps(raw)
        elif spec.standard_field == "duct_burner_on":
            out["duct_burner_on"] = parse_bool(raw, spec)
        else:
            out[spec.standard_field] = parse_numeric(raw, spec.scale_factor, spec.offset)

    return out
