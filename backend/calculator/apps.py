from django.apps import AppConfig


class CalculatorConfig(AppConfig):
    """계산기 — 모델 없이 순수 함수(services)와 API 만 둔다 (specs/05)."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "calculator"
    verbose_name = "계산기"
