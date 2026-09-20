"""표준 항목 필수 충족 규칙 (specs/02 §3.4). DB 불필요."""

import pytest

from units.standard_fields import (
    ALWAYS_REQUIRED,
    DEFAULT_PHYSICAL_RANGES,
    check_required,
    resolve_ranges,
)

FULL = set(ALWAYS_REQUIRED) | {"exhaust_flow", "hrsg_gas_dp_kpa"}


def codes(problems):
    return {p["code"] for p in problems}


def test_complete_mapping_has_no_problems():
    assert check_required(FULL) == []


def test_missing_required_field_is_reported_with_field_names():
    problems = check_required(FULL - {"stack_temp_c"})

    assert "REQUIRED_FIELD_UNMAPPED" in codes(problems)
    assert "stack_temp_c" in problems[0]["fields"]


def test_ac_02_2_backpressure_alone_satisfies_dp_rule():
    """AC-02-2: 차압 컬럼이 없고 GT 배압만 매핑된 호기도 필수 규칙을 통과한다."""
    mapped = (FULL - {"hrsg_gas_dp_kpa"}) | {"gt_backpressure_kpa"}

    assert check_required(mapped) == []


@pytest.mark.parametrize("flow_field", ["exhaust_flow", "fuel_flow", "igv_position_pct"])
def test_any_flow_alternative_satisfies_flow_rule(flow_field):
    mapped = (FULL - {"exhaust_flow"}) | {flow_field}

    assert check_required(mapped) == []


def test_missing_all_flow_alternatives_is_reported():
    problems = check_required(FULL - {"exhaust_flow"})

    assert "FLOW_FIELD_UNMAPPED" in codes(problems)


def test_missing_all_dp_alternatives_is_reported():
    problems = check_required(FULL - {"hrsg_gas_dp_kpa"})

    assert "DP_FIELD_UNMAPPED" in codes(problems)


def test_empty_mapping_reports_all_three_rules():
    assert codes(check_required(set())) == {
        "REQUIRED_FIELD_UNMAPPED",
        "FLOW_FIELD_UNMAPPED",
        "DP_FIELD_UNMAPPED",
    }


# --- 물리 범위 (specs/03 §4.3) ---


def test_gt_power_upper_bound_scales_with_rated_power():
    resolved = resolve_ranges(DEFAULT_PHYSICAL_RANGES, rated_power_mw=160.0)

    assert resolved["gt_power_mw"] == (-5, 160.0 * 1.2)


def test_fixed_ranges_are_passed_through():
    resolved = resolve_ranges(DEFAULT_PHYSICAL_RANGES, rated_power_mw=160.0)

    assert resolved["ambient_temp_c"] == (-40, 60)
    assert resolved["hrsg_gas_dp_kpa"] == (0, 20)


def test_missing_rated_power_leaves_upper_bound_open():
    resolved = resolve_ranges(DEFAULT_PHYSICAL_RANGES, rated_power_mw=None)

    assert resolved["gt_power_mw"] == (-5, None)
