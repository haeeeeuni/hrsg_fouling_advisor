"""루트 URL 설정. 앱 API는 모두 /api/ 아래에 둔다(specs/15 §1)."""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("accounts.urls")),
    path("api/", include("accounts.urls_admin")),
    path("api/", include("common.urls_audit")),
    path("api/", include("common.urls")),
    # analysis 를 units 보다 먼저 둔다 — /api/units/comparison/ 이
    # units 라우터의 상세 경로(/api/units/{pk}/)에 먼저 잡히는 것을 막는다.
    path("api/", include("analysis.urls")),
    path("api/", include("units.urls")),
    path("api/", include("ingestion.urls")),
    path("api/", include("maintenance.urls")),
    path("api/", include("reports.urls")),
]
