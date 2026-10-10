"""유효 설정값 조회기.

조회 우선순위 (specs/08 §4): Setting(DB) → setting_defaults 의 시드 기본값
"""

from typing import Any

from common.models import Setting
from common.setting_defaults import SETTING_DEF_BY_KEY, SETTING_DEFS, cast_value


def get_setting(key: str) -> Any:
    """설정값 하나를 타입 캐스팅해서 반환한다."""
    row = Setting.objects.filter(key=key).only("value", "value_type").first()
    if row is not None:
        return cast_value(row.value, row.value_type)

    definition = SETTING_DEF_BY_KEY.get(key)
    if definition is None:
        raise KeyError(f"정의되지 않은 설정 키입니다: {key}")
    return definition.default


def get_effective_settings(category: str | None = None) -> dict[str, Any]:
    """실제 적용되는 최종 설정값 전체."""
    defs = SETTING_DEFS
    if category:
        defs = tuple(d for d in defs if d.category == category)

    keys = [d.key for d in defs]
    rows = {
        row.key: row
        for row in Setting.objects.filter(key__in=keys).only("key", "value", "value_type")
    }

    effective: dict[str, Any] = {}
    for definition in defs:
        row = rows.get(definition.key)
        if row is not None:
            effective[definition.key] = cast_value(row.value, row.value_type)
        else:
            effective[definition.key] = definition.default
    return effective
