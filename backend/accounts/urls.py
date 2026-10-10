"""/api/auth/ (specs/10 §2)."""

from django.urls import path

from accounts.views import (
    ChangePasswordView,
    CsrfView,
    LoginView,
    LogoutView,
    MeView,
    SignupView,
    UsernameAvailableView,
)

urlpatterns = [
    path("csrf/", CsrfView.as_view(), name="auth-csrf"),
    path("signup/", SignupView.as_view(), name="auth-signup"),
    path("username-available/", UsernameAvailableView.as_view(), name="auth-username-available"),
    path("login/", LoginView.as_view(), name="auth-login"),
    path("logout/", LogoutView.as_view(), name="auth-logout"),
    path("me/", MeView.as_view(), name="auth-me"),
    path("password/", ChangePasswordView.as_view(), name="auth-password"),
]
