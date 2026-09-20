"""감사 로그 (specs/13 §7, specs/14 §4.6).

관리자의 모든 변경 작업을 행위자·일시·대상·변경 전후와 함께 기록한다.
대상: 사용자 CRUD, 호기 CRUD, 컬럼 매핑 변경, 설정 변경, 세정 이력 CRUD,
키워드 CRUD, 모델 활성화, 배치 롤백.
"""

from django.conf import settings as django_settings
from django.db import models


class AuditAction(models.TextChoices):
    CREATE = "CREATE", "생성"
    UPDATE = "UPDATE", "수정"
    DELETE = "DELETE", "삭제"
    ACTIVATE = "ACTIVATE", "활성화"
    RESTORE = "RESTORE", "복원"
    ROLLBACK = "ROLLBACK", "롤백"
    TRAIN = "TRAIN", "학습"


class AuditLog(models.Model):
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
