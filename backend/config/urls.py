"""루트 URL 설정. 앱 API는 모두 /api/ 아래, 관리자 API는 /api/admin/ 아래에 둔다(specs/10)."""

from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path

urlpatterns = [
    # Django 자체 관리 화면(비상용). SPA 의 관리자 모드(/admin/*)와 겹치지 않게 경로를 바꿨다.
    path("django-admin/", admin.site.urls),
    path("api/auth/", include("accounts.urls")),
    path("api/admin/", include("accounts.urls_admin")),
    path("api/admin/", include("common.urls_admin")),
    path("api/", include("common.urls")),
]

# 데모(PaaS) 배포에서만 Django 가 SPA 를 함께 서빙한다.
# 사내 운영은 Nginx 가 맡으므로 이 분기가 타지 않는다 (specs/13 §6).
if getattr(settings, "SERVE_SPA", False):
    from django.views.generic import TemplateView

    urlpatterns += [
        # /api/ 로 시작하지 않는 모든 경로를 SPA 진입점으로 보낸다.
        # Vue Router 가 클라이언트에서 실제 화면을 고른다.
        re_path(
            r"^(?!api/|static/|django-admin/).*$",
            TemplateView.as_view(template_name="index.html"),
        ),
    ]
