from django.urls import include, path
from rest_framework.routers import DefaultRouter

from ingestion.views import UploadBatchViewSet

router = DefaultRouter()
router.register("uploads", UploadBatchViewSet, basename="upload")

urlpatterns = [path("", include(router.urls))]
