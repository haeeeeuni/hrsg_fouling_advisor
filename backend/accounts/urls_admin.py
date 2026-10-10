"""사용자 관리·가입 승인 URL (specs/10 §6). /api/admin/ 아래에 붙는다."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from accounts.views_admin import AdminOverviewView, LoginHistoryViewSet, UserViewSet

router = DefaultRouter()
router.register("users", UserViewSet, basename="user")
router.register("login-histories", LoginHistoryViewSet, basename="login-history")

urlpatterns = [
    path("overview/", AdminOverviewView.as_view(), name="admin-overview"),
    path("", include(router.urls)),
]
