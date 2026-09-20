from django.urls import include, path
from rest_framework.routers import DefaultRouter

from maintenance.views import (
    CleaningEventViewSet,
    FoulingKeywordViewSet,
    MaintenanceRecordViewSet,
    MaintenanceUploadView,
)

router = DefaultRouter()
router.register("cleaning-events", CleaningEventViewSet, basename="cleaning-event")
router.register("maintenance-records", MaintenanceRecordViewSet, basename="maintenance-record")
router.register("fouling-keywords", FoulingKeywordViewSet, basename="fouling-keyword")
router.register("uploads/maintenance", MaintenanceUploadView, basename="maintenance-upload")

urlpatterns = [path("", include(router.urls))]
