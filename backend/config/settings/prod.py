"""운영 설정. specs/18 §2 — DEBUG=False, ALLOWED_HOSTS 명시, 보안 헤더."""

from .base import *  # noqa: F403
from .base import SECRET_KEY, env_bool

DEBUG = False

# 플레이스홀더 키로 운영에 뜨는 사고를 막는다. SECRET_KEY 가 유출되면 세션 위조가 가능하다.
# .env.example 을 그대로 복사해 쓰는 경우가 가장 흔하므로 예시값도 함께 막는다.
_PLACEHOLDER_KEYS = {"insecure-dev-key-change-me", "change-me-in-production", ""}

# 길이는 엔트로피의 대리 지표일 뿐이라 느슨하게 잡는다.
# Django 의 get_random_secret_key() 는 50자, PaaS 가 자동 생성하는 키는 256비트를
# base64 로 담아 44자다. 둘 다 충분히 강하므로 50자 기준은 후자를 오탐한다.
_MIN_SECRET_KEY_LENGTH = 40

if SECRET_KEY in _PLACEHOLDER_KEYS or len(SECRET_KEY) < _MIN_SECRET_KEY_LENGTH:
    raise RuntimeError(
        f"DJANGO_SECRET_KEY 가 안전하지 않습니다"
        f"(예시값이거나 {_MIN_SECRET_KEY_LENGTH}자 미만 — 현재 {len(SECRET_KEY)}자). "
        "운영 환경에서는 충분히 길고 무작위한 값을 지정해야 합니다(specs/18 §2).\n"
        '생성: python -c "import secrets; print(secrets.token_urlsafe(64))"'
    )

# 운영은 동일 오리진(Nginx가 SPA와 /api/를 함께 서빙)이므로 CORS를 열지 않는다.
CORS_ALLOWED_ORIGINS: list[str] = []
CORS_ALLOW_CREDENTIALS = False

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# specs/18 §2 가 Secure 쿠키와 HSTS 를 요구하므로 HTTPS 가 전제다.
# TLS 를 앞단(LB)에서 끊고 이미 리다이렉트까지 처리한다면 환경변수로 끌 수 있다.
SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", True)
# 헬스체크는 컨테이너 내부에서 http 로 들어온다. 리다이렉트되면 기동 판정이 실패한다.
SECURE_REDIRECT_EXEMPT = [r"^api/health/"]

SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
X_FRAME_OPTIONS = "DENY"
