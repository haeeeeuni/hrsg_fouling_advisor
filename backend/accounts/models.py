"""사용자 및 로그인 이력 모델 (specs/01, specs/14 §4.1).

핵심 결정: username 필드를 제거하고 employee_no 를 USERNAME_FIELD 로 사용한다.
이 결정은 첫 마이그레이션 이전에 확정되어야 한다(specs/14 §7).
"""

from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.db import models

from accounts.managers import UserManager
from common.constants import ROLE_ADMIN, ROLE_USER

# specs/01 §5 — 사번은 영문 대문자+숫자 2~20자.
EMPLOYEE_NO_VALIDATOR = RegexValidator(
    regex=r"^[A-Z0-9]{2,20}$",
    message="사번은 영문 대문자와 숫자 2~20자여야 합니다.",
)


class Role(models.TextChoices):
    USER = ROLE_USER, "일반 사용자"
    ADMIN = ROLE_ADMIN, "관리자"


class User(AbstractUser):
    # AbstractUser 의 username / first_name / last_name 은 사용하지 않는다(specs/01 §2).
    username = None  # type: ignore[assignment]
    first_name = None  # type: ignore[assignment]
    last_name = None  # type: ignore[assignment]

    employee_no = models.CharField(
        "사번",
        max_length=20,
        unique=True,
        validators=[EMPLOYEE_NO_VALIDATOR],
    )
    full_name = models.CharField("성명", max_length=50)
    role = models.CharField("역할", max_length=10, choices=Role.choices, default=Role.USER)
    department = models.CharField("부서", max_length=50, blank=True)
    phone = models.CharField("연락처", max_length=20, blank=True)
    must_change_password = models.BooleanField("비밀번호 변경 필요", default=False)
    last_login_at = models.DateTimeField("최근 로그인 일시", null=True, blank=True)
    created_at = models.DateTimeField("생성 일시", auto_now_add=True)
    updated_at = models.DateTimeField("수정 일시", auto_now=True)

    USERNAME_FIELD = "employee_no"
    REQUIRED_FIELDS = ["full_name"]

    objects = UserManager()

    class Meta:
        verbose_name = "사용자"
        verbose_name_plural = "사용자"
        ordering = ["employee_no"]

    def __str__(self) -> str:
        return f"{self.full_name}({self.employee_no})"

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


class LoginHistory(models.Model):
    """로그인 시도 이력 (specs/01 §7).

    실패 시에는 사용자가 특정되지 않을 수 있으므로 입력된 사번 문자열을 함께 보관한다.
    """

    user = models.ForeignKey(
        User,
        verbose_name="사용자",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="login_histories",
    )
    attempted_employee_no = models.CharField("입력 사번", max_length=20)
    full_name_input = models.CharField("입력 성명", max_length=50, blank=True)
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
            models.Index(fields=["attempted_employee_no", "-created_at"]),
            models.Index(fields=["-created_at"]),
        ]

    def __str__(self) -> str:
        status = "성공" if self.success else f"실패({self.fail_reason})"
        return f"{self.attempted_employee_no} {status}"
