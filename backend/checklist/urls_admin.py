"""체크리스트 템플릿 관리자 URL (specs/10 §6). /api/admin/ 아래에 붙는다."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from checklist.views import TemplateItemViewSet

router = DefaultRouter()
router.register("checklist-items", TemplateItemViewSet, basename="checklist-item")

urlpatterns = [path("", include(router.urls))]
