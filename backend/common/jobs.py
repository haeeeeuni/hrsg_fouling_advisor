"""비동기 작업 추상화 (specs/15 §1).

뷰는 Celery를 직접 알지 못하고 이 모듈만 호출한다. 실행기를 바꾸더라도
`202 + job_id` → `GET /api/jobs/{job_id}/` 계약은 그대로 유지된다.

작업 상태는 Celery 결과 백엔드(Redis)에 둔다. 영속 기록은 UploadBatch / AnalysisRun
같은 도메인 테이블이 담당하므로 별도 Job 테이블을 두지 않는다.
"""

from __future__ import annotations

from typing import Any

from celery import current_app
from celery.result import AsyncResult

# 공통 상태값 (specs/15 §1)
RUNNING = "RUNNING"
SUCCESS = "SUCCESS"
FAILED = "FAILED"
CANCELED = "CANCELED"

# Celery 내부 상태 → 공통 상태
_STATE_MAP = {
    "PENDING": RUNNING,
    "RECEIVED": RUNNING,
    "STARTED": RUNNING,
    "RETRY": RUNNING,
    "PROGRESS": RUNNING,
    "SUCCESS": SUCCESS,
    "FAILURE": FAILED,
    "REVOKED": CANCELED,
}

PROGRESS_STATE = "PROGRESS"


def enqueue(task: Any, **kwargs: Any) -> str:
    """작업을 큐에 넣고 job_id 를 반환한다."""
    return task.apply_async(kwargs=kwargs).id


def report_progress(task: Any, percent: int, stage: str) -> None:
    """워커 내부에서 진행률을 갱신한다.

    task.request.called_directly 인 경우(동기 호출/테스트)에는 아무 것도 하지 않는다.
    """
    if task is None or getattr(task.request, "called_directly", True):
        return
    task.update_state(
        state=PROGRESS_STATE,
        meta={"progress": max(0, min(100, int(percent))), "stage": stage},
    )


def get_status(job_id: str) -> dict[str, Any]:
    """job 상태 조회 응답 본문을 만든다.

    주의: Celery 는 존재하지 않는 job_id 에 대해서도 PENDING 을 돌려준다.
    따라서 '알 수 없는 id' 와 '대기 중'은 구분되지 않는다.
    """
    result = AsyncResult(job_id, app=current_app)
    state = result.state
    status = _STATE_MAP.get(state, RUNNING)

    payload: dict[str, Any] = {
        "job_id": job_id,
        "status": status,
        "progress": 0,
        "stage": "",
        "result": None,
        "error": None,
    }

    if state == PROGRESS_STATE and isinstance(result.info, dict):
        payload["progress"] = result.info.get("progress", 0)
        payload["stage"] = result.info.get("stage", "")
    elif status == SUCCESS:
        payload["progress"] = 100
        payload["result"] = result.result
    elif status == FAILED:
        info = result.info
        # 워커에서 DomainError 로 실패한 경우 code/message 를 그대로 전달한다.
        if isinstance(info, dict) and "code" in info:
            payload["error"] = info
        else:
            payload["error"] = {
                "code": "JOB_FAILED",
                "message": "작업이 실패했습니다.",
                "details": {"reason": str(info)[:500]},
            }

    return payload


def cancel(job_id: str) -> None:
    AsyncResult(job_id, app=current_app).revoke(terminate=False)
