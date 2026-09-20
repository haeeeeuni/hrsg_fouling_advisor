"""설정값 조회기 테스트 (specs/13 §4.1, AC-14-4 일부).

호기별 오버라이드(UnitSetting)는 Unit 모델과 함께 Phase 2에서 추가되므로,
여기서는 '전역 Setting → 코드 시드 기본값' 우선순위와 타입 캐스팅을 검증한다.
"""

import pytest

from units.models import Setting
from units.setting_defaults import SETTING_DEF_BY_KEY, cast_value, serialize_value
from units.settings_resolver import get_effective_settings, get_setting

pytestmark = pytest.mark.django_db


def test_falls_back_to_code_default_when_db_row_missing():
    assert Setting.objects.count() == 0

    assert get_setting("max_upload_mb") == 200


def test_db_value_takes_priority_over_code_default(seeded):
    Setting.objects.filter(key="max_upload_mb").update(value="777")

    assert get_setting("max_upload_mb") == 777


def test_unknown_key_raises():
    with pytest.raises(KeyError):
        get_setting("no_such_setting")


def test_value_is_cast_to_declared_type(seeded):
    value = get_setting("session_timeout_hours")

    assert isinstance(value, int)
    assert value == 8


def test_effective_settings_returns_every_defined_key(seeded):
    effective = get_effective_settings()

    assert set(effective) == set(SETTING_DEF_BY_KEY)
    assert effective["min_trend_points"] == 30


def test_effective_settings_can_filter_by_category(seeded):
    effective = get_effective_settings(category="SYSTEM")

    assert effective
    assert all(SETTING_DEF_BY_KEY[key].category == "SYSTEM" for key in effective)


def test_effective_settings_works_without_seed():
    """시드 전에도 코드 기본값으로 전체 설정을 구성할 수 있어야 한다."""
    effective = get_effective_settings()

    assert effective["max_forecast_days"] == 730


@pytest.mark.parametrize(
    ("raw", "value_type", "expected"),
    [
        ("10", "INT", 10),
        ("10.5", "FLOAT", 10.5),
        ("true", "BOOL", True),
        ("false", "BOOL", False),
        ("RULE", "STRING", "RULE"),
        ("[40, 60, 80, 95]", "JSON", [40, 60, 80, 95]),
    ],
)
def test_cast_value(raw, value_type, expected):
    assert cast_value(raw, value_type) == expected


@pytest.mark.parametrize(
    ("value", "value_type", "expected"),
    [
        (10, "INT", "10"),
        (0.6, "FLOAT", "0.6"),
        (True, "BOOL", "true"),
        ([40, 60], "JSON", "[40, 60]"),
    ],
)
def test_serialize_value(value, value_type, expected):
    assert serialize_value(value, value_type) == expected


def test_serialize_then_cast_roundtrips():
    for definition in SETTING_DEF_BY_KEY.values():
        raw = serialize_value(definition.default, definition.value_type)
        assert cast_value(raw, definition.value_type) == definition.default
