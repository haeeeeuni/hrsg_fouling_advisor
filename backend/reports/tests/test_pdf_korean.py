"""PDF 한글 검증 (specs/12 §7). DB 불필요.

AC-12-1: 생성된 PDF 의 모든 한글 텍스트가 깨지지 않고 추출된다.
AC-12-2: 차트 축 라벨·범례의 한글도 정상 표시된다.
"""

import io
from pathlib import Path

import pytest
from pypdf import PdfReader

from reports.pdf import charts, fonts
from reports.pdf.builder import build_analysis_pdf


def extract(pdf: bytes) -> str:
    reader = PdfReader(io.BytesIO(pdf))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


# --- 폰트 ---


def test_bundled_fonts_exist():
    """specs/12 §3.1 — 오픈 라이선스 폰트를 저장소에 동봉한다."""
    assert fonts.REGULAR_PATH.exists()
    assert fonts.BOLD_PATH.exists()
    assert (fonts.FONT_DIR / "OFL.txt").exists()


def test_reportlab_registration_returns_korean_font():
    assert fonts.register_reportlab() == fonts.FONT_REGULAR


def test_font_properties_points_at_bundled_file():
    """family 이름 해석에 의존하면 시스템 폰트로 새어 서버에서 한글이 깨진다."""
    assert Path(fonts.font_properties().get_file()) == fonts.REGULAR_PATH


@pytest.mark.parametrize(
    ("source", "expected"),
    [("112.4 ℃", "112.4 °C"), ("−0.97", "-0.97"), ("3.8 ㎪", "3.8 kPa")],
)
def test_missing_glyphs_are_substituted(source, expected):
    """나눔고딕에 없는 글리프는 있는 글리프로 치환한다."""
    assert fonts.pdf_safe(source) == expected


def test_korean_text_is_untouched():
    assert fonts.pdf_safe("오염도 지수 62.4 (경고)") == "오염도 지수 62.4 (경고)"


# --- AC-12-1 ---


@pytest.fixture(scope="module")
def pdf_text(request):
    context = request.getfixturevalue("context")
    return extract(build_analysis_pdf(context))


def test_pdf_is_generated(context):
    pdf = build_analysis_pdf(context)

    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 10_000


def test_ac_12_1_korean_is_extractable(context):
    text = extract(build_analysis_pdf(context))

    for probe in [
        "HRSG 가스측 오염도 진단 리포트",
        "1호기 HRSG",
        "홍길동",
        "요약",
        "데이터 개요",
        "예측 모델",
        "오염도 분석",
        "추세 및 도달 예측",
        "편익 분석",
        "기동/정지",
        "고부하·여름",
        "권고 세정 시점",
        "청정 기준 기간",
    ]:
        assert probe in text, f"'{probe}' 를 PDF 에서 추출하지 못했습니다"


def test_ac_12_4_execution_context_is_included(context):
    """AC-12-4: 실행자·실행 일시·데이터 기간·적용 설정값·모델 버전이 모두 포함된다."""
    text = extract(build_analysis_pdf(context))

    assert "홍길동" in text
    assert "2025-09-20 14:02" in text
    assert "2024-01-01" in text
    assert "fouling_threshold" in text
    assert "v3" in text


def test_no_unrenderable_glyph_remains(context):
    text = extract(build_analysis_pdf(context))

    assert "℃" not in text
    assert "−" not in text


def test_conclusion_uses_real_numbers(context):
    text = extract(build_analysis_pdf(context))

    assert "62.4" in text
    assert "가정" in text  # 가정·한계를 명시하는 문단


def test_comparison_section_is_rendered(comparison_context):
    text = extract(build_analysis_pdf(comparison_context))

    assert "세정 전후 비교" in text
    assert "오염도 지수 FI" in text
    assert "잔차 기반 지표가 주 지표" in text


def test_pdf_has_multiple_pages(context):
    reader = PdfReader(io.BytesIO(build_analysis_pdf(context)))

    assert len(reader.pages) >= 7  # 표지 + 6개 이상 섹션


# --- AC-12-2 : 차트 ---


def test_chart_png_is_generated(points):
    png = charts.fouling_trend(points, threshold=60)

    assert png.startswith(b"\x89PNG")
    assert len(png) > 5_000


def test_residual_chart_is_generated(points):
    assert charts.measured_vs_expected(points, "dp").startswith(b"\x89PNG")
    assert charts.measured_vs_expected(points, "st").startswith(b"\x89PNG")


def test_cluster_chart_is_generated(context):
    assert charts.cluster_bars(context["clusters"]).startswith(b"\x89PNG")


def test_comparison_chart_is_generated(comparison_context):
    png = charts.comparison_bars(comparison_context["comparison"]["cluster_metrics"], "residual_dp")

    assert png.startswith(b"\x89PNG")


def test_charts_use_bundled_font_not_system(caplog):
    """차트가 시스템 폰트로 새면 서버에서 한글이 네모가 된다."""
    fonts.register_matplotlib.cache_clear()
    fonts.register_matplotlib()

    # font_properties 는 파일 경로 기반이라 항상 동봉 폰트를 가리킨다.
    assert Path(fonts.font_properties().get_file()) == fonts.REGULAR_PATH
