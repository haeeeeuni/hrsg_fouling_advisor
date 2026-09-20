"""로컬 개발 설정. DB는 Docker PostgreSQL을 사용한다(SQLite 금지)."""

from .base import *  # noqa: F403
from .base import env_bool, env_list

DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]"]

# 개발 시 Vite dev server(5173)가 다른 오리진이므로 화이트리스트를 연다(specs/18 §2).
CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", "http://localhost:5173")
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = CORS_ALLOWED_ORIGINS
