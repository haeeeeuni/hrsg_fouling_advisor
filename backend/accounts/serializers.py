"""입력 검증 및 표현 변환 (specs/01, specs/15 §2)."""

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from accounts.models import LoginHistory, User


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


class UserSerializer(serializers.ModelSerializer):
    """관리자용 사용자 CRUD (specs/01 §5)."""

    role_label = serializers.CharField(source="get_role_display", read_only=True)
    initial_password = serializers.CharField(write_only=True, required=False, min_length=4)

    class Meta:
        model = User
        fields = [
            "id",
            "employee_no",
            "full_name",
            "role",
            "role_label",
            "department",
            "phone",
            "email",
            "is_active",
            "must_change_password",
            "last_login_at",
            "created_at",
            "initial_password",
        ]
        read_only_fields = ["id", "role_label", "last_login_at", "created_at"]

    def validate_employee_no(self, value: str) -> str:
        value = value.strip().upper()
        # 사번은 변경 불가 (specs/01 §5)
        if self.instance and self.instance.employee_no != value:
            raise serializers.ValidationError("사번은 변경할 수 없습니다.")
        if not self.instance and User.objects.filter(employee_no=value).exists():
            raise serializers.ValidationError("이미 등록된 사번입니다.")
        return value

    def validate(self, attrs: dict) -> dict:
        if not self.instance and not attrs.get("initial_password"):
            raise serializers.ValidationError(
                {"initial_password": ["초기 비밀번호를 입력해야 합니다."]}
            )
        return attrs

    def create(self, validated_data: dict) -> User:
        password = validated_data.pop("initial_password")
        user = User.objects.create_user(
            employee_no=validated_data.pop("employee_no"),
            full_name=validated_data.pop("full_name"),
            password=password,
            # 생성 시 비밀번호 변경을 강제한다 (specs/01 §5)
            must_change_password=True,
            **validated_data,
        )
        return user

    def update(self, instance: User, validated_data: dict) -> User:
        validated_data.pop("initial_password", None)
        validated_data.pop("employee_no", None)
        return super().update(instance, validated_data)


class UserListSerializer(UserSerializer):
    class Meta(UserSerializer.Meta):
        fields = [f for f in UserSerializer.Meta.fields if f != "initial_password"]


class ResetPasswordSerializer(serializers.Serializer):
    new_password = serializers.CharField(min_length=4, max_length=128, write_only=True)

    def validate_new_password(self, value: str) -> str:
        try:
            validate_password(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages)) from exc
        return value


class LoginHistorySerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source="user.full_name", read_only=True, default="")

    class Meta:
        model = LoginHistory
        fields = [
            "id",
            "attempted_employee_no",
            "full_name_input",
            "full_name",
            "success",
            "fail_reason",
            "ip",
            "user_agent",
            "created_at",
        ]
        read_only_fields = fields
