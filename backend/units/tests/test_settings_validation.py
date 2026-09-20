"""설정값 검증 (specs/13 §4.3, §8). DB 불필요."""

import pytest

from units.settings_validation import SettingValidationError, coerce, validate

BASE = {
    "fouling_threshold": 60,
    "grade_caution_min": 30,
    "grade_warning_min": 60,
    "weight_dp": 0.6,
    "weight_stack_temp": 0.4,
    "max_upload_mb": 200,
}


def test_valid_change_passes():
    result = validate({"fouling_threshold": 55}, BASE)

    assert result == {"fouling_threshold": 55}


def test_string_input_is_coerced_to_declared_type():
    assert coerce("fouling_threshold", "55") == 55.0
    assert coerce("max_upload_mb", "300") == 300
    assert coerce("cluster_method", "KMEANS") == "KMEANS"


def test_unknown_key_is_rejected():
    with pytest.raises(SettingValidationError) as exc:
        validate({"no_such_key": 1}, BASE)

    assert exc.value.code == "UNKNOWN_SETTING"


# --- 범위 (specs/13 §8) ---


def test_value_below_minimum_is_rejected():
    with pytest.raises(SettingValidationError) as exc:
        validate({"max_upload_mb": 0}, BASE)

    assert exc.value.code == "SETTING_OUT_OF_RANGE"
    assert exc.value.details["min"] == 1


def test_value_above_maximum_is_rejected():
    with pytest.raises(SettingValidationError) as exc:
        validate({"fouling_threshold": 150}, BASE)

    assert exc.value.code == "SETTING_OUT_OF_RANGE"


def test_boundary_values_are_allowed():
    assert validate({"fouling_threshold": 0}, BASE)["fouling_threshold"] == 0
    assert validate({"fouling_threshold": 100}, BASE)["fouling_threshold"] == 100


# --- 가중치 합 = 1 (specs/13 §8) ---


def test_weights_summing_to_one_pass():
    result = validate({"weight_dp": 0.8, "weight_stack_temp": 0.2}, BASE)

    assert result["weight_dp"] == 0.8


def test_weights_not_summing_to_one_are_rejected_with_suggestion():
    with pytest.raises(SettingValidationError) as exc:
        validate({"weight_dp": 0.8, "weight_stack_temp": 0.4}, BASE)

    assert exc.value.code == "INVALID_WEIGHTS"
    suggestion = exc.value.details["suggestion"]
    assert suggestion["weight_dp"] == pytest.approx(2 / 3, abs=1e-5)
    assert sum(suggestion.values()) == pytest.approx(1.0)


def test_partial_weight_change_is_checked_against_current_value():
    """한쪽만 바꿔도 현재 적용값과 합쳐 검사한다."""
    with pytest.raises(SettingValidationError) as exc:
        validate({"weight_dp": 0.9}, BASE)  # 0.9 + 기존 0.4 = 1.3

    assert exc.value.code == "INVALID_WEIGHTS"


def test_zero_total_weight_is_rejected():
    with pytest.raises(SettingValidationError) as exc:
        validate({"weight_dp": 0, "weight_stack_temp": 0}, BASE)

    assert exc.value.code == "INVALID_WEIGHTS"


# --- 등급 경계 (specs/07 §4) ---


def test_grade_boundaries_in_order_pass():
    result = validate({"grade_caution_min": 25, "grade_warning_min": 55}, BASE)

    assert result["grade_caution_min"] == 25


def test_caution_must_be_below_warning():
    with pytest.raises(SettingValidationError) as exc:
        validate({"grade_caution_min": 70}, BASE)  # 70 >= 경고 60

    assert exc.value.code == "INVALID_GRADE_BOUNDARY"


def test_equal_boundaries_are_rejected():
    with pytest.raises(SettingValidationError) as exc:
        validate({"grade_caution_min": 60, "grade_warning_min": 60}, BASE)

    assert exc.value.code == "INVALID_GRADE_BOUNDARY"


def test_warning_above_hundred_is_rejected():
    with pytest.raises(SettingValidationError) as exc:
        validate({"grade_warning_min": 101}, BASE)

    # 범위 검사가 먼저 걸린다
    assert exc.value.code in {"SETTING_OUT_OF_RANGE", "INVALID_GRADE_BOUNDARY"}


def test_json_setting_is_coerced():
    result = coerce("load_band_edges", "[40, 60, 80, 95]")

    assert result == [40, 60, 80, 95]


# --- 우선순위 가중치 (specs/19 §3.3) ---


def test_priority_weights_must_sum_to_one():
    with pytest.raises(SettingValidationError) as exc:
        validate(
            {"priority_weights": {"fi": 0.5, "slope": 0.5, "daily_loss": 0.5, "urgency": 0.5}}, {}
        )

    assert exc.value.code == "INVALID_WEIGHTS"
    assert exc.value.details["suggestion"]["fi"] == 0.25


def test_priority_weights_accept_valid_sum():
    result = validate(
        {"priority_weights": {"fi": 0.3, "slope": 0.2, "daily_loss": 0.35, "urgency": 0.15}}, {}
    )

    assert result["priority_weights"]["daily_loss"] == 0.35


def test_priority_weights_reject_missing_component():
    with pytest.raises(SettingValidationError) as exc:
        validate({"priority_weights": {"fi": 1.0}}, {})

    assert exc.value.details["missing"] == ["slope", "daily_loss", "urgency"]
