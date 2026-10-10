"""진행률·이메일 문구 — 순수 함수 (specs/07 CHK-3·CHK-5).

Django 모델을 import 하지 않는다. 항목은 dict(category, name_ko, name_en, unit, is_required,
why_needed_ko, why_needed_en, state) 로 받는다 → DB 없이 단위 테스트한다.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

STATE_PENDING = "PENDING"
STATE_RECEIVED = "RECEIVED"
STATE_NOT_APPLICABLE = "NOT_APPLICABLE"

SCOPE_PENDING = "pending"
SCOPE_ALL = "all"

LANG_KO = "ko"
LANG_EN = "en"

REQUIRED_MARK = {LANG_KO: "필수", LANG_EN: "Required"}


def progress(items: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """필수 항목 기준 진행률. '해당 없음'은 분모에서 뺀다(AC-07-2).

    필수 항목이 하나도 없으면(전부 해당 없음 등) 완료로 본다.
    """
    required = [i for i in items if i["is_required"] and i["state"] != STATE_NOT_APPLICABLE]
    received = sum(1 for i in required if i["state"] == STATE_RECEIVED)
    total = len(required)
    return {
        "received": received,
        "total": total,
        "percent": 100 if total == 0 else round(received / total * 100),
        "complete": received == total,
    }


def progress_by_category(
    items: Iterable[Mapping[str, Any]], category_order: Mapping[str, int]
) -> list[dict[str, Any]]:
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for item in items:
        grouped.setdefault(item["category"], []).append(item)
    return [
        {"category": category, **progress(rows)}
        for category, rows in sorted(grouped.items(), key=lambda kv: category_order.get(kv[0], 999))
    ]


def email_text(
    items: Iterable[Mapping[str, Any]],
    *,
    lang: str,
    scope: str,
    header: str,
    footer: str,
    category_labels: Mapping[str, str],
    category_order: Mapping[str, int],
) -> str:
    """이메일 본문 (specs/07 CHK-5). 분류별로 묶고 항목명·단위·필수·이유를 한 줄씩 쓴다.

    scope=pending: 미수신 항목만 / all: 해당 없음을 뺀 전체(처음 요청할 때).
    """
    if scope == SCOPE_PENDING:
        selected = [i for i in items if i["state"] == STATE_PENDING]
    else:
        selected = [i for i in items if i["state"] != STATE_NOT_APPLICABLE]

    name_key = "name_en" if lang == LANG_EN else "name_ko"
    why_key = "why_needed_en" if lang == LANG_EN else "why_needed_ko"

    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for item in selected:
        grouped.setdefault(item["category"], []).append(item)

    lines: list[str] = []
    if header.strip():
        lines += [header.strip(), ""]
    for category, rows in sorted(grouped.items(), key=lambda kv: category_order.get(kv[0], 999)):
        lines.append(f"[{category_labels.get(category, category)}]")
        for item in rows:
            line = f"- {item[name_key]}"
            if item.get("unit"):
                line += f" ({item['unit']})"
            if item["is_required"]:
                line += f" [{REQUIRED_MARK[lang]}]"
            if item.get(why_key):
                line += f" — {item[why_key]}"
            lines.append(line)
        lines.append("")
    if footer.strip():
        lines.append(footer.strip())
    return "\n".join(lines).strip() + "\n"
