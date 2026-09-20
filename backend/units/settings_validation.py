"""설정값 검증 (specs/13 §4.3, §8).

값 변경 시 즉시 검증한다: min/max 범위, 가중치 합 = 1, 등급 경계 순서.
순수 함수 모듈 — Django 모델을 import 하지 않는다.
"""

from __future__ import annotations

from typing import Any

from units.setting_defaults import SETTING_DEF_BY_KEY, cast_value

# 합이 1이어야 하는 가중치 묶음
WEIGHT_GROUPS: tuple[tuple[str, ...], ...] = (("weight_dp", "weight_stack_temp"),)

# 하나의 JSON 값 안에서 합이 1이어야 하는 가중치 (specs/19 §3.3)
JSON_WEIGHT_KEYS: dict[str, tuple[str, ...]] = {
    "priority_weights": ("fi", "slope", "daily_loss", "urgency"),
}


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
    if isinstance(raw, str):
        try:
            return cast_value(raw, definition.value_type)
        except (ValueError, TypeError) as exc:
            raise SettingValidationError(
                "SETTING_TYPE_ERROR",
                f"{definition.label}: 값 형식이 올바르지 않습니다.",
                {"key": key, "expected": definition.value_type},
            ) from exc
    return raw


def check_range(key: str, value: Any) -> None:
    definition = SETTING_DEF_BY_KEY[key]
    if definition.min_value is None and definition.max_value is None:
        return
    if not isinstance(value, int | float) or isinstance(value, bool):
        return

    if definition.min_value is not None and value < definition.min_value:
        raise SettingValidationError(
            "SETTING_OUT_OF_RANGE",
            f"{definition.label}: 최솟값 {definition.min_value} 이상이어야 합니다.",
            {"key": key, "min": definition.min_value, "value": value},
        )
    if definition.max_value is not None and value > definition.max_value:
        raise SettingValidationError(
            "SETTING_OUT_OF_RANGE",
            f"{definition.label}: 최댓값 {definition.max_value} 이하여야 합니다.",
            {"key": key, "max": definition.max_value, "value": value},
        )


def check_weights(merged: dict[str, Any]) -> None:
    """가중치 합이 1이 아니면 거부하고 자동 정규화 값을 제안한다 (specs/13 §8)."""
    for group in WEIGHT_GROUPS:
        if not any(key in merged for key in group):
            continue
        values = [float(merged[key]) for key in group if key in merged]
        if len(values) != len(group):
            continue
        total = sum(values)
        if abs(total - 1.0) <= 1e-6:
            continue
        if total <= 0:
            raise SettingValidationError(
                "INVALID_WEIGHTS", "가중치 합은 0보다 커야 합니다.", {"keys": list(group)}
            )
        raise SettingValidationError(
            "INVALID_WEIGHTS",
            f"가중치 합이 1이 아닙니다(현재 {total:g}).",
            {
                "keys": list(group),
                "sum": total,
                "suggestion": {key: round(merged[key] / total, 6) for key in group},
            },
        )


def check_json_weights(merged: dict[str, Any]) -> None:
    """JSON 한 덩어리로 들어오는 가중치의 키 구성과 합을 본다 (specs/19 §3.3)."""
    for key, required in JSON_WEIGHT_KEYS.items():
        value = merged.get(key)
        if value is None:
            continue
        if not isinstance(value, dict):
            raise SettingValidationError(
                "INVALID_WEIGHTS", f"{key} 는 객체여야 합니다.", {"key": key}
            )
        missing = [name for name in required if name not in value]
        if missing:
            raise SettingValidationError(
                "INVALID_WEIGHTS",
                f"{key} 에 필요한 항목이 빠졌습니다.",
                {"key": key, "missing": missing},
            )

        total = sum(float(value[name]) for name in required)
        if abs(total - 1.0) <= 1e-6:
            continue
        if total <= 0:
            raise SettingValidationError(
                "INVALID_WEIGHTS", "가중치 합은 0보다 커야 합니다.", {"key": key}
            )
        raise SettingValidationError(
            "INVALID_WEIGHTS",
            f"가중치 합이 1이 아닙니다(현재 {total:g}).",
            {
                "key": key,
                "sum": total,
                "suggestion": {name: round(float(value[name]) / total, 6) for name in required},
            },
        )


def check_grade_boundaries(merged: dict[str, Any]) -> None:
    """grade_caution_min < grade_warning_min ≤ 100 (specs/07 §4)."""
    caution = merged.get("grade_caution_min")
    warning = merged.get("grade_warning_min")
    if caution is None or warning is None:
        return
    if not (0 <= float(caution) < float(warning) <= 100):
        raise SettingValidationError(
            "INVALID_GRADE_BOUNDARY",
            "등급 경계는 0 ≤ 주의 < 경고 ≤ 100 이어야 합니다.",
            {"grade_caution_min": caution, "grade_warning_min": warning},
        )


def validate(updates: dict[str, Any], effective: dict[str, Any]) -> dict[str, Any]:
    """변경분을 검증하고 타입 변환된 dict 를 돌려준다.

    effective 는 현재 적용 중인 전체 설정값이다. 가중치·등급 경계처럼
    **서로 얽힌 값**은 변경분만으로 판단할 수 없어 합쳐서 본다.
    """
    coerced = {key: coerce(key, value) for key, value in updates.items()}
    for key, value in coerced.items():
        check_range(key, value)

    merged = {**effective, **coerced}
    check_weights(merged)
    check_json_weights(merged)
    check_grade_boundaries(merged)
    return coerced
