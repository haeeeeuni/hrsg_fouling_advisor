"""한글 폰트 등록 (specs/12 §3.1).

**기본 Helvetica 를 쓰면 한글이 전부 깨진다.** ReportLab 과 matplotlib 양쪽에
동봉 폰트를 명시적으로 등록해야 한다(AC-12-1, AC-12-2).

matplotlib 주의: family 이름으로만 지정하면 시스템에 같은 이름의 폰트가 있을 때
그쪽이 선택된다(macOS 는 NanumGothic 을 시스템 에셋으로 제공한다). 시스템 폰트가 없는
리눅스 서버에서는 DejaVu Sans 로 조용히 폴백해 **한글이 전부 네모로 나온다.**
→ 차트 코드는 항상 `font_properties()`(파일 경로 기반)를 명시적으로 넘긴다.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

FONT_DIR = Path(__file__).resolve().parent.parent / "fonts"
REGULAR_PATH = FONT_DIR / "NanumGothic-Regular.ttf"
BOLD_PATH = FONT_DIR / "NanumGothic-Bold.ttf"

FONT_REGULAR = "NanumGothic"
FONT_BOLD = "NanumGothic-Bold"

# 나눔고딕에 없는 글리프 → 있는 글리프로 치환 (없으면 PDF 에서 빈칸/네모가 된다)
GLYPH_SUBSTITUTIONS: tuple[tuple[str, str], ...] = (
    ("℃", "°C"),  # U+2103 없음 / U+00B0 + C 는 있음
    ("℉", "°F"),
    ("−", "-"),  # U+2212 유니코드 마이너스 없음
    ("㎪", "kPa"),
    ("㎥", "m3"),
    ("㎡", "m2"),
)


class FontMissing(RuntimeError):
    """동봉 폰트를 찾을 수 없음 — 한글이 깨지므로 리포트를 만들지 않는다."""


def pdf_safe(text: str) -> str:
    """PDF 에 넣기 전 치환. 엑셀(UTF-8)에는 적용하지 않는다."""
    if not isinstance(text, str):
        return text
    for source, target in GLYPH_SUBSTITUTIONS:
        text = text.replace(source, target)
    return text


@lru_cache(maxsize=1)
def register_reportlab() -> str:
    """ReportLab 에 나눔고딕을 등록하고 본문 폰트명을 돌려준다."""
    from reportlab.lib.fonts import addMapping
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    if not REGULAR_PATH.exists() or not BOLD_PATH.exists():
        raise FontMissing(
            f"한글 폰트를 찾을 수 없습니다: {FONT_DIR}. "
            "reports/fonts/README.md 를 참고해 NanumGothic 을 배치하세요."
        )

    pdfmetrics.registerFont(TTFont(FONT_REGULAR, str(REGULAR_PATH)))
    pdfmetrics.registerFont(TTFont(FONT_BOLD, str(BOLD_PATH)))
    pdfmetrics.registerFontFamily(
        FONT_REGULAR,
        normal=FONT_REGULAR,
        bold=FONT_BOLD,
        italic=FONT_REGULAR,
        boldItalic=FONT_BOLD,
    )
    addMapping(FONT_REGULAR, 0, 0, FONT_REGULAR)
    addMapping(FONT_REGULAR, 1, 0, FONT_BOLD)
    logger.info("registered korean font for reportlab")
    return FONT_REGULAR


@lru_cache(maxsize=1)
def font_properties():
    """동봉 폰트 파일을 직접 가리키는 FontProperties.

    차트의 모든 텍스트(제목·축·범례·눈금)에 이걸 넘겨야 서버에서도 한글이 나온다.
    """
    from matplotlib import font_manager

    if not REGULAR_PATH.exists():
        raise FontMissing(f"한글 폰트를 찾을 수 없습니다: {REGULAR_PATH}")
    return font_manager.FontProperties(fname=str(REGULAR_PATH))


@lru_cache(maxsize=1)
def register_matplotlib() -> str:
    """matplotlib 전역 기본값도 동봉 폰트로 맞춘다 (AC-12-2).

    family 해석이 시스템 폰트로 새는지 확인해 경고를 남긴다.
    """
    import matplotlib
    from matplotlib import font_manager

    font_manager.fontManager.addfont(str(REGULAR_PATH))
    if BOLD_PATH.exists():
        font_manager.fontManager.addfont(str(BOLD_PATH))

    family = font_properties().get_name()
    matplotlib.rcParams["font.family"] = family
    # 한글 폰트에는 유니코드 마이너스가 없어 음수 부호가 네모로 나온다.
    matplotlib.rcParams["axes.unicode_minus"] = False

    resolved = font_manager.findfont(font_manager.FontProperties(family=family))
    if Path(resolved) != REGULAR_PATH:
        logger.warning(
            "matplotlib font family '%s' resolves to %s, not the bundled font. "
            "차트 코드는 font_properties() 를 명시적으로 사용해야 한다.",
            family,
            resolved,
        )
    return family
