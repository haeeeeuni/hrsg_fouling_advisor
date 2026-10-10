"""사용자 및 로그인 이력 모델 (specs/01 §2, specs/09 §2).

로그인 식별자는 AbstractUser 의 username 이다. 대소문자를 구분하지 않도록 **소문자로 저장**한다.
사용자와 관리자는 같은 모델이고 role 로 구분한다. 가입만으로는 쓸 수 없고 승인(APPROVED)이 필요하다.
"""

from django.conf import settings as django_settings
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.db import models
from django.db.models.functions import Lower

from accounts.managers import UserManager
from common.constants import (
    APPROVAL_APPROVED,
    APPROVAL_PENDING,
    APPROVAL_REJECTED,
    ROLE_ADMIN,
    ROLE_USER,
)

# specs/01 §2 — 영문 소문자·숫자·. _ -, 4~30자. 소문자 변환 후 검사한다.
USERNAME_MIN_LENGTH = 4
USERNAME_MAX_LENGTH = 30
USERNAME_VALIDATOR = RegexValidator(
    regex=rf"^[a-z0-9._-]{{{USERNAME_MIN_LENGTH},{USERNAME_MAX_LENGTH}}}$",
    message=(
        f"ID 는 영문 소문자·숫자·마침표(.)·밑줄(_)·하이픈(-) "
        f"{USERNAME_MIN_LENGTH}~{USERNAME_MAX_LENGTH}자여야 합니다."
    ),
)


class Role(models.TextChoices):
    USER = ROLE_USER, "일반 사용자"
    ADMIN = ROLE_ADMIN, "관리자"


class ApprovalStatus(models.TextChoices):
    PENDING = APPROVAL_PENDING, "승인 대기"
    APPROVED = APPROVAL_APPROVED, "승인"
    REJECTED = APPROVAL_REJECTED, "반려"


class User(AbstractUser):
    # 성명은 full_name 하나로 받는다(specs/01 §2).
    first_name = None  # type: ignore[assignment]
    last_name = None  # type: ignore[assignment]

    username = models.CharField(
        "ID",
        max_length=USERNAME_MAX_LENGTH,
        unique=True,
        validators=[USERNAME_VALIDATOR],
        error_messages={"unique": "이미 사용 중인 ID 입니다."},
    )
    full_name = models.CharField("성명", max_length=50)
    organization = models.CharField("소속", max_length=100)
    signup_reason = models.TextField("가입 사유", max_length=500, blank=True)
    role = models.CharField("역할", max_length=10, choices=Role.choices, default=Role.USER)
    approval_status = models.CharField(
        "승인 상태",
        max_length=10,
        choices=ApprovalStatus.choices,
        default=ApprovalStatus.PENDING,
        db_index=True,
    )
    approved_by = models.ForeignKey(
        django_settings.AUTH_USER_MODEL,
        verbose_name="승인·반려 처리자",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    approved_at = models.DateTimeField("승인·반려 일시", null=True, blank=True)
    rejection_reason = models.TextField("반려 사유", max_length=500, blank=True)
    must_change_password = models.BooleanField("비밀번호 변경 필요", default=False)
    last_login_at = models.DateTimeField("최근 로그인 일시", null=True, blank=True)
    created_at = models.DateTimeField("생성 일시", auto_now_add=True)
    updated_at = models.DateTimeField("수정 일시", auto_now=True)

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ["full_name", "organization"]

    objects = UserManager()

    class Meta:
        verbose_name = "사용자"
        verbose_name_plural = "사용자"
        ordering = ["username"]
        constraints = [
            # 소문자 저장이 1차 방어선이고, 이 제약은 그 규칙이 깨졌을 때를 대비한다.
            models.UniqueConstraint(Lower("username"), name="accounts_user_username_ci_unique"),
        ]

    def __str__(self) -> str:
        return f"{self.full_name}({self.username})"

    def save(self, *args, **kwargs) -> None:
        if self.username:
            self.username = self.username.strip().lower()
        super().save(*args, **kwargs)

    def get_full_name(self) -> str:
        return self.full_name

    def get_short_name(self) -> str:
        return self.full_name

    @property
    def is_admin_role(self) -> bool:
        """앱 권한 판정은 role 로만 한다.

        Django 의 is_staff/is_superuser 는 /admin/ 접근용이며 앱 권한에 쓰지 않는다(specs/01 §2).
        """
        return self.role == Role.ADMIN

    @property
    def is_approved(self) -> bool:
        return self.approval_status == ApprovalStatus.APPROVED


class LoginHistory(models.Model):
    """로그인 시도 이력 (specs/09 §2).

    실패 시에는 사용자가 특정되지 않을 수 있으므로 입력된 ID 문자열을 함께 보관한다.
    """

    user = models.ForeignKey(
        User,
        verbose_name="사용자",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="login_histories",
    )
    attempted_username = models.CharField("입력 ID", max_length=150)
    success = models.BooleanField("성공 여부", default=False)
    fail_reason = models.CharField("실패 사유", max_length=30, blank=True)
    ip = models.GenericIPAddressField("IP", null=True, blank=True)
    user_agent = models.TextField("User-Agent", blank=True)
    created_at = models.DateTimeField("일시", auto_now_add=True)

    class Meta:
        verbose_name = "로그인 이력"
        verbose_name_plural = "로그인 이력"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["attempted_username", "-created_at"]),
            models.Index(fields=["-created_at"]),
        ]

    def __str__(self) -> str:
        status = "성공" if self.success else f"실패({self.fail_reason})"
        return f"{self.attempted_username} {status}"
