"""/api/checklist/ (specs/10 §5). 권한은 기본값(IsApprovedUser), 요청 건은 본인 것만."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from checklist.views import DataRequestViewSet

router = DefaultRouter()
router.register("requests", DataRequestViewSet, basename="data-request")

urlpatterns = [path("", include(router.urls))]
