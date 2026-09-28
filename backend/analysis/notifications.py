"""등급 상승 알림 (specs/19 §1.4).

전달 수단은 **앱 내 알림 센터(벨 아이콘) + 대시보드 배너** 하나뿐이다.
자동 재계산(`tasks_auto`)과 수동 분석 실행(`tasks`) 양쪽이 같은 함수를 쓴다.

호출 지점을 태스크 계층에 두는 이유: `pipeline.run_analysis` 안에 넣으면 백테스트
(`tasks_auto.run_backtest`)가 과거 시점을 재현할 때마다 알림이 쏟아진다.
"""

from __future__ import annotations

import logging

from analysis.models import AnalysisRun, Notification, NotificationLevel, RunStatus
from analysis.services.fouling_index import GRADE_CAUTION, GRADE_NORMAL, GRADE_WARNING
from units.models import Unit
from units.settings_resolver import get_effective_settings

logger = logging.getLogger(__name__)

# 낮을수록 양호. 등급이 **올라갔을 때만** 알린다 (specs/19 §1.4).
GRADE_ORDER = {GRADE_NORMAL: 0, GRADE_CAUTION: 1, GRADE_WARNING: 2}
GRADE_LABELS = {GRADE_NORMAL: "양호", GRADE_CAUTION: "주의", GRADE_WARNING: "경고"}


def _fi(value) -> str:
    """FI 표시는 소수 1자리로 통일한다(프론트 `formatFi` 와 같은 규약)."""
    return "-" if value is None else f"{float(value):.1f}"


def previous_success_run(run: AnalysisRun) -> AnalysisRun | None:
    """같은 호기의 직전 성공 분석.

    수동 실행에는 자동 재계산의 `base_analysis_run` 같은 기준이 없다.
    "사용자가 직전에 보고 있던 결과" 가 비교 기준이므로 실행 시각 역순으로 찾는다.
    `id__lt` 로 자기 자신과 이후 실행을 배제한다(실행 시각이 같아도 안전하다).
    """
    return (
        AnalysisRun.objects.filter(unit_id=run.unit_id, status=RunStatus.SUCCESS, id__lt=run.id)
        .order_by("-executed_at", "-id")
        .first()
    )


def notify_grade_change(
    unit: Unit,
    base: AnalysisRun | None,
    run: AnalysisRun,
    *,
    is_auto: bool = False,
) -> Notification | None:
    """등급이 올라갔을 때만 알림을 만든다 (AC-19-2).

    비교 대상이 없으면(호기의 첫 분석) 알리지 않는다 — 상승으로 볼 근거가 없다.
    """
    if base is None:
        return None

    before = GRADE_ORDER.get(base.result_grade)
    after = GRADE_ORDER.get(run.result_grade)
    if before is None or after is None or after <= before:
        return None

    origin = "자동 재계산" if is_auto else "분석"
    return Notification.objects.create(
        unit=unit,
        analysis_run=run,
        level=NotificationLevel.WARNING,
        title=(
            f"{unit.code} 오염 등급 상승: "
            f"{GRADE_LABELS[base.result_grade]} → {GRADE_LABELS[run.result_grade]}"
        ),
        message=(
            f"{origin} 결과 오염도 지수가 {_fi(base.result_fi)} → {_fi(run.result_fi)} 로 "
            "변했습니다. 세정 계획 검토를 권장합니다."
        ),
        payload={
            "before_grade": base.result_grade,
            "after_grade": run.result_grade,
            "before_fi": base.result_fi,
            "after_fi": run.result_fi,
            "eta_days": run.result_dday,
            "is_auto": is_auto,
        },
    )


def notify_after_manual_run(run: AnalysisRun) -> Notification | None:
    """수동 분석 실행 뒤 등급 상승을 알린다.

    자동 재계산이 꺼져 있어도 알림이 동작해야 한다 — 자동 재계산은 기본 비활성이라
    이 경로가 없으면 알림 기능이 사실상 죽어 있게 된다.
    """
    if not get_effective_settings(run.unit_id).get("notify_on_manual_run"):
        return None
    return notify_grade_change(run.unit, previous_success_run(run), run, is_auto=False)
