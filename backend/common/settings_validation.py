"""설정값 검증 (specs/08 ADM-4).

값 변경 시 즉시 검증한다: 정의 존재, 타입, min/max 범위.
순수 함수 모듈 — Django 모델을 import 하지 않는다.
"""

from __future__ import annotations

from typing import Any

from common.setting_defaults import (
    SETTING_DEF_BY_KEY,
    TYPE_BOOL,
    TYPE_FLOAT,
    TYPE_INT,
    TYPE_JSON,
    cast_value,
)


class SettingValidationError(Exception):
    def __init__(self, code: str, message: str, details: dict | None = None) -> None:
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)


def coerce(key: str, raw: Any) -> Any:
    """입력값을 정의된 타입으로 변환한다."""
    definition = SETTING_DEF_BY_KEY.get(key)
    if definition is None:
        raise SettingValidationError(
            "UNKNOWN_SETTING", f"정의되지 않은 설정 키입니다: {key}", {"key": key}
        )

    type_error = SettingValidationError(
        "SETTING_TYPE_ERROR",
        f"{definition.label}: 값 형식이 올바르지 않습니다.",
        {"key": key, "expected": definition.value_type},
    )
    try:
        if isinstance(raw, str):
            return cast_value(raw, definition.value_type)
        if definition.value_type == TYPE_INT:
            if isinstance(raw, bool) or not float(raw).is_integer():
                raise type_error
            return int(raw)
        if definition.value_type == TYPE_FLOAT:
            if isinstance(raw, bool):
                raise type_error
            return float(raw)
        if definition.value_type == TYPE_BOOL:
            if not isinstance(raw, bool):
                raise type_error
            return raw
        if definition.value_type == TYPE_JSON:
            return raw
    except (ValueError, TypeError) as exc:
        raise type_error from exc
    # 문자열 계열에 문자열이 아닌 값이 들어왔다.
    raise type_error


def check_range(key: str, value: Any) -> None:
    definition = SETTING_DEF_BY_KEY[key]
    if definition.min_value is None and definition.max_value is None:
        return
    if not isinstance(value, int | float) or isinstance(value, bool):
        return

    if definition.min_value is not None and value < definition.min_value:
        raise SettingValidationError(
            "SETTING_OUT_OF_RANGE",
            f"{definition.label}: 최솟값 {definition.min_value:g} 이상이어야 합니다.",
            {"key": key, "min": definition.min_value, "value": value},
        )
    if definition.max_value is not None and value > definition.max_value:
        raise SettingValidationError(
            "SETTING_OUT_OF_RANGE",
            f"{definition.label}: 최댓값 {definition.max_value:g} 이하여야 합니다.",
            {"key": key, "max": definition.max_value, "value": value},
        )


def validate(updates: dict[str, Any]) -> dict[str, Any]:
    """변경분을 검증하고 타입 변환된 dict 를 돌려준다."""
    coerced = {key: coerce(key, value) for key, value in updates.items()}
    for key, value in coerced.items():
        check_range(key, value)
    return coerced
