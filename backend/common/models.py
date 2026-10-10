"""설정값과 감사 로그 (specs/08 §4·§5, specs/09 §8)."""

from django.conf import settings as django_settings
from django.db import models

from common.setting_defaults import (
    CATEGORY_LABELS,
    TYPE_BOOL,
    TYPE_FLOAT,
    TYPE_INT,
    TYPE_JSON,
    TYPE_STRING,
    TYPE_TEXT,
)


class SettingValueType(models.TextChoices):
    INT = TYPE_INT, "정수"
    FLOAT = TYPE_FLOAT, "실수"
    BOOL = TYPE_BOOL, "참/거짓"
    STRING = TYPE_STRING, "문자열"
    TEXT = TYPE_TEXT, "긴 문자열"
    JSON = TYPE_JSON, "JSON"


class Setting(models.Model):
    """전역 설정값. 값은 문자열로 저장하고 value_type 으로 캐스팅한다.

    라벨·설명·범위는 코드 정의(setting_defaults)를 seed_defaults 가 동기화한다.
    """

    key = models.CharField("키", max_length=80, unique=True)
    value = models.TextField("현재값")
    value_type = models.CharField("값 타입", max_length=10, choices=SettingValueType.choices)
    category = models.CharField("분류", max_length=20, choices=list(CATEGORY_LABELS.items()))
    label = models.CharField("표시 이름", max_length=100)
    description = models.TextField("설명", blank=True)
    default_value = models.TextField("기본값")
    min_value = models.FloatField("최솟값", null=True, blank=True)
    max_value = models.FloatField("최댓값", null=True, blank=True)
    unit_label = models.CharField("단위", max_length=20, blank=True)
    updated_by = models.ForeignKey(
        django_settings.AUTH_USER_MODEL,
        verbose_name="변경자",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_settings",
    )
    updated_at = models.DateTimeField("변경 일시", auto_now=True)

    class Meta:
        verbose_name = "설정값"
        verbose_name_plural = "설정값"
        ordering = ["category", "key"]
        indexes = [models.Index(fields=["category"])]

    def __str__(self) -> str:
        return f"{self.key}={self.value}"


class AuditAction(models.TextChoices):
    CREATE = "CREATE", "생성"
    UPDATE = "UPDATE", "수정"
    DELETE = "DELETE", "삭제"
    ACTIVATE = "ACTIVATE", "활성화"
    RESTORE = "RESTORE", "복원"
    APPROVE = "APPROVE", "승인"
    REJECT = "REJECT", "반려"


class AuditLog(models.Model):
    """관리자의 모든 변경 작업 (specs/08 ADM-6).

    비밀번호·API 키·문서 원본은 스냅샷에 남기지 않는다.
    """

    actor = models.ForeignKey(
        django_settings.AUTH_USER_MODEL,
        verbose_name="행위자",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    action = models.CharField("동작", max_length=20, choices=AuditAction.choices)
    target_type = models.CharField("대상 종류", max_length=50)
    target_id = models.CharField("대상 식별자", max_length=50, blank=True)
    target_label = models.CharField("대상 표시명", max_length=200, blank=True)

    before = models.JSONField("변경 전", null=True, blank=True)
    after = models.JSONField("변경 후", null=True, blank=True)

    ip = models.GenericIPAddressField("IP", null=True, blank=True)
    created_at = models.DateTimeField("일시", auto_now_add=True)

    class Meta:
        verbose_name = "감사 로그"
        verbose_name_plural = "감사 로그"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["target_type", "-created_at"]),
            models.Index(fields=["actor", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.action} {self.target_type}#{self.target_id}"
