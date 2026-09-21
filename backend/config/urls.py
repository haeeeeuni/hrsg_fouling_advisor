"""루트 URL 설정. 앱 API는 모두 /api/ 아래에 둔다(specs/15 §1)."""

from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path

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

# 데모(PaaS) 배포에서만 Django 가 SPA 를 함께 서빙한다.
# 사내 운영은 Nginx 가 맡으므로 이 분기가 타지 않는다 (specs/18 §7).
if getattr(settings, "SERVE_SPA", False):
    from django.views.generic import TemplateView

    urlpatterns += [
        # /api/ 로 시작하지 않는 모든 경로를 SPA 진입점으로 보낸다.
        # Vue Router 가 클라이언트에서 실제 화면을 고른다.
        re_path(r"^(?!api/|static/|admin/).*$", TemplateView.as_view(template_name="index.html")),
    ]
