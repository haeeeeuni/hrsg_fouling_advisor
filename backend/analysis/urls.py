from django.urls import include, path
from rest_framework.routers import DefaultRouter

from analysis.views import AnalysisRunViewSet, ComparisonViewSet, ModelVersionViewSet

router = DefaultRouter()
router.register("analysis-runs", AnalysisRunViewSet, basename="analysis-run")
router.register("model-versions", ModelVersionViewSet, basename="model-version")
router.register("comparisons", ComparisonViewSet, basename="comparison")

urlpatterns = [path("", include(router.urls))]
