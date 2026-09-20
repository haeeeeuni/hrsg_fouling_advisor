"""분석 리포트 PDF 생성 (specs/12 §3).

구성: 표지 / 1.요약 / 2.데이터 개요 / 3.예측 모델 / 4.오염도 분석 /
      5.추세·도달 예측 / 6.편익 분석 / 7.세정 전후 비교(해당 시) / 부록

모든 문자열은 `pdf_safe()` 를 거쳐 나눔고딕에 없는 글리프를 치환한다.
"""

from __future__ import annotations

import io
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
)

from reports import formatting as fmt
from reports.pdf import charts
from reports.pdf.fonts import FONT_REGULAR, pdf_safe, register_reportlab
from reports.pdf.styles import PAGE_MARGIN, build_styles, table_style

CONTENT_WIDTH = A4[0] - PAGE_MARGIN * 2


def _range(start, end) -> str:
    return f"{fmt.ymd(start)} ~ {fmt.ymd(end)}"


class PdfReportBuilder:
    def __init__(self, context: dict[str, Any]) -> None:
        register_reportlab()
        self.ctx = context
        self.styles = build_styles()
        self.story: list[Any] = []

    # --- 공통 헬퍼 ---

    def p(self, text: str, style: str = "body") -> Paragraph:
        return Paragraph(pdf_safe(str(text)), self.styles[style])

    def heading(self, text: str, level: str = "h1") -> None:
        self.story.append(self.p(text, level))

    def table(self, rows: list[list[Any]], widths: list[float] | None = None) -> None:
        data = [[self.p(cell, "cell") for cell in row] for row in rows]
        table = Table(data, colWidths=widths or self._even_widths(len(rows[0])))
        table.setStyle(table_style())
        self.story.append(table)
        self.story.append(Spacer(1, 6))

    def kv_table(self, pairs: list[tuple[str, Any]]) -> None:
        self.table(
            [["항목", "값"], *[[k, v] for k, v in pairs]],
            [CONTENT_WIDTH * 0.42, CONTENT_WIDTH * 0.58],
        )

    def chart(self, png: bytes, height_mm: float = 55) -> None:
        self.story.append(Image(io.BytesIO(png), width=CONTENT_WIDTH, height=height_mm * mm))
        self.story.append(Spacer(1, 8))

    @staticmethod
    def _even_widths(columns: int) -> list[float]:
        return [CONTENT_WIDTH / columns] * columns

    # --- 페이지 장식 (specs/12 §3.3) ---

    def _decorate(self, canvas, doc) -> None:
        canvas.saveState()
        canvas.setFont(FONT_REGULAR, 8)
        canvas.setFillColor(colors.HexColor("#6c757d"))
        header = f"{self.ctx['unit_name']} · {self.ctx['report_title']}"
        canvas.drawString(PAGE_MARGIN, A4[1] - 12 * mm, pdf_safe(header))
        footer = f"{doc.page} / {self.ctx.get('total_pages', '')}".strip(" /")
        canvas.drawCentredString(A4[0] / 2, 10 * mm, footer)
        canvas.drawRightString(
            A4[0] - PAGE_MARGIN, 10 * mm, pdf_safe(f"생성 {self.ctx['generated_at']}")
        )
        canvas.restoreState()

    # --- 섹션 ---

    def cover(self) -> None:
        ctx = self.ctx
        self.story.append(Spacer(1, 60 * mm))
        self.story.append(self.p(ctx["report_title"], "title"))
        self.story.append(Spacer(1, 8))
        self.story.append(self.p(ctx["unit_name"], "subtitle"))
        self.story.append(Spacer(1, 20 * mm))
        self.kv_table(
            [
                ("분석 기간", f"{ctx['period_start']} ~ {ctx['period_end']}"),
                ("실행자", ctx["executed_by"]),
                ("분석 일시", ctx["executed_at"]),
                ("생성 일시", ctx["generated_at"]),
                ("발전소 / 부서", ctx.get("plant_name") or fmt.EMPTY),
            ]
        )
        self.story.append(PageBreak())

    def summary(self) -> None:
        ctx = self.ctx
        self.heading("1. 요약")
        self.table(
            [
                ["현재 오염도 지수", "등급", "임계 도달 D-day", "예상 순편익"],
                [
                    fmt.fi(ctx["current_fi"]),
                    fmt.grade(ctx["grade"]),
                    fmt.dday(ctx.get("eta_days"), ctx.get("trend_status")),
                    fmt.currency(ctx.get("net_benefit")),
                ],
            ]
        )
        self.story.append(self.p(f"<b>결론</b> — {ctx['conclusion']}"))
        self.story.append(Spacer(1, 4))
        self.story.append(self.p(ctx["assumption_note"], "small"))
        if ctx.get("warnings"):
            self.heading("주의 사항", "h2")
            for warning in ctx["warnings"]:
                self.story.append(self.p(f"• {warning}", "small"))
        self.story.append(PageBreak())

    def data_overview(self) -> None:
        stats = self.ctx["data_stats"]
        self.heading("2. 데이터 개요")
        self.kv_table(
            [
                ("데이터 기간", f"{self.ctx['period_start']} ~ {self.ctx['period_end']}"),
                ("총 데이터 포인트", fmt.count(stats.get("row_total"))),
                (
                    "유효 포인트",
                    f"{fmt.count(stats.get('row_valid'))} "
                    f"({fmt.percent((stats.get('valid_ratio') or 0) * 100)})",
                ),
                ("유효 세그먼트 수", f"{fmt.count(stats.get('segment_count'))}개"),
                ("청정 기준 포인트", fmt.count(stats.get("baseline_points"))),
                ("도메인 밖 비율", fmt.percent((stats.get("out_of_domain_ratio") or 0) * 100)),
            ]
        )
        excluded = stats.get("excluded_by_reason") or {}
        if excluded:
            self.heading("제외 사유별 건수", "h2")
            self.table([["사유", "건수"], *[[k, fmt.count(v)] for k, v in excluded.items()]])
        if self.ctx.get("clusters"):
            self.heading("군집 분포", "h2")
            self.chart(charts.cluster_bars(self.ctx["clusters"]), 40)
            self.table(
                [
                    ["군집", "라벨", "표본 수", "비중", "평균 부하율"],
                    *[
                        [
                            c["cluster_key"],
                            c.get("label", ""),
                            fmt.count(c.get("sample_count")),
                            fmt.percent(c.get("share_pct")),
                            fmt.percent(c.get("avg_load_ratio_pct")),
                        ]
                        for c in self.ctx["clusters"][:12]
                    ],
                ]
            )
        self.story.append(PageBreak())

    def models(self) -> None:
        self.heading("3. 예측 모델")
        rows = [["구분", "알고리즘", "버전", "학습 기간", "학습 표본", "MAE", "RMSE", "R²"]]
        for label, model in (
            ("차압", self.ctx.get("model_dp")),
            ("스택온도", self.ctx.get("model_st")),
        ):
            if not model:
                continue
            metrics = model.get("metrics") or {}
            rows.append(
                [
                    label,
                    model.get("algorithm", fmt.EMPTY),
                    f"v{model.get('version', '')}",
                    f"{fmt.ymd(model.get('baseline_start'))}~{fmt.ymd(model.get('baseline_end'))}",
                    fmt.count(model.get("training_rows")),
                    f"{metrics.get('mae', float('nan')):.3f}",
                    f"{metrics.get('rmse', float('nan')):.3f}",
                    f"{metrics.get('r2', float('nan')):.3f}",
                ]
            )
        self.table(rows)
        self.story.append(
            self.p(
                "기대값 모델은 세정 직후 '청정 기준 기간' 으로만 학습한다. "
                "실측값과의 차이(잔차)가 오염의 직접 신호가 된다.",
                "small",
            )
        )
        self.story.append(PageBreak())

    def fouling(self) -> None:
        self.heading("4. 오염도 분석")
        points = self.ctx.get("fouling_points") or []
        if points:
            self.chart(
                charts.fouling_trend(
                    points, self.ctx.get("threshold", 60), self.ctx.get("cleaning_dates")
                )
            )
            self.chart(charts.measured_vs_expected(points, "dp"), 42)
            self.chart(charts.measured_vs_expected(points, "st"), 42)
        self.story.append(PageBreak())

    def trend(self) -> None:
        trend = self.ctx.get("trend")
        self.heading("5. 추세 및 도달 예측")
        if not trend:
            self.story.append(self.p("추세 예측 결과가 없습니다."))
            self.story.append(PageBreak())
            return

        self.kv_table(
            [
                ("추세 모델", trend.get("model_type") or fmt.EMPTY),
                ("상태", fmt.trend_status(trend.get("status"))),
                ("진행률", f"{(trend.get('slope_per_day') or 0):.4f} FI/일"),
                ("주간 증가량", f"{(trend.get('weekly_increase') or 0):.2f} FI/주"),
                (
                    "적합 구간",
                    f"{fmt.ymd(trend.get('fit_start'))} ~ {fmt.ymd(trend.get('fit_end'))}",
                ),
                ("적합도", f"R² {(trend.get('r2') or float('nan')):.3f}"),
                ("임계 도달 예상일", fmt.ymd(trend.get("eta_date"))),
                ("신뢰구간", _range(trend.get("eta_lower_date"), trend.get("eta_upper_date"))),
                ("주의(30) 전환 예상일", fmt.ymd(trend.get("caution_eta_date"))),
                ("경고(60) 전환 예상일", fmt.ymd(trend.get("warning_eta_date"))),
                ("마지막 세정 이후", f"{trend.get('days_since_cleaning') or fmt.EMPTY}일"),
            ]
        )
        if trend.get("uncertain"):
            self.story.append(self.p("신뢰구간이 넓어 불확실성이 높습니다.", "small"))
        self.story.append(PageBreak())

    def benefit(self) -> None:
        benefit = self.ctx.get("benefit")
        self.heading("6. 편익 분석")
        if not benefit:
            self.story.append(self.p("편익 결과가 없습니다."))
            self.story.append(PageBreak())
            return

        self.kv_table(
            [
                (
                    "현재 손실 출력",
                    f"{fmt.power(benefit.get('power_loss_total_mw'))} "
                    f"(GT {fmt.power(benefit.get('power_loss_gt_mw'))} / "
                    f"ST {fmt.power(benefit.get('power_loss_st_mw'))})",
                ),
                ("일일 손실 비용", fmt.currency(benefit.get("daily_loss_cost"), False)),
                ("일일 연료 손실", fmt.currency(benefit.get("daily_fuel_loss"), False)),
                ("세정 비용", fmt.currency(benefit.get("cleaning_cost"))),
                ("정지 손실", fmt.currency(benefit.get("outage_loss"))),
                ("총 세정 비용", fmt.currency(benefit.get("total_cleaning_cost"))),
                ("회수 편익(평가기간)", fmt.currency(benefit.get("gross_benefit"))),
                ("순편익", fmt.currency(benefit.get("net_benefit"))),
                (
                    "회수기간",
                    (
                        f"{round(benefit['payback_days'])}일"
                        if benefit.get("payback_days")
                        else fmt.EMPTY
                    ),
                ),
                ("지연 비용", f"{fmt.currency(benefit.get('daily_loss_cost'), False)}/일"),
                ("권고 세정 시점", fmt.ymd(benefit.get("recommended_cleaning_date"))),
            ]
        )

        if benefit.get("scenarios"):
            self.heading("시나리오 비교", "h2")
            self.table(
                [
                    ["시나리오", "시점", "순편익"],
                    *[
                        [
                            row["label"],
                            (
                                f"D+{row['offset_days']}"
                                if row.get("offset_days") is not None
                                else fmt.EMPTY
                            ),
                            fmt.currency(row.get("net_benefit")),
                        ]
                        for row in benefit["scenarios"]
                    ],
                ]
            )

        if benefit.get("sensitivity"):
            self.heading("민감도 (±30%)", "h2")
            self.table(
                [
                    ["파라미터", "−30%", "+30%", "변동폭"],
                    *[
                        [
                            row["param"],
                            fmt.currency(row.get("net_benefit_low")),
                            fmt.currency(row.get("net_benefit_high")),
                            fmt.currency(row.get("swing")),
                        ]
                        for row in benefit["sensitivity"]
                    ],
                ]
            )

        self.story.append(self.p(self.ctx["assumption_note"], "small"))
        self.story.append(PageBreak())

    def comparison(self) -> None:
        comparison = self.ctx.get("comparison")
        if not comparison:
            return
        self.heading("7. 세정 전후 비교")
        self.story.append(
            self.p(
                f"비교 구간 — 세정 전 {comparison['before_start']} ~ {comparison['before_end']} / "
                f"세정 후 {comparison['after_start']} ~ {comparison['after_end']}",
                "small",
            )
        )
        self.story.append(
            self.p(
                f"공통 군집 {', '.join(comparison['common_clusters'])} "
                "— 같은 운전 조건끼리만 비교합니다.",
                "small",
            )
        )
        rows = [["지표", "세정 전", "세정 후", "개선량", "개선율"]]
        for metric in comparison["metrics"]["rows"]:
            rows.append(
                [
                    metric["label"] + (" *" if metric["is_primary"] else ""),
                    str(metric["before"]) if metric["before"] is not None else fmt.EMPTY,
                    str(metric["after"]) if metric["after"] is not None else fmt.EMPTY,
                    str(metric["delta"]) if metric["delta"] is not None else fmt.EMPTY,
                    (
                        f"{metric['delta_pct']:+.1f}%"
                        if metric["delta_pct"] is not None
                        else fmt.EMPTY
                    ),
                ]
            )
        self.table(rows)
        self.story.append(
            self.p("* 잔차 기반 지표가 주 지표입니다(운전 조건 차이를 보정).", "small")
        )
        if comparison.get("cluster_metrics"):
            self.chart(charts.comparison_bars(comparison["cluster_metrics"], "residual_dp"), 40)
        self.story.append(PageBreak())

    def appendix(self) -> None:
        self.heading("부록 A. 적용 설정값")
        snapshot = self.ctx.get("settings_snapshot") or {}
        rows = [["키", "값"], *[[k, str(v)] for k, v in sorted(snapshot.items())]]
        self.table(rows, [CONTENT_WIDTH * 0.45, CONTENT_WIDTH * 0.55])

        self.heading("부록 B. 용어", "h1")
        self.table(
            [
                ["용어", "설명"],
                ["오염도 지수 (FI)", "실측과 기대값의 편차를 0~100으로 환산한 지수"],
                ["잔차", "실측값 − 기대값. 오염의 직접 신호"],
                ["청정 기준 기간", "세정 직후 오염이 없다고 보는 구간. 기대값 모델 학습 구간"],
                ["D-day", "FI 추세가 임계치에 도달할 것으로 예측되는 날까지 남은 일수"],
                ["군집", "부하대 × 계절. 같은 조건끼리 비교하기 위한 구분"],
            ],
            [CONTENT_WIDTH * 0.28, CONTENT_WIDTH * 0.72],
        )

    # --- 실행 ---

    def build(self) -> bytes:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=PAGE_MARGIN,
            rightMargin=PAGE_MARGIN,
            topMargin=PAGE_MARGIN + 6 * mm,
            bottomMargin=PAGE_MARGIN,
            title=pdf_safe(self.ctx["report_title"]),
            author="HRSG Fouling Advisor",
        )
        self.cover()
        self.summary()
        self.data_overview()
        self.models()
        self.fouling()
        self.trend()
        self.benefit()
        self.comparison()
        self.appendix()
        doc.build(self.story, onFirstPage=self._decorate, onLaterPages=self._decorate)
        return buffer.getvalue()


def build_analysis_pdf(context: dict[str, Any]) -> bytes:
    return PdfReportBuilder(context).build()
