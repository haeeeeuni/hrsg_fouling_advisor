"""감사 로그 기록 유틸 (specs/13 §7).

DRF 뷰셋에 `AuditedModelMixin` 을 섞으면 생성·수정·삭제가 자동으로 남는다.
커스텀 액션은 `record()` 를 직접 호출한다.

**민감정보는 남기지 않는다**(AGENTS.md §7) — password 계열 필드는 스냅샷에서 제외한다.
"""

from __future__ import annotations

import logging
from typing import Any

from rest_framework.request import Request

from common.models import AuditAction, AuditLog

logger = logging.getLogger(__name__)

# 스냅샷에서 제외할 필드 (비밀번호·해시는 절대 남기지 않는다)
SENSITIVE_FIELDS = {"password", "passwd", "pwd", "new_password", "current_password", "token"}


def client_ip(request: Request | None) -> str | None:
    if request is None:
        return None
    meta = getattr(request, "META", {}) or {}
    forwarded = meta.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return meta.get("REMOTE_ADDR") or None


def snapshot(instance: Any, fields: list[str] | None = None) -> dict[str, Any]:
    """모델 인스턴스를 JSON 직렬화 가능한 dict 로 만든다."""
    if instance is None:
        return {}

    meta_fields = {f.name: f for f in instance._meta.fields}
    names = fields or list(meta_fields)
    out: dict[str, Any] = {}
    for name in names:
        if name in SENSITIVE_FIELDS:
            continue
        # auto_now 필드는 저장할 때마다 바뀌어 변경 목록을 오염시킨다.
        # 누가 언제 바꿨는지는 AuditLog 자체의 actor/created_at 이 이미 가지고 있다.
        if getattr(meta_fields.get(name), "auto_now", False):
            continue
        try:
            value = getattr(instance, name)
        except Exception:  # noqa: BLE001 - 접근 불가 필드는 건너뛴다.
            continue
        out[name] = _jsonify(value)
    return out


def _jsonify(value: Any) -> Any:
    from datetime import date, datetime
    from decimal import Decimal

    if value is None or isinstance(value, bool | int | float | str):
        return value
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict | list):
        return value
    # FK 등 모델 인스턴스는 pk 로 축약한다.
    pk = getattr(value, "pk", None)
    return pk if pk is not None else str(value)


def record(
    *,
    request: Request | None,
    action: str,
    target_type: str,
    target_id: Any = "",
    target_label: str = "",
    before: dict | None = None,
    after: dict | None = None,
) -> AuditLog | None:
    user = getattr(request, "user", None) if request else None
    try:
        return AuditLog.objects.create(
            actor=user if getattr(user, "is_authenticated", False) else None,
            action=action,
            target_type=target_type,
            target_id=str(target_id)[:50],
            target_label=str(target_label)[:200],
            before=before,
            after=after,
            ip=client_ip(request),
        )
    except Exception:  # noqa: BLE001 - 감사 기록 실패가 본 작업을 막아서는 안 된다.
        logger.exception("audit log failed action=%s target=%s", action, target_type)
        return None


class AuditedModelMixin:
    """ModelViewSet 에 섞으면 CRUD 가 감사 로그에 남는다.

    `audit_target_type` 과 `audit_label(instance)` 를 지정해 표시명을 정한다.
    """

    audit_target_type: str = ""

    def audit_label(self, instance: Any) -> str:
        return str(instance)

    def _audit_type(self) -> str:
        return self.audit_target_type or self.queryset.model.__name__

    def perform_create(self, serializer) -> None:
        super().perform_create(serializer)
        instance = serializer.instance
        record(
            request=self.request,
            action=AuditAction.CREATE,
            target_type=self._audit_type(),
            target_id=instance.pk,
            target_label=self.audit_label(instance),
            after=snapshot(instance),
        )

    def perform_update(self, serializer) -> None:
        before = snapshot(self.get_object())
        super().perform_update(serializer)
        instance = serializer.instance
        after = snapshot(instance)
        changed = {k: v for k, v in after.items() if before.get(k) != v}
        if not changed:
            return
        record(
            request=self.request,
            action=AuditAction.UPDATE,
            target_type=self._audit_type(),
            target_id=instance.pk,
            target_label=self.audit_label(instance),
            before={k: before.get(k) for k in changed},
            after=changed,
        )

    def perform_destroy(self, instance) -> None:
        before = snapshot(instance)
        label = self.audit_label(instance)
        pk = instance.pk
        super().perform_destroy(instance)
        record(
            request=self.request,
            action=AuditAction.DELETE,
            target_type=self._audit_type(),
            target_id=pk,
            target_label=label,
            before=before,
        )
