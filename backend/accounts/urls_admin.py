"""사용자 관리 URL (specs/15 §3)."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from accounts.views_admin import LoginHistoryViewSet, UserViewSet

router = DefaultRouter()
router.register("users", UserViewSet, basename="user")
router.register("login-histories", LoginHistoryViewSet, basename="login-history")

urlpatterns = [path("", include(router.urls))]
