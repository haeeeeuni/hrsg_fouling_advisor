"""PDF 스타일 — 모든 스타일에 등록 폰트를 지정한다 (specs/12 §3.1)."""

from __future__ import annotations

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm

from reports.pdf.fonts import FONT_BOLD, FONT_REGULAR

PAGE_MARGIN = 18 * mm

GRADE_COLORS = {
    "NORMAL": colors.HexColor("#198754"),
    "CAUTION": colors.HexColor("#ffc107"),
    "WARNING": colors.HexColor("#dc3545"),
}


def build_styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    styles = {
        "title": ParagraphStyle(
            "title",
            parent=base["Title"],
            fontName=FONT_BOLD,
            fontSize=22,
            leading=30,
            alignment=TA_CENTER,
        ),
        "subtitle": ParagraphStyle(
            "subtitle",
            parent=base["Normal"],
            fontName=FONT_REGULAR,
            fontSize=12,
            leading=18,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#6c757d"),
        ),
        "h1": ParagraphStyle(
            "h1",
            parent=base["Heading1"],
            fontName=FONT_BOLD,
            fontSize=15,
            leading=22,
            spaceBefore=10,
            spaceAfter=6,
        ),
        "h2": ParagraphStyle(
            "h2",
            parent=base["Heading2"],
            fontName=FONT_BOLD,
            fontSize=12,
            leading=18,
            spaceBefore=8,
            spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "body",
            parent=base["Normal"],
            fontName=FONT_REGULAR,
            fontSize=9.5,
            leading=15,
        ),
        "small": ParagraphStyle(
            "small",
            parent=base["Normal"],
            fontName=FONT_REGULAR,
            fontSize=8,
            leading=12,
            textColor=colors.HexColor("#6c757d"),
        ),
        "cell": ParagraphStyle(
            "cell",
            parent=base["Normal"],
            fontName=FONT_REGULAR,
            fontSize=8.5,
            leading=12,
        ),
    }
    return styles


def table_style(header_rows: int = 1):
    from reportlab.platypus import TableStyle

    return TableStyle(
        [
            ("FONTNAME", (0, 0), (-1, -1), FONT_REGULAR),
            ("FONTNAME", (0, 0), (-1, header_rows - 1), FONT_BOLD),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("BACKGROUND", (0, 0), (-1, header_rows - 1), colors.HexColor("#f1f3f5")),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#dee2e6")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (1, header_rows), (-1, -1), "RIGHT"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]
    )
