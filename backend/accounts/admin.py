"""Django Admin 등록 — 비상용. 앱의 관리자 모드는 SPA(/admin/*)다."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from accounts.models import LoginHistory, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    ordering = ["username"]
    list_display = [
        "username",
        "full_name",
        "organization",
        "role",
        "approval_status",
        "is_active",
        "last_login_at",
    ]
    list_filter = ["role", "approval_status", "is_active"]
    search_fields = ["username", "full_name", "organization"]
    readonly_fields = ["last_login_at", "created_at", "updated_at", "approved_at"]

    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("개인 정보", {"fields": ("full_name", "organization", "email", "signup_reason")}),
        ("승인", {"fields": ("approval_status", "approved_by", "approved_at", "rejection_reason")}),
        ("권한", {"fields": ("role", "is_active", "is_staff", "is_superuser", "groups")}),
        ("상태", {"fields": ("must_change_password", "last_login_at", "created_at", "updated_at")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "username",
                    "full_name",
                    "organization",
                    "role",
                    "approval_status",
                    "password1",
                    "password2",
                ),
            },
        ),
    )


@admin.register(LoginHistory)
class LoginHistoryAdmin(admin.ModelAdmin):
    list_display = ["created_at", "attempted_username", "success", "fail_reason", "ip"]
    list_filter = ["success", "fail_reason"]
    search_fields = ["attempted_username"]
    readonly_fields = [f.name for f in LoginHistory._meta.fields]

    def has_add_permission(self, request) -> bool:  # 이력은 손으로 만들지 않는다.
        return False
