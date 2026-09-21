"""루트 URL 설정. 앱 API는 모두 /api/ 아래에 둔다(specs/15 §1)."""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("accounts.urls")),
    path("api/", include("accounts.urls_admin")),
    path("api/", include("common.urls_audit")),
    path("api/", include("common.urls")),
    # 고정 경로를 먼저 둔다. 라우터의 상세 경로(/{pk}/)는 [^/.]+ 를 잡으므로
    # 순서를 바꾸면 리터럴 경로가 pk 로 먹힌다.
    #   analysis → units   : /api/units/comparison/
    #   maintenance → ingestion: /api/uploads/maintenance/
    path("api/", include("analysis.urls")),
    path("api/", include("units.urls")),
    path("api/", include("maintenance.urls")),
    path("api/", include("ingestion.urls")),
    path("api/", include("reports.urls")),
]
