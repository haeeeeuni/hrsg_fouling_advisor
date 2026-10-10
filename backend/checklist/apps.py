from django.apps import AppConfig


class ChecklistConfig(AppConfig):
    """플랜트 데이터 요청 체크리스트 (specs/07)."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "checklist"
    verbose_name = "데이터 요청 체크리스트"
