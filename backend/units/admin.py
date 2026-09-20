from django.contrib import admin

from units.models import Setting


@admin.register(Setting)
class SettingAdmin(admin.ModelAdmin):
    list_display = [
        "key",
        "label",
        "category",
        "value",
        "default_value",
        "unit_label",
        "updated_at",
    ]
    list_filter = ["category"]
    search_fields = ["key", "label"]
    readonly_fields = ["key", "value_type", "category", "default_value", "updated_at"]
