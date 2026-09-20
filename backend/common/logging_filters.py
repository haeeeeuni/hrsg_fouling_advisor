"""로그 마스킹 필터.

specs/18 §2 — 비밀번호·사번 전체를 로그에 남기지 않는다(AC-18-3).
"""

import logging
import re

# password=..., "password": "..." 등을 통째로 가린다.
_PASSWORD_RE = re.compile(
    r"(?i)(password|passwd|pwd|new_password|current_password)([\"']?\s*[:=]\s*[\"']?)([^\s,;}\"']+)"
)

# 사번 형태(영문 대문자+숫자 2~20자)는 앞 2자만 남기고 마스킹한다.
_EMPLOYEE_NO_RE = re.compile(r"\b([A-Z]{1,4}\d{1,}|[A-Z]\d{3,})\b")


def _mask_employee_no(match: re.Match[str]) -> str:
    token = match.group(1)
    if len(token) <= 2:
        return "*" * len(token)
    return f"{token[:2]}{'*' * (len(token) - 2)}"


def mask(text: str) -> str:
    text = _PASSWORD_RE.sub(r"\1\2***", text)
    return _EMPLOYEE_NO_RE.sub(_mask_employee_no, text)


class MaskSensitiveFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            # record.args가 있으면 먼저 포매팅한 뒤 마스킹해 원본 인자에 남지 않게 한다.
            message = record.getMessage()
        except Exception:  # pragma: no cover - 포매팅 실패 시 원본 유지
            return True
        record.msg = mask(message)
        record.args = ()
        return True
