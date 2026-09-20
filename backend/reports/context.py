"""리포트 컨텍스트 조립 (specs/12 §3.2, §4.2).

PDF·엑셀 빌더가 쓰는 dict 를 DB 모델에서 만든다.
빌더는 Django 를 모르고, 여기가 유일한 연결점이다.
"""

from __future__ import annotations

from typing import Any

from django.utils import timezone

from analysis.models import AnalysisRun, ComparisonReport, FoulingIndexPoint
from analysis.serializers import (
    BenefitResultSerializer,
    FoulingIndexPointSerializer,
    ModelVersionSerializer,
    TrendForecastSerializer,
)
from maintenance.models import CleaningEvent
from reports import formatting as fmt

REPORT_TITLE = "HRSG 가스측 오염도 진단 리포트"
COMPARISON_TITLE = "세정 전후 비교 리포트"


def _conclusion(run: AnalysisRun, trend: dict, benefit: dict) -> str:
    """결론 문장은 템플릿 기반으로 만들되 수치는 실제 결과를 쓴다 (specs/12 §3.3)."""
    parts = [
        f"{run.unit.name}의 현재 오염도 지수는 {fmt.fi(run.result_fi)}"
        f"({fmt.grade(run.result_grade)})입니다."
    ]

    status = trend.get("status")
    if status == "ALREADY_EXCEEDED":
        parts.append(
            f"임계치 {fmt.fi(trend.get('threshold_used'))}를 이미 초과했습니다"
            f"({trend.get('exceeded_days') or 0}일째)."
        )
    elif status == "OK" and trend.get("eta_date"):
        parts.append(
            f"현재 추세라면 {fmt.ymd(trend['eta_date'])}"
            f"({fmt.dday(trend.get('eta_days'))})에 임계치에 도달할 것으로 예상됩니다."
        )
    else:
        parts.append("추세가 확인되지 않아 도달 시점을 예측할 수 없습니다.")

    net = benefit.get("net_benefit")
    if net is not None:
        payback = benefit.get("payback_days")
        payback_text = f", 회수기간은 {round(payback)}일" if payback else ""
        parts.append(
            f"현재 조건에서 세정 시 순편익은 약 {fmt.currency(net)}{payback_text}로 추정됩니다."
        )
    return " ".join(parts)


def _assumption_note(benefit: dict) -> str:
    params = benefit.get("params_snapshot") or {}
    return (
        "가정 — 전력단가 {price}원/kWh, 배압 손실계수 {dp}%MW/kPa, "
        "스택온도 손실계수 {st}%MW/℃, 세정 후 회복률 {recovery}, 평가기간 {horizon}일. "
        "모든 편익 수치는 계수 기반 추정치이며, 실적 데이터로 계수를 보정해야 합니다."
    ).format(
        price=params.get("electricity_price", fmt.EMPTY),
        dp=params.get("dp_power_loss_coeff", fmt.EMPTY),
        st=params.get("stack_temp_loss_coeff", fmt.EMPTY),
        recovery=params.get("cleaning_recovery_ratio", fmt.EMPTY),
        horizon=params.get("evaluation_horizon_days", fmt.EMPTY),
    )


def build_analysis_context(run: AnalysisRun) -> dict[str, Any]:
    trend = TrendForecastSerializer(run.trend).data if hasattr(run, "trend") else {}
    benefit = BenefitResultSerializer(run.benefit).data if hasattr(run, "benefit") else {}

    points = FoulingIndexPointSerializer(
        FoulingIndexPoint.objects.filter(analysis_run=run, cluster_key="").order_by("date"),
        many=True,
    ).data

    cleaning_dates = list(
        CleaningEvent.objects.filter(
            unit=run.unit, cleaned_at__gte=run.period_start, cleaned_at__lte=run.period_end
        )
        .order_by("cleaned_at")
        .values_list("cleaned_at", flat=True)
    )

    return {
        "report_title": REPORT_TITLE,
        "unit_name": f"{run.unit.code} {run.unit.name}",
        "plant_name": run.unit.plant_name,
        "period_start": fmt.ymd(run.period_start),
        "period_end": fmt.ymd(run.period_end),
        "executed_by": run.executed_by.full_name if run.executed_by else fmt.EMPTY,
        "executed_at": fmt.ymd_hm(run.executed_at),
        "generated_at": fmt.ymd_hm(timezone.now()),
        "current_fi": run.result_fi,
        "grade": run.result_grade,
        "confidence": run.result_confidence,
        "eta_days": trend.get("eta_days"),
        "trend_status": trend.get("status"),
        "net_benefit": benefit.get("net_benefit"),
        "threshold": (run.settings_snapshot or {}).get("fouling_threshold", 60),
        "data_stats": run.data_stats or {},
        "clusters": (run.data_stats or {}).get("cluster_summary", []),
        "settings_snapshot": run.settings_snapshot or {},
        "model_dp": (
            ModelVersionSerializer(run.model_version_dp).data if run.model_version_dp else None
        ),
        "model_st": (
            ModelVersionSerializer(run.model_version_st).data if run.model_version_st else None
        ),
        "fouling_points": points,
        "cleaning_dates": [timezone.localtime(d).date() for d in cleaning_dates],
        "trend": trend,
        "benefit": benefit,
        "warnings": [w.get("message", "") for w in (run.warnings or [])],
        "conclusion": _conclusion(run, trend, benefit),
        "assumption_note": _assumption_note(benefit),
    }


def build_comparison_context(report: ComparisonReport) -> dict[str, Any]:
    """비교 리포트 컨텍스트. 분석 리포트와 같은 뼈대를 쓰되 7장만 채운다."""
    event = report.cleaning_event
    return {
        "report_title": COMPARISON_TITLE,
        "unit_name": f"{report.unit.code} {report.unit.name}",
        "plant_name": report.unit.plant_name,
        "period_start": fmt.ymd(report.before_start),
        "period_end": fmt.ymd(report.after_end),
        "executed_by": report.created_by.full_name if report.created_by else fmt.EMPTY,
        "executed_at": fmt.ymd_hm(report.created_at),
        "generated_at": fmt.ymd_hm(timezone.now()),
        "current_fi": None,
        "grade": "",
        "data_stats": {},
        "clusters": [],
        "settings_snapshot": {},
        "fouling_points": [],
        "trend": {},
        "benefit": {},
        "warnings": [w.get("message", "") for w in (report.warnings or [])],
        "conclusion": (
            f"{fmt.ymd(event.cleaned_at)} {event.get_method_display()} 세정 전후를 "
            f"공통 군집 {', '.join(report.common_clusters)} 에서 비교했습니다. "
            f"회복률은 {fmt.percent((report.recovery_ratio or 0) * 100)} 입니다."
        ),
        "assumption_note": (
            "잔차 기반 지표가 주 지표입니다(운전 조건 차이를 보정). "
            "원시 평균 비교는 참고 지표입니다."
        ),
        "comparison": {
            "before_start": fmt.ymd(report.before_start),
            "before_end": fmt.ymd(report.before_end),
            "after_start": fmt.ymd(report.after_start),
            "after_end": fmt.ymd(report.after_end),
            "common_clusters": report.common_clusters,
            "metrics": report.metrics,
            "cluster_metrics": report.cluster_metrics,
            "p_values": report.p_values,
            "recovery_ratio": report.recovery_ratio,
        },
    }
