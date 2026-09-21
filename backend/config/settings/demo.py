"""데모 배포 설정 (Render 등 PaaS).

`specs/18` §7 의 운영 구성은 Nginx 가 SPA·정적 파일을 서빙하고 그 뒤에 Gunicorn 이
서는 형태다. PaaS 는 컨테이너 하나만 띄우므로 그 역할을 Django 가 대신 맡는다.

**사내 운영에는 쓰지 않는다.** `PROJECT.md` §1.5 는 외부 공개 서비스를 범위 밖으로 두고
`specs/01` §1 은 폐쇄형 사내 시스템을 요구한다. 이 설정은 프로젝트 시연 전용이며,
실제 운전 데이터가 아니라 `scripts/generate_sample_data.py` 산출물을 쓴다는 전제다.

prod.py 와의 차이는 세 가지뿐이다.
1. WhiteNoise 가 정적 파일과 SPA 를 서빙한다(Nginx 부재).
2. HTTPS 리다이렉트를 끈다 — PaaS 가 앞단에서 이미 처리한다.
3. 워커 없이도 데모가 되도록 태스크를 동기 실행할 수 있다.
"""

import os
from urllib.parse import unquote, urlparse

from .base import BASE_DIR, MIDDLEWARE, TEMPLATES, env_bool
from .prod import *  # noqa: F403

# --- 정적 파일 · SPA ---------------------------------------------------------

# SecurityMiddleware 바로 뒤가 WhiteNoise 의 권장 위치다.
MIDDLEWARE = [
    MIDDLEWARE[0],
    "whitenoise.middleware.WhiteNoiseMiddleware",
    *MIDDLEWARE[1:],
]

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# 빌드된 SPA. 이미지 빌드 단계에서 frontend/dist 를 여기로 복사한다.
SPA_ROOT = BASE_DIR / "spa"

# WhiteNoise 가 이 디렉터리를 **루트 URL 에서** 서빙한다.
# Vite 산출물의 index.html 은 /assets/... 를 참조하므로 /static/ 아래로 옮기면
# 경로가 어긋나 자바스크립트 대신 SPA 폴백 HTML 이 나가고 화면이 비어 버린다.
WHITENOISE_ROOT = SPA_ROOT

# SPA 는 WHITENOISE_ROOT 가 맡으므로 collectstatic 대상에 넣지 않는다.
# 넣으면 /static/ 아래로 중복 복사되고 매니페스트 처리에서 걸린다.
STATICFILES_DIRS: list = []

# TemplateView 가 SPA 진입점(index.html)을 찾을 수 있게 한다.
# Django Template 기능을 쓰는 게 아니라 빌드된 정적 파일을 그대로 내보내는 것이다.
TEMPLATES[0]["DIRS"] = [SPA_ROOT]

# config/urls.py 가 이 플래그를 보고 SPA 폴백 라우트를 붙인다.
SERVE_SPA = True

# --- PaaS 앞단이 TLS 를 끊는다 ------------------------------------------------

# 리다이렉트를 켜면 플랫폼 헬스체크·내부 요청이 301 로 튕긴다.
SECURE_SSL_REDIRECT = False
# Render 는 *.onrender.com 로 서비스한다. 배포 시 실제 호스트를 넣는다.
ALLOWED_HOSTS = [h for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",") if h]
if hostname := os.environ.get("RENDER_EXTERNAL_HOSTNAME"):
    ALLOWED_HOSTS.append(hostname)
    CSRF_TRUSTED_ORIGINS = [f"https://{hostname}"]

# --- 관리형 DB ---------------------------------------------------------------

# PaaS 는 접속 정보를 연결 문자열 하나로 준다(Render: DATABASE_URL).
# 우리 base.py 는 DB_NAME/DB_USER/... 개별 변수를 쓰므로 여기서 풀어 넣는다.
# dj-database-url 을 쓰지 않는 이유는 의존성을 하나라도 덜 늘리기 위해서다.
if database_url := os.environ.get("DATABASE_URL"):
    parsed = urlparse(database_url)
    DATABASES["default"].update(  # noqa: F405
        {
            "NAME": parsed.path.lstrip("/"),
            "USER": unquote(parsed.username or ""),
            "PASSWORD": unquote(parsed.password or ""),
            "HOST": parsed.hostname or "",
            "PORT": str(parsed.port or 5432),
            # 관리형 DB 는 대개 TLS 를 요구한다.
            "OPTIONS": {"sslmode": os.environ.get("DB_SSLMODE", "require")},
        }
    )


# --- 워커 없이 돌리는 모드 ----------------------------------------------------

# 무료 플랜에는 백그라운드 워커가 없다. 켜면 업로드·분석이 요청 안에서 끝난다.
# 샘플 데이터(10만 행) 기준 적재 12초·분석 9초라 데모에는 충분하지만,
# 요청이 그만큼 블로킹되므로 실제 운영에서는 절대 켜지 않는다.
if env_bool("DEMO_RUN_TASKS_INLINE", False):
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_TASK_EAGER_PROPAGATES = False
    # 동기 실행 결과도 백엔드에 저장해야 `GET /api/jobs/{id}/` 폴링이 성립한다.
    CELERY_TASK_STORE_EAGER_RESULT = True
