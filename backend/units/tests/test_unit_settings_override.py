"""호기별 설정 오버라이드 (specs/13 §4.1, AC-13-2). PostgreSQL 필요."""

import pytest

from units.models import Setting, Unit, UnitSetting
from units.settings_resolver import get_effective_settings, get_setting

pytestmark = pytest.mark.django_db


@pytest.fixture
def unit(db):
    return Unit.objects.create(code="U1", name="1호기", rated_power_mw=160, min_load_mw=60)


def test_unit_override_wins_over_global(seeded, unit):
    Setting.objects.filter(key="max_upload_mb").update(value="200")
    UnitSetting.objects.create(unit=unit, key="max_upload_mb", value="500")

    assert get_setting("max_upload_mb", unit.id) == 500
    assert get_setting("max_upload_mb") == 200


def test_without_override_global_is_used(seeded, unit):
    Setting.objects.filter(key="max_upload_mb").update(value="300")

    assert get_setting("max_upload_mb", unit.id) == 300


def test_override_falls_back_to_code_default_when_nothing_in_db(unit):
    assert get_setting("min_trend_points", unit.id) == 30


def test_effective_settings_merge_overrides(seeded, unit):
    UnitSetting.objects.create(unit=unit, key="min_trend_points", value="45")

    effective = get_effective_settings(unit.id)

    assert effective["min_trend_points"] == 45
    assert effective["max_forecast_days"] == 730


def test_override_of_another_unit_does_not_leak(seeded, unit):
    other = Unit.objects.create(code="U2", name="2호기", rated_power_mw=160, min_load_mw=60)
    UnitSetting.objects.create(unit=other, key="min_trend_points", value="99")

    assert get_setting("min_trend_points", unit.id) == 30


def test_json_setting_is_cast(seeded, unit):
    ranges = get_setting("physical_ranges", unit.id)

    assert ranges["ambient_temp_c"] == {"min": -40, "max": 60}
