"""설정값 관리 API (specs/08 ADM-4, specs/10 §6).

**튜닝값은 코드에 하드코딩하지 않는다**(AGENTS.md §1.2). 이 화면이 유일한 변경 경로다.
"""

from __future__ import annotations

from django.db import transaction
from rest_framework import serializers, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsAdminRole
from common import audit
from common.exceptions import DomainError, NotFound
from common.models import AuditAction, Setting
from common.setting_defaults import CATEGORY_LABELS, SETTING_DEF_BY_KEY, cast_value, serialize_value
from common.settings_validation import SettingValidationError, validate

TARGET_SETTING = "Setting"


class SettingError(DomainError):
    """검증 실패를 공통 에러 포맷으로 내보낸다."""

    status_code = status.HTTP_400_BAD_REQUEST


class SettingSerializer(serializers.ModelSerializer):
    """현재값은 타입 캐스팅해서 내보낸다(문자열 저장은 구현 세부)."""

    value = serializers.SerializerMethodField()
    default = serializers.SerializerMethodField()
    is_modified = serializers.SerializerMethodField()
    category_label = serializers.SerializerMethodField()

    class Meta:
        model = Setting
        fields = [
            "key",
            "value",
            "default",
            "value_type",
            "category",
            "category_label",
            "label",
            "description",
            "unit_label",
            "min_value",
            "max_value",
            "is_modified",
            "updated_at",
        ]
        read_only_fields = fields

    def get_value(self, obj):
        return cast_value(obj.value, obj.value_type)

    def get_default(self, obj):
        return cast_value(obj.default_value, obj.value_type)

    def get_is_modified(self, obj) -> bool:
        return obj.value != obj.default_value

    def get_category_label(self, obj) -> str:
        return CATEGORY_LABELS.get(obj.category, obj.category)


def _apply(request: Request, changes: dict[str, str], action: str) -> list[str]:
    """{key: 직렬화된 새 값} 을 저장하고 감사 로그를 남긴다. 실제로 바뀐 키를 돌려준다."""
    rows = {row.key: row for row in Setting.objects.select_for_update().filter(key__in=changes)}
    missing = sorted(set(changes) - set(rows))
    if missing:
        raise SettingError(
            code="UNKNOWN_SETTING",
            message=f"정의되지 않은 설정 키입니다: {', '.join(missing)}",
            details={"keys": missing},
        )

    before: dict[str, str] = {}
    after: dict[str, str] = {}
    for key, new_value in changes.items():
        row = rows[key]
        if row.value == new_value:
            continue
        before[key], after[key] = row.value, new_value
        row.value = new_value
        row.updated_by = request.user
        row.save(update_fields=["value", "updated_by", "updated_at"])

    if after:
        audit.record(
            request=request,
            action=action,
            target_type=TARGET_SETTING,
            target_label=", ".join(sorted(after)),
            before=before,
            after=after,
        )
    return sorted(after)


class SettingListView(APIView):
    """GET/PATCH /api/admin/settings/ — {"login_max_failures": 5, ...}"""

    permission_classes = [IsAdminRole]

    def get(self, request: Request) -> Response:
        queryset = Setting.objects.all()
        if category := request.query_params.get("category"):
            queryset = queryset.filter(category=category)
        return Response(
            {
                "results": SettingSerializer(queryset, many=True).data,
                "categories": [
                    {"code": code, "label": label}
                    for code, label in CATEGORY_LABELS.items()
                    if any(d.category == code for d in SETTING_DEF_BY_KEY.values())
                ],
            }
        )

    @transaction.atomic
    def patch(self, request: Request) -> Response:
        updates = request.data
        if not isinstance(updates, dict) or not updates:
            raise SettingError(
                code="VALIDATION_ERROR", message="변경할 설정값을 하나 이상 보내야 합니다."
            )

        try:
            coerced = validate(dict(updates))
        except SettingValidationError as error:
            raise SettingError(
                message=error.message, code=error.code, details=error.details
            ) from error

        changes = {
            key: serialize_value(value, SETTING_DEF_BY_KEY[key].value_type)
            for key, value in coerced.items()
        }
        updated = _apply(request, changes, AuditAction.UPDATE)
        return Response(
            {
                "updated": updated,
                "results": SettingSerializer(
                    Setting.objects.filter(key__in=coerced), many=True
                ).data,
            }
        )


class SettingResetView(APIView):
    """POST /api/admin/settings/{key}/reset/ — 기본값으로 되돌린다."""

    permission_classes = [IsAdminRole]

    @transaction.atomic
    def post(self, request: Request, key: str) -> Response:
        row = Setting.objects.filter(key=key).first()
        if row is None:
            raise NotFound(message="설정 항목을 찾을 수 없습니다.")
        _apply(request, {key: row.default_value}, AuditAction.RESTORE)
        row.refresh_from_db()
        return Response(SettingSerializer(row).data)
