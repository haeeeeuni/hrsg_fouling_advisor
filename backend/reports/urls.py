from django.urls import include, path
from rest_framework.routers import DefaultRouter

from reports.views import AnalysisExportView, ComparisonExportView, ReportExportViewSet

router = DefaultRouter()
router.register("reports", ReportExportViewSet, basename="report")

urlpatterns = [
    path(
        "analysis-runs/<int:analysis_run_id>/export/",
        AnalysisExportView.as_view({"post": "create"}),
        name="analysis-export",
    ),
    path(
        "comparisons/<int:comparison_id>/export/",
        ComparisonExportView.as_view({"post": "create"}),
        name="comparison-export",
    ),
    path("", include(router.urls)),
]
