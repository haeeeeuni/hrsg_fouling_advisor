"""옵션 기능 태스크 — 자동 재계산·백테스트 (specs/19 §1, §2).

`pipeline.run_analysis` 를 그대로 재사용하는 **얇은 조립층**이다(AGENTS.md §3).
분석 로직은 여기에 두지 않는다.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from analysis.models import (
    AnalysisRun,
    AutoRecalcConfig,
    AutoRecalcPeriodMode,
    BacktestResult,
    FoulingIndexPoint,
    Notification,
    NotificationLevel,
    RunStatus,
)
from analysis.pipeline import PipelineContext, PipelineError, build_config, run_analysis
from analysis.services import backtest as bt
from analysis.services.fouling_index import GRADE_CAUTION, GRADE_NORMAL, GRADE_WARNING
from ingestion.models import Measurement
from maintenance.models import CleaningEvent
from units.models import Unit
from units.settings_resolver import get_effective_settings

logger = logging.getLogger(__name__)

# 낮을수록 양호. 등급이 올라갔을 때만 알린다 (specs/19 §1.4).
GRADE_ORDER = {GRADE_NORMAL: 0, GRADE_CAUTION: 1, GRADE_WARNING: 2}


# ---------------------------------------------------------------- 자동 재계산


def resolve_period(config: AutoRecalcConfig, base: AnalysisRun, latest_end) -> tuple:
    """재계산 대상 기간 (specs/19 §1.3).

    ROLLING: 최신 데이터 기준 최근 N개월. EXTEND: 기준 분석의 시작일 고정, 끝만 연장.
    """
    if config.period_mode == AutoRecalcPeriodMode.EXTEND:
        return base.period_start, latest_end
    # ROLLING 은 기준 분석 시작일에 얽매이지 않고 최신 데이터 기준으로 창을 민다.
    start = latest_end - timedelta(days=int(config.rolling_months) * 30)
    return start, latest_end


@shared_task(name="analysis.auto_recalc")
def auto_recalc(unit_id: int, trigger: str = "") -> dict:
    """기준 분석의 설정 스냅샷을 그대로 써서 다시 돌린다 (AC-19-3)."""
    config = AutoRecalcConfig.objects.filter(unit_id=unit_id, enabled=True).first()
    if config is None:
        return {"skipped": True, "reason": "자동 재계산이 설정되어 있지 않습니다."}

    unit = Unit.objects.get(pk=unit_id)

    # 분석이 이미 돌고 있으면 건너뛰고 사유를 남긴다 (specs/19 §1.5).
    if AnalysisRun.objects.filter(unit=unit, status=RunStatus.RUNNING).exists():
        logger.info("auto recalc skipped unit=%s reason=ANALYSIS_ALREADY_RUNNING", unit.code)
        return {"skipped": True, "reason": "진행 중인 분석이 있어 자동 재계산을 건너뛰었습니다."}

    base = config.base_analysis_run or (
        AnalysisRun.objects.filter(unit=unit, status=RunStatus.SUCCESS)
        .order_by("-executed_at")
        .first()
    )
    if base is None:
        return {"skipped": True, "reason": "기준이 될 성공한 분석이 없습니다."}

    latest_end = (
        Measurement.objects.filter(unit=unit)
        .order_by("-timestamp")
        .values_list("timestamp", flat=True)
        .first()
    )
    if latest_end is None:
        return {"skipped": True, "reason": "적재된 데이터가 없습니다."}

    start, end = resolve_period(config, base, latest_end)

    # 기준 분석의 스냅샷을 override 로 넘겨 같은 기준으로 비교되게 한다.
    snapshot = dict(base.settings_snapshot or {})
    benefit_overrides = dict(base.benefit_params_snapshot or {})

    run = AnalysisRun.objects.create(
        unit=unit,
        executed_by=None,
        period_start=start,
        period_end=end,
        status=RunStatus.RUNNING,
        is_auto=True,
        settings_snapshot=snapshot or build_config(unit),
        benefit_params_snapshot=benefit_overrides,
    )

    ctx = PipelineContext(run=run, unit=unit, config={**build_config(unit), **snapshot})
    try:
        result = run_analysis(ctx, benefit_overrides=benefit_overrides)
    except PipelineError as exc:
        _fail(run, exc.stage, exc.code, str(exc))
        return {"analysis_run_id": run.id, "status": RunStatus.FAILED, "error": str(exc)}
    except Exception as exc:  # noqa: BLE001
        logger.exception("auto recalc failed unit=%s", unit.code)
        _fail(run, "", "ANALYSIS_FAILED", str(exc))
        return {"analysis_run_id": run.id, "status": RunStatus.FAILED, "error": str(exc)}

    if config.notify_on_grade_change:
        notify_grade_change(unit, base, run)
    return {**result, "is_auto": True, "trigger": trigger or config.trigger}


def notify_grade_change(unit: Unit, base: AnalysisRun, run: AnalysisRun) -> Notification | None:
    """등급이 올라갔을 때만 알림을 만든다 (AC-19-2)."""
    before = GRADE_ORDER.get(base.result_grade)
    after = GRADE_ORDER.get(run.result_grade)
    if before is None or after is None or after <= before:
        return None

    labels = {GRADE_NORMAL: "양호", GRADE_CAUTION: "주의", GRADE_WARNING: "경고"}
    return Notification.objects.create(
        unit=unit,
        analysis_run=run,
        level=NotificationLevel.WARNING,
        title=(
            f"{unit.code} 오염 등급 상승: "
            f"{labels[base.result_grade]} → {labels[run.result_grade]}"
        ),
        message=(
            f"자동 재계산 결과 오염도 지수가 {base.result_fi} → {run.result_fi} 로 변했습니다. "
            "세정 계획 검토를 권장합니다."
        ),
        payload={
            "before_grade": base.result_grade,
            "after_grade": run.result_grade,
            "before_fi": base.result_fi,
            "after_fi": run.result_fi,
            "eta_days": run.result_dday,
        },
    )


def _fail(run: AnalysisRun, stage: str, code: str, message: str) -> None:
    run.status = RunStatus.FAILED
    run.failed_stage = stage
    run.error_message = f"[{code}] {message}"[:2000]
    run.save(update_fields=["status", "failed_stage", "error_message"])


# ------------------------------------------------------------------- 백테스트


@shared_task(name="analysis.run_backtest")
def run_backtest(
    unit_id: int, lookahead_days: int | None = None, created_by_id: int | None = None
) -> dict:
    """세정 이벤트마다 컷오프 이전 데이터만으로 파이프라인을 다시 돌린다 (specs/19 §2).

    컷오프 이후의 데이터·세정 이력·모델은 **어떤 경로로도 쓰지 않는다**(AC-19-4).
    lookahead_days 를 생략하면 설정에 등록된 다중 지점(기본 30/60/90)을 모두 평가한다.
    """
    unit = Unit.objects.get(pk=unit_id)
    settings_map = get_effective_settings(unit_id)

    events = list(CleaningEvent.objects.filter(unit=unit).order_by("cleaned_at"))
    if len(events) <= 1:
        # 세정 1회 이하는 검증 자체가 불가능하다 (AC-19-6).
        return {
            "unit_id": unit_id,
            "available": False,
            "reason": "세정 이력이 2회 이상이어야 백테스트를 실행할 수 있습니다.",
        }

    if lookahead_days is None:
        points = settings_map.get("backtest_lookahead_days") or [60]
        lookaheads = [int(x) for x in points]
    else:
        lookaheads = [int(lookahead_days)]

    results = [
        _run_lookahead(unit, events, days, settings_map, created_by_id) for days in lookaheads
    ]
    return {"unit_id": unit_id, "available": True, "results": results}


def _run_lookahead(
    unit: Unit, events: list, lookahead_days: int, settings_map: dict, created_by_id: int | None
) -> dict:
    """컷오프 선행 일수 하나에 대한 전체 평가. 결과 1건을 저장한다."""
    hit_window = int(settings_map.get("backtest_hit_window_days", 30))
    warnings: list[dict] = []

    period_start = (
        Measurement.objects.filter(unit=unit)
        .order_by("timestamp")
        .values_list("timestamp", flat=True)
        .first()
    )

    summary = bt.BacktestSummary(hit_window_days=hit_window)
    for event in events:
        cutoff = event.cleaned_at - timedelta(days=lookahead_days)
        if period_start is None or cutoff <= period_start:
            at = timezone.localtime(event.cleaned_at)
            warnings.append(
                {
                    "code": "CUTOFF_BEFORE_DATA",
                    "message": f"{at:%Y-%m-%d} 세정은 컷오프 이전 데이터가 부족합니다.",
                }
            )
            continue

        summary.cases.append(_run_case(unit, event, cutoff, lookahead_days))

    _fill_actual_fi(unit, summary.cases, warnings)

    predicted, actual = _recovery_pairs(summary.cases)
    result = BacktestResult.objects.create(
        unit=unit,
        created_by_id=created_by_id,
        lookahead_days=lookahead_days,
        cases=[c.to_dict() for c in summary.cases],
        summary=summary.to_dict(),
        coefficient_suggestion=bt.suggest_coefficients(predicted, actual),
        warnings=warnings,
    )
    return {"backtest_id": result.id, "lookahead_days": lookahead_days, **summary.to_dict()}


def _fill_actual_fi(unit: Unit, cases: list, warnings: list[dict]) -> None:
    """실제 세정 시점의 FI (specs/19 §2.4).

    컷오프 없이 돌린 **최신 성공 분석**의 FI 시계열에서 읽는다. 사후 계산값이므로
    예측에는 쓰이지 않고 표에 참고로만 붙는다.
    """
    if not cases:
        return

    full_run = (
        AnalysisRun.objects.filter(unit=unit, status=RunStatus.SUCCESS)
        .order_by("-executed_at")
        .first()
    )
    if full_run is None:
        warnings.append(
            {
                "code": "NO_FULL_RUN",
                "message": "전체 기간 분석 결과가 없어 실제 세정 시점의 FI를 채우지 못했습니다.",
            }
        )
        return

    series = dict(
        FoulingIndexPoint.objects.filter(
            analysis_run=full_run, cluster_key="", date__in=[c.actual_date for c in cases]
        ).values_list("date", "fi_value")
    )
    for case in cases:
        case.fi_at_actual = series.get(case.actual_date)


def _recovery_pairs(cases: list) -> tuple[list[float], list[float]]:
    """컷오프 시점의 예측 Δ차압 vs 세정 전후 비교로 확인된 실제 회복량 (specs/19 §2.3).

    손실 모델에서 편익은 Δ차압에 비례하므로 두 값의 비가 곧 손실 계수의 보정 배수다.

    예측값은 **백테스트가 그 컷오프에서 직접 계산한 값**을 쓴다. 운영 이력에서
    "세정 전에 실행된 분석"을 찾는 방식은 과거 데이터를 나중에 적재한 경우
    (executed_at 이 전부 최근) 짝이 하나도 만들어지지 않는다.
    """
    predicted: list[float] = []
    actual: list[float] = []

    for case in cases:
        if not case.predicted_delta_dp:
            continue
        event = CleaningEvent.objects.filter(pk=case.cleaning_event_id).first()
        report = event.comparisons.order_by("-created_at").first() if event else None
        if report is None:
            continue
        rows = (report.metrics or {}).get("rows") or []
        row = next((r for r in rows if r.get("key") == "residual_dp"), None)
        if row is None or row.get("delta") is None:
            continue

        predicted.append(float(case.predicted_delta_dp))
        # 잔차는 세정 후 내려가므로 회복량은 부호를 뒤집은 값이다.
        actual.append(-float(row["delta"]))

    return predicted, actual


def _run_case(unit: Unit, event, cutoff, lookahead_days: int) -> bt.CaseResult:
    """컷오프 시점에서 한 번 예측하고, 사용한 임시 AnalysisRun 은 롤백한다."""
    period_start = (
        Measurement.objects.filter(unit=unit)
        .order_by("timestamp")
        .values_list("timestamp", flat=True)
        .first()
    )
    actual_date = timezone.localtime(event.cleaned_at).date()
    cutoff_date = timezone.localtime(cutoff).date()

    try:
        with transaction.atomic():
            run = AnalysisRun.objects.create(
                unit=unit,
                period_start=period_start,
                period_end=cutoff,
                status=RunStatus.RUNNING,
                is_auto=True,
                settings_snapshot=build_config(unit),
            )
            ctx = PipelineContext(run=run, unit=unit, config=build_config(unit), cutoff=cutoff)
            run_analysis(ctx)
            run.refresh_from_db()
            trend = getattr(run, "trend", None)
            benefit = getattr(run, "benefit", None)
            case = bt.build_case(
                cleaning_event_id=event.id,
                actual_date=actual_date,
                cutoff_date=cutoff_date,
                predicted_date=trend.eta_date if trend else None,
                trend_status=trend.status if trend else "",
                fi_at_cutoff=run.result_fi,
                # 롤백 전에 꺼내 둔다 — 이 트랜잭션이 끝나면 접근할 수 없다.
                predicted_delta_dp=benefit.delta_dp_kpa if benefit else None,
                note="" if trend and trend.eta_date else "임계치 도달 예측이 나오지 않았습니다.",
            )
            # 백테스트 산출물은 운영 이력에 남기지 않는다.
            raise _Rollback(case)
    except _Rollback as done:
        return done.case
    except PipelineError as exc:
        return bt.build_case(
            cleaning_event_id=event.id,
            actual_date=actual_date,
            cutoff_date=cutoff_date,
            predicted_date=None,
            trend_status="FAILED",
            note=f"[{exc.code}] {exc}",
        )


class _Rollback(Exception):
    """성공 결과를 들고 트랜잭션만 되돌리기 위한 내부 신호."""

    def __init__(self, case: bt.CaseResult) -> None:
        super().__init__("rollback")
        self.case = case
