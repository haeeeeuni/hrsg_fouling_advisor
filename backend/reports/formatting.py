"""리포트 공통 표기 규칙 (specs/16 §7, specs/09 §9).

프론트의 `utils/format.js` 와 같은 규칙을 서버에서도 쓴다.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

EMPTY = "–"

GRADE_LABELS = {"NORMAL": "정상", "CAUTION": "주의", "WARNING": "경고"}
CONFIDENCE_LABELS = {"HIGH": "높음", "MEDIUM": "보통", "LOW": "낮음"}
TREND_STATUS_LABELS = {
    "OK": "정상",
    "ALREADY_EXCEEDED": "이미 도달",
    "NO_TREND": "추세 미확인",
    "BEYOND_HORIZON": "예측 지평 밖",
    "INSUFFICIENT_DATA": "데이터 부족",
}


def _blank(value: Any) -> bool:
    return value is None or value == ""


def fi(value) -> str:
    return EMPTY if _blank(value) else f"{float(value):.1f}"


def currency(value, with_eok: bool = True) -> str:
    if _blank(value):
        return EMPTY
    number = float(value)
    text = f"{round(number):,} 원"
    if with_eok and abs(number) >= 1e8:
        text += f" ({number / 1e8:.2f}억)"
    return text


def dp(value) -> str:
    return EMPTY if _blank(value) else f"{float(value):.2f} kPa"


def temp(value) -> str:
    return EMPTY if _blank(value) else f"{float(value):.1f} ℃"


def power(value) -> str:
    return EMPTY if _blank(value) else f"{float(value):.1f} MW"


def percent(value) -> str:
    return EMPTY if _blank(value) else f"{float(value):.1f} %"


def count(value) -> str:
    return EMPTY if _blank(value) else f"{int(value):,}"


def ymd(value) -> str:
    if _blank(value):
        return EMPTY
    if isinstance(value, datetime | date):
        return value.strftime("%Y-%m-%d")
    return str(value)[:10]


def ymd_hm(value) -> str:
    if _blank(value):
        return EMPTY
    if isinstance(value, datetime):
        from django.utils import timezone

        local = timezone.localtime(value) if timezone.is_aware(value) else value
        return local.strftime("%Y-%m-%d %H:%M")
    return str(value)[:16]


def dday(days, status: str | None = None) -> str:
    if status == "ALREADY_EXCEEDED":
        return "이미 도달"
    if status in {"NO_TREND", "INSUFFICIENT_DATA"}:
        return "예측 불가"
    if status == "BEYOND_HORIZON":
        return "2년 내 도달 예상 없음"
    if _blank(days):
        return EMPTY
    return "이미 도달" if int(days) <= 0 else f"D-{int(days)}"


def grade(value) -> str:
    return GRADE_LABELS.get(value, EMPTY)


def confidence(value) -> str:
    return CONFIDENCE_LABELS.get(value, EMPTY)


def trend_status(value) -> str:
    return TREND_STATUS_LABELS.get(value, EMPTY)


def pdf_text(value: Any) -> Any:
    """PDF 출력용 글리프 치환 — 나눔고딕에 없는 문자를 있는 문자로 바꾼다."""
    from reports.pdf.fonts import pdf_safe

    return pdf_safe(value) if isinstance(value, str) else value


def sanitize_cell(value: Any) -> Any:
    """CSV 수식 인젝션 방지 (specs/18 §2, AC-18-5).

    엑셀 출력 시 `=`, `+`, `-`, `@` 로 시작하는 **문자열** 셀 앞에 작은따옴표를 붙인다.
    숫자는 그대로 둔다(음수가 문자열로 바뀌면 계산이 깨진다).
    """
    if isinstance(value, str) and value[:1] in {"=", "+", "-", "@"}:
        return f"'{value}"
    return value
