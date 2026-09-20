"""Django Admin 등록.

관리자 콘솔은 Phase 6에서 SPA로 구현한다. 그 전까지 설정값·사용자를 손으로 손볼 수 있도록
최소한의 등록만 해 둔다. username 을 제거했으므로 기본 UserAdmin 은 쓸 수 없다.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from accounts.models import LoginHistory, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    ordering = ["employee_no"]
    list_display = ["employee_no", "full_name", "role", "department", "is_active", "last_login_at"]
    list_filter = ["role", "is_active", "department"]
    search_fields = ["employee_no", "full_name"]
    readonly_fields = ["last_login_at", "created_at", "updated_at"]

    fieldsets = (
        (None, {"fields": ("employee_no", "password")}),
        ("개인 정보", {"fields": ("full_name", "department", "phone", "email")}),
        ("권한", {"fields": ("role", "is_active", "is_staff", "is_superuser", "groups")}),
        ("상태", {"fields": ("must_change_password", "last_login_at", "created_at", "updated_at")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("employee_no", "full_name", "role", "password1", "password2"),
            },
        ),
    )


@admin.register(LoginHistory)
class LoginHistoryAdmin(admin.ModelAdmin):
    list_display = ["created_at", "attempted_employee_no", "success", "fail_reason", "ip"]
    list_filter = ["success", "fail_reason"]
    search_fields = ["attempted_employee_no"]
    readonly_fields = [f.name for f in LoginHistory._meta.fields]

    def has_add_permission(self, request) -> bool:  # 이력은 손으로 만들지 않는다.
        return False
