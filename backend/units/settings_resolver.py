"""유효 설정값 조회기.

조회 우선순위 (specs/13 §4.1):
    UnitSetting(호기 오버라이드) → Setting(전역) → setting_defaults 의 시드 기본값
"""

from typing import Any

from units.models import Setting, UnitSetting
from units.setting_defaults import SETTING_DEF_BY_KEY, SETTING_DEFS, cast_value


def _unit_override(key: str, unit_id: int | None) -> str | None:
    """호기별 오버라이드 값(문자열) 또는 None."""
    if unit_id is None:
        return None
    return (
        UnitSetting.objects.filter(unit_id=unit_id, key=key).values_list("value", flat=True).first()
    )


def _unit_overrides(keys: list[str], unit_id: int | None) -> dict[str, str]:
    """여러 키의 오버라이드를 한 번에 읽는다(N+1 방지)."""
    if unit_id is None:
        return {}
    return dict(
        UnitSetting.objects.filter(unit_id=unit_id, key__in=keys).values_list("key", "value")
    )


def get_setting(key: str, unit_id: int | None = None) -> Any:
    """설정값 하나를 타입 캐스팅해서 반환한다."""
    definition = SETTING_DEF_BY_KEY.get(key)

    override = _unit_override(key, unit_id)
    if override is not None:
        value_type = definition.value_type if definition else "STRING"
        return cast_value(override, value_type)

    row = Setting.objects.filter(key=key).only("value", "value_type").first()
    if row is not None:
        return cast_value(row.value, row.value_type)

    if definition is None:
        raise KeyError(f"정의되지 않은 설정 키입니다: {key}")
    return definition.default


def get_effective_settings(
    unit_id: int | None = None, category: str | None = None
) -> dict[str, Any]:
    """해당 호기에 실제 적용되는 최종 설정값 전체.

    AnalysisRun.settings_snapshot 에 그대로 저장해 재현성을 확보한다(AGENTS.md §1.3).
    """
    defs = SETTING_DEFS
    if category:
        defs = tuple(d for d in defs if d.category == category)

    # 전역값·오버라이드를 각각 한 번에 읽어 N+1 조회를 피한다.
    keys = [d.key for d in defs]
    rows = {
        row.key: row
        for row in Setting.objects.filter(key__in=keys).only("key", "value", "value_type")
    }
    overrides = _unit_overrides(keys, unit_id)

    effective: dict[str, Any] = {}
    for definition in defs:
        override = overrides.get(definition.key)
        if override is not None:
            effective[definition.key] = cast_value(override, definition.value_type)
            continue

        row = rows.get(definition.key)
        if row is not None:
            effective[definition.key] = cast_value(row.value, row.value_type)
        else:
            effective[definition.key] = definition.default

    return effective
