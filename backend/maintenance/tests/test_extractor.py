"""오염 키워드 추출 (specs/10 §3.2, §8). DB 불필요."""

import pytest

from maintenance.services import extractor as ex
from maintenance.services.keywords import DEFAULT_KEYWORDS

KEYWORDS = [ex.Keyword(keyword=k, category=c) for k, c in DEFAULT_KEYWORDS]


def match(title, description=""):
    return ex.match(title, description, KEYWORDS, threshold=1.0)


def test_ac_10_1_chemical_cleaning_title_is_detected():
    """AC-10-1: 'HRSG 전열면 화학세정 시행' 이 세정 후보로 자동 추출된다."""
    result = match("HRSG 전열면 화학세정 시행", "가스측 차압 상승에 따른 화학세정 실시")

    assert result.is_fouling_related
    assert result.category == ex.CATEGORY_CLEANING
    assert any(m["keyword"] == "화학세정" for m in result.matched)


@pytest.mark.parametrize(
    "title",
    [
        "수세 시행",
        "HRSG 드라이아이스 세정",
        "핀 튜브 청소 작업",
        "Soot Blowing 실시",
        "튜브 클리닝",
    ],
)
def test_cleaning_keywords_are_detected(title):
    assert match(title).category == ex.CATEGORY_CLEANING


def test_fouling_symptom_is_classified_separately():
    result = match("가스측 차압 상승 확인", "스케일 퇴적 의심")

    assert result.is_fouling_related
    assert result.category == ex.CATEGORY_FOULING


def test_unrelated_record_is_not_a_candidate():
    result = match("GT 연소기 육안 점검", "정기 점검 결과 이상 없음")

    # '육안 점검' 은 INSPECTION 이라 후보이긴 하지만 세정은 아니다.
    assert result.category == ex.CATEGORY_INSPECTION


def test_completely_unrelated_record_scores_zero():
    result = match("발전기 절연 저항 측정", "기준치 이내")

    assert not result.is_fouling_related
    assert result.score == 0


def test_exclude_keyword_removes_candidate():
    """specs/10 §3.2 — EXCLUDE 키워드가 포함되면 후보에서 제외한다."""
    result = match("HRSG 세정 계획 취소", "예산 사유로 금회 세정 미시행")

    assert not result.is_fouling_related
    assert result.score == 0
    assert "취소" in result.excluded_by


def test_matching_ignores_case_and_spaces():
    assert match("SOOT  BLOWING").is_fouling_related
    assert match("화학 세정").is_fouling_related


def test_score_is_sum_of_weights():
    keywords = [
        ex.Keyword("세정", ex.CATEGORY_CLEANING, weight=2.0),
        ex.Keyword("차압 상승", ex.CATEGORY_FOULING, weight=1.5),
    ]

    result = ex.match("세정 시행", "차압 상승 확인", keywords, threshold=1.0)

    assert result.score == pytest.approx(3.5)


def test_threshold_filters_low_scores():
    keywords = [ex.Keyword("세정", ex.CATEGORY_CLEANING, weight=0.5)]

    assert not ex.match("세정", "", keywords, threshold=1.0).is_fouling_related
    assert ex.match("세정", "", keywords, threshold=0.4).is_fouling_related


def test_cleaning_wins_over_fouling_when_both_match():
    result = match("차압 상승으로 화학세정 시행")

    assert result.category == ex.CATEGORY_CLEANING


def test_empty_input_is_safe():
    assert not match("", "").is_fouling_related
    assert not ex.match(None, None, KEYWORDS).is_fouling_related


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("화학세정 시행", "CHEMICAL"),
        ("드라이아이스 세정", "DRY_ICE"),
        ("수세 실시", "WATER_WASH"),
        ("워터젯 세정", "WATER_WASH"),
        ("전열면 청소", "MECHANICAL"),
        ("세정 시행", "OTHER"),
    ],
)
def test_guess_method(title, expected):
    assert ex.guess_method(title, "") == expected


def test_normalize():
    assert ex.normalize(" 화학 세정 ") == "화학세정"
    assert ex.normalize("SOOT Blowing") == "sootblowing"
    assert ex.normalize(None) == ""
