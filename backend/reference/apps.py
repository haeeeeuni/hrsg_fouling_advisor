from django.apps import AppConfig


class ReferenceConfig(AppConfig):
    """참조 데이터 — GT 한계표·세정 공법·SMP·계산 파라미터 세트 (specs/06)."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "reference"
    verbose_name = "참조 데이터"
