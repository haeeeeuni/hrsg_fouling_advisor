"""루트 URL 설정. 앱 API는 모두 /api/ 아래에 둔다(specs/15 §1)."""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("accounts.urls")),
    path("api/", include("common.urls")),
    path("api/", include("units.urls")),
    path("api/", include("ingestion.urls")),
    path("api/", include("maintenance.urls")),
    path("api/", include("analysis.urls")),
    path("api/", include("reports.urls")),
]
