"""참조 데이터 관리자 URL (specs/10 §6). /api/admin/ 아래에 붙는다."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from reference.views import (
    CalcParameterSetViewSet,
    CleaningMethodViewSet,
    GtModelViewSet,
    SmpPriceViewSet,
)

router = DefaultRouter()
router.register("gt-models", GtModelViewSet, basename="gt-model")
router.register("cleaning-methods", CleaningMethodViewSet, basename="cleaning-method")
router.register("smp-prices", SmpPriceViewSet, basename="smp-price")
router.register("calc-parameter-sets", CalcParameterSetViewSet, basename="calc-parameter-set")

urlpatterns = [path("", include(router.urls))]
