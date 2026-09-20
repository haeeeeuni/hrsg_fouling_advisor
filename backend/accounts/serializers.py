"""입력 검증 및 표현 변환 (specs/01, specs/15 §2)."""

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from accounts.models import User


class LoginSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=50, label="성명")
    employee_no = serializers.CharField(max_length=20, label="사번")
    password = serializers.CharField(max_length=128, label="비밀번호", write_only=True)

    def validate_employee_no(self, value: str) -> str:
        return value.strip().upper()

    def validate_full_name(self, value: str) -> str:
        return value.strip()


class MeSerializer(serializers.ModelSerializer):
    """GET /api/auth/me/ 응답 (specs/15 §2)."""

    is_admin = serializers.BooleanField(source="is_admin_role", read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "employee_no",
            "full_name",
            "role",
            "is_admin",
            "department",
            "phone",
            "must_change_password",
            "last_login_at",
        ]
        read_only_fields = fields


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(max_length=128, write_only=True)
    new_password = serializers.CharField(max_length=128, write_only=True)

    def validate_new_password(self, value: str) -> str:
        # specs/01 §6 — MinimumLengthValidator(4) 만 활성화되어 있다.
        try:
            validate_password(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages)) from exc
        return value

    def validate(self, attrs: dict) -> dict:
        if attrs["current_password"] == attrs["new_password"]:
            raise serializers.ValidationError(
                {"new_password": ["기존 비밀번호와 다른 값을 입력해 주세요."]}
            )
        return attrs
