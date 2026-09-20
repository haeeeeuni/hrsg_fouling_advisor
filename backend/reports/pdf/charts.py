"""리포트용 차트 이미지 생성 (specs/12 §3.1).

모든 텍스트에 동봉 폰트를 **명시적으로** 넘긴다. family 이름에만 의존하면
서버에서 한글이 네모로 나온다.
"""

from __future__ import annotations

import io
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from reports.pdf.fonts import font_properties, register_matplotlib  # noqa: E402

GRADE_BANDS = ((0, 30, "#198754"), (30, 60, "#ffc107"), (60, 100, "#dc3545"))


def _finish(fig) -> bytes:
    buffer = io.BytesIO()
    fig.tight_layout()
    fig.savefig(buffer, format="png", dpi=140)
    plt.close(fig)
    return buffer.getvalue()


def _apply_font(ax, title: str, xlabel: str, ylabel: str) -> None:
    fp = font_properties()
    ax.set_title(title, fontproperties=fp, fontsize=11)
    ax.set_xlabel(xlabel, fontproperties=fp, fontsize=9)
    ax.set_ylabel(ylabel, fontproperties=fp, fontsize=9)
    for label in [*ax.get_xticklabels(), *ax.get_yticklabels()]:
        label.set_fontproperties(fp)
        label.set_fontsize(8)


def fouling_trend(
    points: list[dict[str, Any]],
    threshold: float = 60,
    cleaning_dates: list | None = None,
) -> bytes:
    """FI 시계열 + 등급 배경 + 임계치 라인 + 세정 마커 (specs/12 §3.2 4장)."""
    register_matplotlib()
    fp = font_properties()

    dates = [p["date"] for p in points]
    values = [p.get("fi_value") for p in points]

    fig, ax = plt.subplots(figsize=(9, 3.2))
    for low, high, color in GRADE_BANDS:
        ax.axhspan(low, high, color=color, alpha=0.06)

    ax.plot(dates, values, color="#0d6efd", linewidth=1.6, label="오염도 지수")
    ax.axhline(
        threshold, color="#dc3545", linestyle="--", linewidth=1, label=f"임계치 {threshold:g}"
    )

    for index, cleaned_at in enumerate(cleaning_dates or []):
        ax.axvline(
            cleaned_at,
            color="#198754",
            linestyle=":",
            linewidth=1.2,
            label="세정" if index == 0 else None,
        )

    ax.set_ylim(0, 100)
    _apply_font(ax, "오염도 지수(FI) 시계열", "날짜", "FI")
    ax.legend(prop=fp, fontsize=8, loc="upper left")
    fig.autofmt_xdate()
    return _finish(fig)


def measured_vs_expected(points: list[dict[str, Any]], target: str) -> bytes:
    """실측 vs 기대 오버레이 (specs/12 §3.2 4장)."""
    register_matplotlib()
    fp = font_properties()

    if target == "dp":
        title, unit, measured_key, expected_key = (
            "차압 실측 vs 기대",
            "kPa",
            "measured_dp",
            "expected_dp",
        )
    else:
        title, unit, measured_key, expected_key = (
            "스택온도 실측 vs 기대",
            "°C",
            "measured_st",
            "expected_st",
        )

    dates = [p["date"] for p in points]
    fig, ax = plt.subplots(figsize=(9, 2.6))
    ax.plot(
        dates, [p.get(measured_key) for p in points], color="#0d6efd", linewidth=1.4, label="실측"
    )
    ax.plot(
        dates,
        [p.get(expected_key) for p in points],
        color="#6c757d",
        linestyle="--",
        linewidth=1.2,
        label="기대",
    )
    _apply_font(ax, title, "날짜", unit)
    ax.legend(prop=fp, fontsize=8)
    fig.autofmt_xdate()
    return _finish(fig)


def cluster_bars(clusters: list[dict[str, Any]]) -> bytes:
    """군집별 표본 분포 (specs/12 §3.2 2장)."""
    register_matplotlib()
    fp = font_properties()

    rows = [c for c in clusters if c.get("sample_count")][:12]
    labels = [f"{c['cluster_key']}" for c in rows]
    counts = [c["sample_count"] for c in rows]
    colors = ["#adb5bd" if c.get("is_sparse") else "#0d6efd" for c in rows]

    fig, ax = plt.subplots(figsize=(9, 2.8))
    ax.bar(labels, counts, color=colors)
    _apply_font(ax, "군집별 유효 표본 수", "군집", "표본 수")
    for label in ax.get_xticklabels():
        label.set_fontproperties(fp)
        label.set_rotation(45)
        label.set_ha("right")
    return _finish(fig)


def comparison_bars(cluster_metrics: list[dict[str, Any]], metric_key: str) -> bytes:
    """군집별 전/후 그룹 막대 (specs/12 §2.4)."""
    register_matplotlib()
    fp = font_properties()

    import numpy as np

    labels, before, after = [], [], []
    for row in cluster_metrics:
        metric = next((m for m in row["metrics"] if m["key"] == metric_key), None)
        if not metric or metric["before"] is None or metric["after"] is None:
            continue
        labels.append(row["cluster_key"])
        before.append(metric["before"])
        after.append(metric["after"])

    fig, ax = plt.subplots(figsize=(9, 2.8))
    if labels:
        x = np.arange(len(labels))
        ax.bar(x - 0.2, before, width=0.4, color="#dc3545", label="세정 전")
        ax.bar(x + 0.2, after, width=0.4, color="#198754", label="세정 후")
        ax.set_xticks(x)
        ax.set_xticklabels(labels)
        ax.legend(prop=fp, fontsize=8)

    title = {
        "residual_dp": "군집별 차압 잔차",
        "residual_st": "군집별 스택온도 잔차",
        "fi": "군집별 FI",
    }
    _apply_font(ax, title.get(metric_key, metric_key), "군집", "")
    return _finish(fig)
