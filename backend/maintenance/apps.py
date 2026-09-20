from django.apps import AppConfig


class MaintenanceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "maintenance"
    verbose_name = "정비·세정 이력"
