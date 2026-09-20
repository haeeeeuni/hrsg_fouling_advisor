"""원본 → 표준 항목 변환 (specs/02 §4). DB 불필요."""

import pandas as pd
import pytest

from ingestion.services.transform import (
    MappingSpec,
    apply_mapping,
    mapping_specs_from_rows,
    parse_bool,
    parse_numeric,
    parse_timestamps,
)


def test_ac_02_3_scale_factor_and_offset_are_applied():
    """AC-02-3: 변환식 표준값 = 원본값 × scale_factor + offset"""
    series = pd.Series(["100", "200"])

    # mmH2O → kPa
    result = parse_numeric(series, scale_factor=0.00980665, offset=0.0)

    assert result.iloc[0] == pytest.approx(0.980665)
    assert result.iloc[1] == pytest.approx(1.96133)


def test_fahrenheit_conversion_uses_offset():
    result = parse_numeric(pd.Series(["212"]), scale_factor=5 / 9, offset=-32 * 5 / 9)

    assert result.iloc[0] == pytest.approx(100.0)


@pytest.mark.parametrize("token", ["Bad", "I/O Timeout", "N/A", "", "  "])
def test_non_numeric_tokens_become_nan(token):
    result = parse_numeric(pd.Series([token]), 1.0, 0.0)

    assert pd.isna(result.iloc[0])


def test_thousand_separators_are_handled():
    result = parse_numeric(pd.Series(["1,234.5"]), 1.0, 0.0)

    assert result.iloc[0] == pytest.approx(1234.5)


# --- 타임스탬프 ---


def test_mixed_timestamp_formats_are_parsed():
    series = pd.Series(["2024-01-01 00:10:00", "2024/01/01 00:20"])

    result = parse_timestamps(series)

    assert result.notna().all()
    assert result.iloc[1].minute == 20


def test_unparseable_timestamp_becomes_nat():
    result = parse_timestamps(pd.Series(["2024-01-01 00:10:00", "쓰레기"]))

    assert pd.isna(result.iloc[1])


# --- duct_burner_on (specs/02 §4) ---


@pytest.mark.parametrize("raw", ["1", "True", "ON", "Y", "yes"])
def test_bool_rule_recognizes_true_tokens(raw):
    spec = MappingSpec("duct_burner_on", "db", bool_rule="BOOL")

    assert parse_bool(pd.Series([raw]), spec).iloc[0] is True


@pytest.mark.parametrize("raw", ["0", "False", "OFF", "N", "no"])
def test_bool_rule_recognizes_false_tokens(raw):
    spec = MappingSpec("duct_burner_on", "db", bool_rule="BOOL")

    assert parse_bool(pd.Series([raw]), spec).iloc[0] is False


def test_bool_rule_unknown_token_is_none():
    spec = MappingSpec("duct_burner_on", "db", bool_rule="BOOL")

    assert parse_bool(pd.Series(["알수없음"]), spec).iloc[0] is None


def test_threshold_rule_compares_against_threshold():
    spec = MappingSpec("duct_burner_on", "db", bool_rule="THRESHOLD", bool_threshold=100.0)

    result = parse_bool(pd.Series(["150", "50"]), spec)

    assert bool(result.iloc[0]) is True
    assert bool(result.iloc[1]) is False


# --- apply_mapping ---


def build_chunk():
    return pd.DataFrame(
        {
            "시각": ["2024-01-01 00:00:00", "2024-01-01 00:10:00"],
            "GT출력(MW)": ["150.5", "148.0"],
            "HRSG가스차압(mmH2O)": ["300", "310"],
            "덕트버너상태": ["1", "0"],
            "쓰이지않는컬럼": ["a", "b"],
        }
    )


def specs():
    return mapping_specs_from_rows(
        [
            {"standard_field": "timestamp", "source_column": "시각"},
            {"standard_field": "gt_power_mw", "source_column": "GT출력(MW)"},
            {
                "standard_field": "hrsg_gas_dp_kpa",
                "source_column": "HRSG가스차압(mmH2O)",
                "scale_factor": 0.00980665,
            },
            {
                "standard_field": "duct_burner_on",
                "source_column": "덕트버너상태",
                "bool_rule": "BOOL",
            },
        ]
    )


def test_apply_mapping_outputs_only_standard_field_names():
    """분석 코드는 원본 컬럼명을 절대 알지 못한다 (AGENTS.md §5.1)."""
    result = apply_mapping(build_chunk(), specs())

    assert set(result.columns) == {
        "timestamp",
        "gt_power_mw",
        "hrsg_gas_dp_kpa",
        "duct_burner_on",
    }
    assert "쓰이지않는컬럼" not in result.columns


def test_apply_mapping_converts_units():
    result = apply_mapping(build_chunk(), specs())

    assert result["hrsg_gas_dp_kpa"].iloc[0] == pytest.approx(2.941995)
    assert result["gt_power_mw"].iloc[0] == pytest.approx(150.5)
    assert result["duct_burner_on"].iloc[0] is True


def test_apply_mapping_skips_absent_source_columns():
    chunk = build_chunk().drop(columns=["HRSG가스차압(mmH2O)"])

    result = apply_mapping(chunk, specs())

    assert "hrsg_gas_dp_kpa" not in result.columns
