"""공통 직렬화 도구."""

from __future__ import annotations

from rest_framework import serializers

from common.exceptions import Conflict


class VersionedSerializer(serializers.ModelSerializer):
    """수정 요청에 version 을 실어 보내면, 다른 관리자가 먼저 고쳤을 때 409 를 낸다(specs/08 ADM-7).

    모델에 version(PositiveIntegerField) 이 있어야 한다. 값이 실제로 바뀐 경우에만 올린다.
    """

    def validate(self, attrs: dict) -> dict:
        expected = self.initial_data.get("version") if isinstance(self.initial_data, dict) else None
        if self.instance is not None and expected is not None:
            if int(expected) != self.instance.version:
                raise Conflict(
                    code="STALE_VERSION",
                    message="다른 관리자가 먼저 수정했습니다. 새로고침 후 다시 시도하세요.",
                    details={"current_version": self.instance.version},
                )
        return attrs

    def update(self, instance, validated_data):
        validated_data.pop("version", None)
        changed = any(getattr(instance, k) != v for k, v in validated_data.items())
        instance = super().update(instance, validated_data)
        if changed:
            instance.version += 1
            instance.save(update_fields=["version", "updated_at"])
        return instance
