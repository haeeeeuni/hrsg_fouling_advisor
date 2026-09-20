from django.urls import include, path
from rest_framework.routers import DefaultRouter

from analysis.views import AnalysisRunViewSet, ComparisonViewSet
from analysis.views_models import (
    CleanBaselinePeriodViewSet,
    ClusterDefinitionViewSet,
    ModelVersionViewSet,
)
from analysis.views_optional import (
    AutoRecalcConfigView,
    BacktestViewSet,
    NotificationViewSet,
    UnitComparisonView,
)

router = DefaultRouter()
router.register("analysis-runs", AnalysisRunViewSet, basename="analysis-run")
router.register("model-versions", ModelVersionViewSet, basename="model-version")
router.register("comparisons", ComparisonViewSet, basename="comparison")
router.register(
    "clean-baseline-periods", CleanBaselinePeriodViewSet, basename="clean-baseline-period"
)
router.register("cluster-definitions", ClusterDefinitionViewSet, basename="cluster-definition")
# --- Phase 7: 옵션 기능 (specs/19) ---
router.register("backtests", BacktestViewSet, basename="backtest")
router.register("notifications", NotificationViewSet, basename="notification")

urlpatterns = [
    # 라우터의 units/{pk}/ 와 겹치지 않도록 고정 경로를 먼저 둔다.
    path("units/comparison/", UnitComparisonView.as_view(), name="unit-comparison"),
    path(
        "units/<int:unit_id>/auto-recalc/",
        AutoRecalcConfigView.as_view(),
        name="unit-auto-recalc",
    ),
    path("", include(router.urls)),
]
