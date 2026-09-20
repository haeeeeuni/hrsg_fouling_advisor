"""DRF 예외 → 공통 에러 JSON 변환 (specs/15 §1).

모든 에러 응답은 {"error": {"code", "message", "details"}} 형태를 따른다.
"""

import logging
from typing import Any

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.http import Http404
from rest_framework import exceptions as drf_exc
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from common.exceptions import DomainError

logger = logging.getLogger(__name__)

# DRF 예외 클래스 → 공통 에러 코드
_DRF_CODE_MAP: dict[type[Exception], str] = {
    drf_exc.NotAuthenticated: "NOT_AUTHENTICATED",
    drf_exc.AuthenticationFailed: "NOT_AUTHENTICATED",
    drf_exc.PermissionDenied: "PERMISSION_DENIED",
    drf_exc.NotFound: "NOT_FOUND",
    drf_exc.MethodNotAllowed: "METHOD_NOT_ALLOWED",
    drf_exc.Throttled: "RATE_LIMITED",
    drf_exc.ParseError: "PARSE_ERROR",
    drf_exc.UnsupportedMediaType: "UNSUPPORTED_MEDIA_TYPE",
}

_DEFAULT_MESSAGES: dict[str, str] = {
    "NOT_AUTHENTICATED": "로그인이 필요합니다.",
    "PERMISSION_DENIED": "권한이 없습니다.",
    "NOT_FOUND": "대상을 찾을 수 없습니다.",
    "METHOD_NOT_ALLOWED": "허용되지 않은 요청 방식입니다.",
    "RATE_LIMITED": "요청이 너무 많습니다. 잠시 후 다시 시도해 주세요.",
    "PARSE_ERROR": "요청 본문을 해석할 수 없습니다.",
    "UNSUPPORTED_MEDIA_TYPE": "지원하지 않는 형식입니다.",
    "VALIDATION_ERROR": "입력값이 올바르지 않습니다.",
}


def _validation_details(detail: Any) -> dict[str, Any]:
    """DRF ValidationError 의 detail 을 필드별 details 로 펼친다."""
    if isinstance(detail, dict):
        return {key: [str(item) for item in _as_list(value)] for key, value in detail.items()}
    return {"non_field_errors": [str(item) for item in _as_list(detail)]}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else [value]


def domain_exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    # 1) 도메인 예외는 그대로 포맷팅한다.
    if isinstance(exc, DomainError):
        return Response(exc.to_payload(), status=exc.status_code)

    # 2) Django 기본 예외를 DRF 예외로 정규화한다.
    if isinstance(exc, Http404):
        exc = drf_exc.NotFound()
    elif isinstance(exc, DjangoPermissionDenied):
        exc = drf_exc.PermissionDenied()

    response = drf_exception_handler(exc, context)
    if response is None:
        # 처리되지 않은 예외는 DRF가 그대로 올려보내 500이 된다. 로그만 남긴다.
        logger.exception("Unhandled exception in %s", context.get("view"))
        return None

    if isinstance(exc, drf_exc.ValidationError):
        code = "VALIDATION_ERROR"
        details = _validation_details(exc.detail)
    else:
        code = _DRF_CODE_MAP.get(type(exc), "REQUEST_ERROR")
        details = {}

    message = _DEFAULT_MESSAGES.get(code)
    if not message:
        message = str(getattr(exc, "detail", "")) or "요청을 처리할 수 없습니다."

    if isinstance(exc, drf_exc.Throttled) and exc.wait:
        details = {"retry_after_sec": int(exc.wait)}

    payload: dict[str, Any] = {"code": code, "message": message}
    if details:
        payload["details"] = details
    response.data = {"error": payload}
    return response
