"""분석 실행 Celery 태스크 (specs/15 §6)."""

from __future__ import annotations

import logging

from celery import shared_task

from analysis.models import AnalysisRun, RunStatus
from analysis.notifications import notify_after_manual_run
from analysis.pipeline import PipelineContext, PipelineError, build_config, run_analysis
from common.jobs import report_progress

logger = logging.getLogger(__name__)


@shared_task(bind=True, name="analysis.run_analysis")
def run_analysis_task(
    self,
    analysis_run_id: int,
    overrides: dict | None = None,
    benefit_overrides: dict | None = None,
) -> dict:
    run = AnalysisRun.objects.select_related("unit").get(pk=analysis_run_id)
    ctx = PipelineContext(
        run=run,
        unit=run.unit,
        config=build_config(run.unit, overrides),
        progress=lambda percent, stage: report_progress(self, percent, stage),
    )

    try:
        result = run_analysis(ctx, benefit_overrides=benefit_overrides)
    except PipelineError as exc:
        _fail(run, exc.stage, exc.code, str(exc))
        # 워커 실패 정보를 job 상태로 그대로 노출한다 (common/jobs.get_status).
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("analysis failed run_id=%s", analysis_run_id)
        _fail(run, "", "ANALYSIS_FAILED", str(exc))
        raise

    # 등급 상승 알림 (specs/19 §1.4). 자동 재계산이 꺼져 있어도 동작해야 하므로
    # 수동 실행 경로에도 건다. 알림 실패가 성공한 분석을 실패로 만들지는 않는다.
    run.refresh_from_db()
    try:
        notify_after_manual_run(run)
    except Exception:  # noqa: BLE001
        logger.exception("notify failed run_id=%s", analysis_run_id)

    return result


def _fail(run: AnalysisRun, stage: str, code: str, message: str) -> None:
    run.status = RunStatus.FAILED
    run.failed_stage = stage[:50]
    run.error_message = f"{code}: {message}"[:2000]
    run.save(update_fields=["status", "failed_stage", "error_message"])
