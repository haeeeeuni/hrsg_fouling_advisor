"""로그 마스킹 필터.

specs/13 NFR-8 — 비밀번호·API 키를 로그에 남기지 않는다(AC-13-4).
마스킹은 마지막 방어선이다. 애초에 본문·키를 로그 인자로 넘기지 않는 것이 원칙이다.
"""

import logging
import re

# password=..., "password": "..." 등을 통째로 가린다.
_SECRET_FIELD_RE = re.compile(
    r"(?i)(password|passwd|pwd|new_password|current_password|api_key|secret)"
    r"([\"']?\s*[:=]\s*[\"']?)([^\s,;}\"']+)"
)

# LLM 공급자 키 형태(specs/04 LLM-2). OpenAI·Anthropic(sk-…), Google(AIza…).
_API_KEY_RE = re.compile(r"\b(sk-[A-Za-z0-9_-]{8,}|AIza[0-9A-Za-z_-]{20,})")


def mask(text: str) -> str:
    text = _SECRET_FIELD_RE.sub(r"\1\2***", text)
    return _API_KEY_RE.sub("***", text)


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
