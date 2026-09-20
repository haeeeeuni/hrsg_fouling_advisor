"""정비 이력에서 오염 관련 이력 자동 추출 (specs/10 §3.2).

순수 함수 모듈 — Django 모델을 import 하지 않는다.

추출 결과는 **후보**일 뿐이다. 승인 전에는 CleaningEvent 로 등록되지 않는다(AC-10-2).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

CATEGORY_CLEANING = "CLEANING"
CATEGORY_FOULING = "FOULING"
CATEGORY_INSPECTION = "INSPECTION"
CATEGORY_EXCLUDE = "EXCLUDE"

_SPACES = re.compile(r"\s+")


@dataclass(frozen=True)
class Keyword:
    keyword: str
    category: str
    weight: float = 1.0


@dataclass
class MatchResult:
    is_fouling_related: bool
    score: float
    category: str
    matched: list[dict] = field(default_factory=list)
    excluded_by: list[str] = field(default_factory=list)


def normalize(text: str | None) -> str:
    """대소문자 무시 + 공백 제거 후 비교한다 (specs/10 §3.2)."""
    if not text:
        return ""
    return _SPACES.sub("", str(text)).lower()


def match(
    title: str | None,
    description: str | None,
    keywords: list[Keyword],
    threshold: float = 1.0,
) -> MatchResult:
    """제목 + 내용에서 활성 키워드를 찾아 매칭 점수를 낸다.

    1) EXCLUDE 키워드가 포함되면 후보에서 제외한다.
    2) 매칭 점수 = Σ(매칭 키워드 weight)
    3) 점수 ≥ threshold 면 후보.
    4) CLEANING 매칭은 세정 이벤트 후보, FOULING 매칭은 오염 징후 이력.
    """
    haystack = normalize(title) + normalize(description)

    excluded_by = [
        k.keyword
        for k in keywords
        if k.category == CATEGORY_EXCLUDE and normalize(k.keyword) in haystack
    ]
    if excluded_by:
        return MatchResult(False, 0.0, "", [], excluded_by)

    matched: list[dict] = []
    score = 0.0
    for keyword in keywords:
        if keyword.category == CATEGORY_EXCLUDE:
            continue
        if normalize(keyword.keyword) and normalize(keyword.keyword) in haystack:
            matched.append(
                {"keyword": keyword.keyword, "category": keyword.category, "weight": keyword.weight}
            )
            score += keyword.weight

    if not matched or score < threshold:
        return MatchResult(False, score, "", matched, [])

    # 세정 > 오염 징후 > 점검 순으로 분류를 결정한다.
    categories = {m["category"] for m in matched}
    for candidate in (CATEGORY_CLEANING, CATEGORY_FOULING, CATEGORY_INSPECTION):
        if candidate in categories:
            return MatchResult(True, score, candidate, matched, [])
    return MatchResult(True, score, "", matched, [])


def guess_method(title: str | None, description: str | None) -> str:
    """세정 방법을 문구에서 추정한다. 실패하면 OTHER."""
    haystack = normalize(title) + normalize(description)
    for token, method in (
        ("화학세정", "CHEMICAL"),
        ("드라이아이스", "DRY_ICE"),
        ("워터젯", "WATER_WASH"),
        ("수세", "WATER_WASH"),
        ("sootblowing", "SOOT_BLOWING"),
        ("건식세정", "MECHANICAL"),
        ("청소", "MECHANICAL"),
    ):
        if token in haystack:
            return method
    return "OTHER"
