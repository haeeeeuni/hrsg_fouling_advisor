"""도메인 예외. DRF 핸들러가 공통 JSON 포맷으로 변환한다(AGENTS.md §4, specs/15 §1)."""

from typing import Any

from rest_framework import status


class DomainError(Exception):
    """모든 도메인 예외의 기반. code/message/details/status_code 를 갖는다."""

    code = "INTERNAL_ERROR"
    message = "처리 중 오류가 발생했습니다."
    status_code = status.HTTP_400_BAD_REQUEST

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        details: dict[str, Any] | None = None,
        status_code: int | None = None,
    ) -> None:
        self.message = message or self.message
        self.code = code or self.code
        self.details = details or {}
        self.status_code = status_code or self.status_code
        super().__init__(self.message)

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.details:
            payload["details"] = self.details
        return {"error": payload}


class ValidationError(DomainError):
    code = "VALIDATION_ERROR"
    message = "입력값이 올바르지 않습니다."
    status_code = status.HTTP_400_BAD_REQUEST


class NotAuthenticated(DomainError):
    code = "NOT_AUTHENTICATED"
    message = "로그인이 필요합니다."
    status_code = status.HTTP_401_UNAUTHORIZED


class PermissionDenied(DomainError):
    code = "PERMISSION_DENIED"
    message = "권한이 없습니다."
    status_code = status.HTTP_403_FORBIDDEN


class NotFound(DomainError):
    code = "NOT_FOUND"
    message = "대상을 찾을 수 없습니다."
    status_code = status.HTTP_404_NOT_FOUND


class Conflict(DomainError):
    code = "CONFLICT"
    message = "현재 상태에서는 처리할 수 없습니다."
    status_code = status.HTTP_409_CONFLICT


class LoginFailed(DomainError):
    """specs/01 §3.2 — 원인을 구분하지 않는 통일 메시지(계정 존재 여부 노출 방지)."""

    code = "LOGIN_FAILED"
    message = "성명, 사번 또는 비밀번호가 올바르지 않습니다."
    status_code = status.HTTP_400_BAD_REQUEST


class AccountInactive(DomainError):
    code = "ACCOUNT_INACTIVE"
    message = "비활성화된 계정입니다. 관리자에게 문의하세요."
    status_code = status.HTTP_400_BAD_REQUEST


class LoginLocked(DomainError):
    code = "LOGIN_LOCKED"
    message = "로그인 시도가 너무 많습니다. 잠시 후 다시 시도해 주세요."
    status_code = status.HTTP_429_TOO_MANY_REQUESTS


class DuplicateEmployeeNo(DomainError):
    code = "DUPLICATE_EMPLOYEE_NO"
    message = "이미 등록된 사번입니다."
    status_code = status.HTTP_400_BAD_REQUEST


class LastAdminProtected(DomainError):
    """specs/01 §5 — 마지막 활성 관리자 계정은 삭제·비활성화·역할 변경이 불가하다."""

    code = "LAST_ADMIN_PROTECTED"
    message = "마지막 관리자 계정은 비활성화하거나 역할을 변경할 수 없습니다."
    status_code = status.HTTP_409_CONFLICT


class SettingOutOfRange(DomainError):
    code = "SETTING_OUT_OF_RANGE"
    message = "설정값이 허용 범위를 벗어났습니다."
    status_code = status.HTTP_400_BAD_REQUEST
