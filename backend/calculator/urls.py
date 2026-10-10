"""/api/calculator/ (specs/10 §4). 권한은 기본값(IsApprovedUser)."""

from django.urls import path

from calculator.views import LossView, MethodsView, OptionsView, PinchApproachView

urlpatterns = [
    path("options/", OptionsView.as_view(), name="calculator-options"),
    path("loss/", LossView.as_view(), name="calculator-loss"),
    path("methods/", MethodsView.as_view(), name="calculator-methods"),
    path("pinch-approach/", PinchApproachView.as_view(), name="calculator-pinch-approach"),
]
