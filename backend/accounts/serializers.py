"""입력 검증 및 표현 변환 (specs/01, specs/10 §2·§6)."""

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from accounts.models import USERNAME_VALIDATOR, LoginHistory, User


def _normalize_username(value: str) -> str:
    return (value or "").strip().lower()


def _check_password(value: str, user: User | None = None) -> str:
    try:
        validate_password(value, user=user)
    except DjangoValidationError as exc:
        raise serializers.ValidationError(list(exc.messages)) from exc
    return value


class SignupSerializer(serializers.Serializer):
    """POST /api/auth/signup/ (specs/01 AUTH-1)."""

    username = serializers.CharField(max_length=150, label="ID")
    password = serializers.CharField(max_length=128, write_only=True, label="비밀번호")
    password_confirm = serializers.CharField(max_length=128, write_only=True, label="비밀번호 확인")
    full_name = serializers.CharField(max_length=50, label="성명")
    organization = serializers.CharField(max_length=100, label="소속")
    email = serializers.EmailField(required=False, allow_blank=True, label="이메일")
    signup_reason = serializers.CharField(
        max_length=500, required=False, allow_blank=True, label="가입 사유"
    )

    def validate_username(self, value: str) -> str:
        value = _normalize_username(value)
        try:
            USERNAME_VALIDATOR(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages)) from exc
        # 반려된 ID 도 여기서 막힌다 — 관리자가 승인하거나 삭제해야 다시 쓸 수 있다(AUTH-5).
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("이미 사용 중인 ID 입니다.")
        return value

    def validate_full_name(self, value: str) -> str:
        return value.strip()

    def validate_organization(self, value: str) -> str:
        return value.strip()

    def validate(self, attrs: dict) -> dict:
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError(
                {"password_confirm": ["비밀번호가 일치하지 않습니다."]}
            )
        probe = User(
            username=attrs["username"],
            full_name=attrs["full_name"],
            email=attrs.get("email", ""),
        )
        try:
            _check_password(attrs["password"], probe)
        except serializers.ValidationError as exc:
            raise serializers.ValidationError({"password": exc.detail}) from exc
        return attrs

    def create(self, validated_data: dict) -> User:
        validated_data.pop("password_confirm")
        return User.objects.create_user(
            username=validated_data.pop("username"),
            full_name=validated_data.pop("full_name"),
            password=validated_data.pop("password"),
            **validated_data,
        )


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150, label="ID")
    password = serializers.CharField(max_length=128, label="비밀번호", write_only=True)

    def validate_username(self, value: str) -> str:
        return _normalize_username(value)


class MeSerializer(serializers.ModelSerializer):
    """GET /api/auth/me/ 응답."""

    is_admin = serializers.BooleanField(source="is_admin_role", read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "full_name",
            "organization",
            "email",
            "role",
            "is_admin",
            "must_change_password",
            "last_login_at",
        ]
        read_only_fields = fields


class MeUpdateSerializer(serializers.ModelSerializer):
    """PATCH /api/auth/me/ — 본인 정보 수정. ID·역할은 바꿀 수 없다."""

    class Meta:
        model = User
        fields = ["full_name", "organization", "email"]


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(max_length=128, write_only=True)
    new_password = serializers.CharField(max_length=128, write_only=True)

    def validate_new_password(self, value: str) -> str:
        return _check_password(value, self.context.get("user"))

    def validate(self, attrs: dict) -> dict:
        if attrs["current_password"] == attrs["new_password"]:
            raise serializers.ValidationError(
                {"new_password": ["기존 비밀번호와 다른 값을 입력해 주세요."]}
            )
        return attrs


class AdminUserSerializer(serializers.ModelSerializer):
    """관리자용 사용자 조회·수정 (specs/01 AUTH-10). 생성은 회원가입으로만 한다."""

    role_label = serializers.CharField(source="get_role_display", read_only=True)
    approval_status_label = serializers.CharField(
        source="get_approval_status_display", read_only=True
    )
    approved_by_name = serializers.CharField(
        source="approved_by.full_name", read_only=True, default=""
    )

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "full_name",
            "organization",
            "email",
            "signup_reason",
            "role",
            "role_label",
            "approval_status",
            "approval_status_label",
            "approved_by_name",
            "approved_at",
            "rejection_reason",
            "is_active",
            "must_change_password",
            "last_login_at",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "username",
            "signup_reason",
            "role_label",
            "approval_status",
            "approval_status_label",
            "approved_by_name",
            "approved_at",
            "rejection_reason",
            "must_change_password",
            "last_login_at",
            "created_at",
        ]


class RejectSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=500, label="반려 사유")

    def validate_reason(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError("반려 사유를 입력해 주세요.")
        return value


class ResetPasswordSerializer(serializers.Serializer):
    new_password = serializers.CharField(max_length=128, write_only=True)

    def validate_new_password(self, value: str) -> str:
        return _check_password(value, self.context.get("user"))


class LoginHistorySerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source="user.full_name", read_only=True, default="")

    class Meta:
        model = LoginHistory
        fields = [
            "id",
            "attempted_username",
            "full_name",
            "success",
            "fail_reason",
            "ip",
            "user_agent",
            "created_at",
        ]
        read_only_fields = fields
