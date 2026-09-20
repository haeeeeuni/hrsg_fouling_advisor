"""설정값 관리 API (specs/15 §10).

**어떤 기준값도 코드에 하드코딩하지 않는다**(specs/13 §1). 이 화면이 유일한 변경 경로다.
"""

from __future__ import annotations

from django.db import transaction
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsAdminRole
from common import audit
from common.exceptions import DomainError, NotFound
from common.models import AuditAction
from units.models import Setting, Unit, UnitSetting
from units.serializers_settings import (
    RestoreDefaultsSerializer,
    SettingSerializer,
    SettingsPatchSerializer,
    UnitSettingSerializer,
)
from units.setting_defaults import SETTING_DEF_BY_KEY, SETTING_DEFS, serialize_value
from units.settings_resolver import get_effective_settings
from units.settings_validation import SettingValidationError, validate

TARGET_SETTING = "Setting"
TARGET_UNIT_SETTING = "UnitSetting"


class SettingError(DomainError):
    """검증 실패를 공통 에러 포맷으로 내보낸다."""

    status_code = status.HTTP_400_BAD_REQUEST


def _raise(error: SettingValidationError) -> None:
    raise SettingError(message=error.message, code=error.code, details=error.details)


def _get_unit(unit_id: int) -> Unit:
    unit = Unit.objects.filter(pk=unit_id).first()
    if unit is None:
        raise NotFound(message="호기를 찾을 수 없습니다.")
    return unit


class SettingListView(APIView):
    """GET/PATCH /api/settings/ — 전역 설정 (관리자)."""

    permission_classes = [IsAdminRole]

    def get(self, request: Request) -> Response:
        queryset = Setting.objects.all()
        if category := request.query_params.get("category"):
            queryset = queryset.filter(category=category)
        return Response(
            {
                "results": SettingSerializer(queryset, many=True).data,
                "categories": sorted({d.category for d in SETTING_DEFS}),
            }
        )

    @transaction.atomic
    def patch(self, request: Request) -> Response:
        serializer = SettingsPatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updates = serializer.validated_data

        try:
            coerced = validate(updates, get_effective_settings())
        except SettingValidationError as error:
            _raise(error)

        rows = {row.key: row for row in Setting.objects.filter(key__in=coerced)}
        missing = sorted(set(coerced) - set(rows))
        if missing:
            raise SettingError(
                code="UNKNOWN_SETTING",
                message=f"정의되지 않은 설정 키입니다: {', '.join(missing)}",
                details={"keys": missing},
            )

        changed: dict[str, dict] = {}
        for key, value in coerced.items():
            row = rows[key]
            new_value = serialize_value(value, row.value_type)
            if row.value == new_value:
                continue
            changed[key] = {"before": row.value, "after": new_value}
            row.value = new_value
            row.updated_by = request.user
            row.save(update_fields=["value", "updated_by", "updated_at"])

        if changed:
            audit.record(
                request=request,
                action=AuditAction.UPDATE,
                target_type=TARGET_SETTING,
                target_label=", ".join(sorted(changed)),
                before={k: v["before"] for k, v in changed.items()},
                after={k: v["after"] for k, v in changed.items()},
            )

        return Response(
            {
                "updated": sorted(changed),
                "results": SettingSerializer(
                    Setting.objects.filter(key__in=coerced), many=True
                ).data,
                # 변경은 다음 분석부터 적용된다. 기존 결과는 스냅샷이라 바뀌지 않는다.
                "notice": "다음 분석부터 적용됩니다. 기존 분석 결과는 변경되지 않습니다.",
            }
        )


class SettingRestoreDefaultsView(APIView):
    """POST /api/settings/restore-defaults/ — 항목별/카테고리별 기본값 복원."""

    permission_classes = [IsAdminRole]

    @transaction.atomic
    def post(self, request: Request) -> Response:
        serializer = RestoreDefaultsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        queryset = Setting.objects.all()
        if keys := data.get("keys"):
            queryset = queryset.filter(key__in=keys)
        elif category := data.get("category"):
            queryset = queryset.filter(category=category)

        restored = []
        for row in queryset:
            if row.value == row.default_value:
                continue
            restored.append({"key": row.key, "before": row.value, "after": row.default_value})
            row.value = row.default_value
            row.updated_by = request.user
            row.save(update_fields=["value", "updated_by", "updated_at"])

        if restored:
            audit.record(
                request=request,
                action=AuditAction.RESTORE,
                target_type=TARGET_SETTING,
                target_label=", ".join(r["key"] for r in restored),
                before={r["key"]: r["before"] for r in restored},
                after={r["key"]: r["after"] for r in restored},
            )

        return Response({"restored": [r["key"] for r in restored], "count": len(restored)})


class EffectiveSettingsView(APIView):
    """GET /api/settings/effective/?unit_id=1 — 실제 적용되는 최종값 (인증 사용자)."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        unit_id = request.query_params.get("unit_id")
        unit_id = int(unit_id) if unit_id else None
        if unit_id:
            _get_unit(unit_id)
        return Response({"unit_id": unit_id, "settings": get_effective_settings(unit_id)})


class UnitSettingView(APIView):
    """GET/PUT /api/units/{id}/settings/ — 호기별 오버라이드 (관리자)."""

    permission_classes = [IsAdminRole]

    def get(self, request: Request, unit_id: int) -> Response:
        unit = _get_unit(unit_id)
        overrides = {row.key: row for row in UnitSetting.objects.filter(unit=unit)}
        globals_ = {row.key: row for row in Setting.objects.all()}
        effective = get_effective_settings(unit.id)

        # 상속값과 오버라이드를 함께 보여준다 (specs/13 §4.3)
        rows = []
        for definition in SETTING_DEFS:
            global_row = globals_.get(definition.key)
            rows.append(
                {
                    "key": definition.key,
                    "label": definition.label,
                    "category": definition.category,
                    "unit_label": definition.unit_label,
                    "value_type": definition.value_type,
                    "min_value": definition.min_value,
                    "max_value": definition.max_value,
                    "global_value": (
                        SettingSerializer(global_row).data["value"]
                        if global_row
                        else definition.default
                    ),
                    "effective_value": effective[definition.key],
                    "is_overridden": definition.key in overrides,
                }
            )

        return Response(
            {
                "unit_id": unit.id,
                "overrides": UnitSettingSerializer(overrides.values(), many=True).data,
                "settings": rows,
            }
        )

    @transaction.atomic
    def put(self, request: Request, unit_id: int) -> Response:
        unit = _get_unit(unit_id)
        serializer = SettingsPatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updates = serializer.validated_data

        try:
            coerced = validate(updates, get_effective_settings(unit.id))
        except SettingValidationError as error:
            _raise(error)

        before = dict(UnitSetting.objects.filter(unit=unit).values_list("key", "value"))
        for key, value in coerced.items():
            definition = SETTING_DEF_BY_KEY[key]
            UnitSetting.objects.update_or_create(
                unit=unit,
                key=key,
                defaults={
                    "value": serialize_value(value, definition.value_type),
                    "updated_by": request.user,
                },
            )

        after = dict(UnitSetting.objects.filter(unit=unit).values_list("key", "value"))
        if before != after:
            audit.record(
                request=request,
                action=AuditAction.UPDATE,
                target_type=TARGET_UNIT_SETTING,
                target_id=unit.id,
                target_label=f"{unit.code} 오버라이드",
                before=before,
                after=after,
            )

        return self.get(request, unit_id)


class UnitSettingDeleteView(APIView):
    """DELETE /api/units/{id}/settings/{key}/ — 오버라이드 해제(전역값 상속)."""

    permission_classes = [IsAdminRole]

    def delete(self, request: Request, unit_id: int, key: str) -> Response:
        unit = _get_unit(unit_id)
        row = UnitSetting.objects.filter(unit=unit, key=key).first()
        if row is None:
            raise NotFound(message="해당 호기에 그 설정의 오버라이드가 없습니다.")

        before = {key: row.value}
        row.delete()
        audit.record(
            request=request,
            action=AuditAction.DELETE,
            target_type=TARGET_UNIT_SETTING,
            target_id=unit.id,
            target_label=f"{unit.code}.{key} 오버라이드 해제",
            before=before,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)
