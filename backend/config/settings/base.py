"""공통 Django 설정. 환경별 차이는 dev.py / prod.py 에 둔다."""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def env_bool(key: str, default: bool = False) -> bool:
    return env(key, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def env_list(key: str, default: str = "") -> list[str]:
    return [item.strip() for item in env(key, default).split(",") if item.strip()]


def env_path(key: str, default: str) -> Path:
    raw = Path(env(key, default))
    return raw if raw.is_absolute() else (BASE_DIR / raw).resolve()


SECRET_KEY = env("DJANGO_SECRET_KEY", "insecure-dev-key-change-me")
DEBUG = env_bool("DJANGO_DEBUG", False)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "common",
    "accounts",
    "units",
    "ingestion",
    "maintenance",
    "analysis",
    "reports",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        # SPA를 쓰므로 앱 화면용 템플릿은 없다. Django Admin 전용(AGENTS.md §2).
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# --- DB : PostgreSQL 고정 (AGENTS.md §2) ---
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("DB_NAME", "hrsg"),
        "USER": env("DB_USER", "hrsg"),
        "PASSWORD": env("DB_PASSWORD", "hrsg"),
        "HOST": env("DB_HOST", "localhost"),
        "PORT": env("DB_PORT", "5432"),
        "ATOMIC_REQUESTS": False,
    }
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- 인증 ---
# specs/01 §2 — username 을 제거하고 employee_no 를 USERNAME_FIELD 로 사용한다.
AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = [
    "accounts.backends.EmployeeNoBackend",
    # Django /admin/ 로그인 폼 전용(사번+비밀번호). 앱 로그인은 뷰에서 성명까지 3요소를
    # 직접 검증하므로 이 백엔드를 거치지 않는다(specs/01 §3.2).
    "django.contrib.auth.backends.ModelBackend",
]

# specs/01 §6 — 기본 관리자 계정 'qwer' 허용을 위해 MinimumLengthValidator(4) 만 활성화한다.
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 4},
    },
]

# --- 세션 : 세션 쿠키 + CSRF 로 확정 (specs/15 §1, specs/01 §3.3) ---
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = int(env("SESSION_TIMEOUT_HOURS", "8")) * 3600
SESSION_SAVE_EVERY_REQUEST = True  # 8시간 "무활동" 기준이므로 요청마다 만료를 갱신한다.
CSRF_COOKIE_HTTPONLY = False  # SPA가 읽어 X-CSRFToken 헤더로 되돌려보낸다.
CSRF_COOKIE_SAMESITE = "Lax"

# --- i18n / tz : specs/18 §5 ---
LANGUAGE_CODE = "ko-kr"
TIME_ZONE = "Asia/Seoul"  # DB 저장은 UTC, 표시·집계는 KST
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# 업로드 원본은 미디어 루트 밖 별도 경로에 둔다(specs/18 §2).
MEDIA_URL = "/media/"
MEDIA_ROOT = env_path("MEDIA_ROOT", "./var/media")
UPLOAD_ROOT = env_path("UPLOAD_ROOT", "./var/uploads")
REPORT_ROOT = env_path("REPORT_ROOT", "./var/reports")
MODEL_ARTIFACT_ROOT = env_path("MODEL_ARTIFACT_ROOT", "./var/models")

# --- DRF : specs/15 §1 ---
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    # 기본 권한은 인증 필수. 관리자 전용은 IsAdminRole 을 뷰에 명시한다(AGENTS.md §7).
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "common.pagination.StandardPagination",
    "PAGE_SIZE": 50,
    "EXCEPTION_HANDLER": "common.handlers.domain_exception_handler",
    "DEFAULT_FILTER_BACKENDS": [
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.ScopedRateThrottle"],
    # specs/15 §13 — 로그인은 IP 기준 분당 10회.
    "DEFAULT_THROTTLE_RATES": {"login": "10/min"},
    "UNAUTHENTICATED_USER": None,
}

# --- Celery : specs/18 §7 ---
CELERY_BROKER_URL = env("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", CELERY_BROKER_URL)
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
# 100만 행 적재 5분, 모델 재학습 3분 목표(specs/18 §1)를 넉넉히 감싸는 상한.
CELERY_TASK_TIME_LIMIT = 30 * 60
CELERY_TASK_SOFT_TIME_LIMIT = 25 * 60
# 실패 시 재시도 1회 후 실패 기록 (specs/18 §3)
CELERY_TASK_DEFAULT_RETRY_DELAY = 10
CELERY_TASK_MAX_RETRIES = 1
CELERY_RESULT_EXPIRES = 60 * 60 * 24
# 테스트에서는 워커 없이 즉시 실행한다.
CELERY_TASK_ALWAYS_EAGER = env_bool("CELERY_TASK_ALWAYS_EAGER", False)
CELERY_TASK_EAGER_PROPAGATES = True

# 업로드: 대용량 CSV는 항상 디스크에 흘려 메모리 사용을 억제한다(specs/03 §7).
FILE_UPLOAD_MAX_MEMORY_SIZE = 2 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 2 * 1024 * 1024
DATA_UPLOAD_MAX_NUMBER_FIELDS = 2000

# --- 로깅 : specs/18 §4. 비밀번호·사번은 마스킹한다. ---
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "mask_sensitive": {"()": "common.logging_filters.MaskSensitiveFilter"},
    },
    "formatters": {
        "standard": {
            "format": "{asctime} {levelname} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
            "filters": ["mask_sensitive"],
        },
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django.db.backends": {"level": "WARNING", "handlers": ["console"], "propagate": False},
    },
}
