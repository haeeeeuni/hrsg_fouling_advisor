"""등급 상승 알림 (specs/19 §1.4). PostgreSQL 필요.

핵심: 자동 재계산은 기본 비활성이므로 **수동 분석 실행 경로에서도** 알림이 나와야 한다.
"""

from __future__ import annotations

import pandas as pd
import pytest
from django.utils import timezone

from analysis.models import AnalysisRun, Notification, NotificationLevel, RunStatus
from analysis.notifications import notify_after_manual_run, previous_success_run
from units.models import Unit, UnitSetting

pytestmark = pytest.mark.django_db


def _aware(text: str):
    return timezone.make_aware(pd.Timestamp(text).to_pydatetime())


@pytest.fixture
def unit(db) -> Unit:
    return Unit.objects.create(code="U1", name="1호기", rated_power_mw=160, min_load_mw=60)


def _run(unit, fi, grade, at, status=RunStatus.SUCCESS, dday=30) -> AnalysisRun:
    """`executed_at` 은 auto_now_add 라 지정할 수 없다 — 생성 순서가 곧 실행 순서다."""
    return AnalysisRun.objects.create(
        unit=unit,
        period_start=_aware("2024-01-01"),
        period_end=_aware(at),
        status=status,
        result_fi=fi,
        result_grade=grade,
        result_dday=dday,
    )


def _setting(unit, **values) -> None:
    for key, value in values.items():
        UnitSetting.objects.update_or_create(unit=unit, key=key, defaults={"value": str(value)})


# --- 비교 기준 찾기 -------------------------------------------------------


def test_previous_success_run_picks_latest_earlier_success(unit):
    _run(unit, 10.0, "NORMAL", "2024-02-01")
    expected = _run(unit, 30.0, "CAUTION", "2024-03-01")
    current = _run(unit, 62.0, "WARNING", "2024-04-01")

    assert previous_success_run(current) == expected


def test_previous_success_run_ignores_failed_runs(unit):
    expected = _run(unit, 30.0, "CAUTION", "2024-02-01")
    _run(unit, None, "", "2024-03-01", status=RunStatus.FAILED)
    current = _run(unit, 62.0, "WARNING", "2024-04-01")

    assert previous_success_run(current) == expected


def test_previous_success_run_is_scoped_to_unit(unit):
    other = Unit.objects.create(code="U2", name="2호기", rated_power_mw=160, min_load_mw=60)
    _run(other, 30.0, "CAUTION", "2024-03-01")
    current = _run(unit, 62.0, "WARNING", "2024-04-01")

    assert previous_success_run(current) is None


# --- 수동 실행 경로 (이 기능의 핵심) --------------------------------------


def test_manual_run_notifies_on_grade_escalation(unit):
    _run(unit, 30.0, "CAUTION", "2024-03-01")
    current = _run(unit, 62.0, "WARNING", "2024-04-01")

    notification = notify_after_manual_run(current)

    assert notification is not None
    assert notification.level == NotificationLevel.WARNING
    assert notification.payload["is_auto"] is False
    # 수동 실행이므로 '자동 재계산' 문구가 붙으면 안 된다.
    assert "자동 재계산" not in notification.message


def test_fi_is_rounded_to_one_decimal(unit):
    """FI 는 어디서나 소수 1자리다 — 원시 부동소수가 사용자에게 보이면 안 된다."""
    _run(unit, 12.0, "CAUTION", "2024-03-01")
    current = _run(unit, 45.66673862226151, "WARNING", "2024-04-01")

    notification = notify_after_manual_run(current)

    assert "45.7" in notification.message
    assert "45.66673862226151" not in notification.message


def test_first_analysis_of_a_unit_does_not_notify(unit):
    """비교 대상이 없으면 '상승' 으로 볼 근거가 없다."""
    assert notify_after_manual_run(_run(unit, 80.0, "WARNING", "2024-04-01")) is None
    assert Notification.objects.count() == 0


def test_manual_notification_can_be_turned_off(unit):
    _setting(unit, notify_on_manual_run=False)
    _run(unit, 30.0, "CAUTION", "2024-03-01")

    assert notify_after_manual_run(_run(unit, 62.0, "WARNING", "2024-04-01")) is None
    assert Notification.objects.count() == 0


# --- 태스크 배선 (이번 수정의 본체) --------------------------------------


def test_analysis_task_actually_triggers_notification(unit, monkeypatch):
    """`run_analysis_task` 가 알림을 부르는지 고정한다.

    이 배선이 없던 동안 알림은 자동 재계산(기본 비활성)에서만 생성돼
    기능이 사실상 죽어 있었다. 회귀하면 조용히 다시 죽으므로 테스트로 못박는다.
    """
    from analysis import tasks as analysis_tasks

    _run(unit, 30.0, "CAUTION", "2024-03-01")
    current = _run(unit, 0.0, "NORMAL", "2024-04-01")

    def fake_run_analysis(ctx, benefit_overrides=None):
        # 파이프라인이 결과를 저장하는 것처럼 등급을 올려 둔다.
        AnalysisRun.objects.filter(pk=ctx.run.pk).update(
            status=RunStatus.SUCCESS, result_fi=62.0, result_grade="WARNING", result_dday=20
        )
        return {"analysis_run_id": ctx.run.pk, "status": RunStatus.SUCCESS}

    monkeypatch.setattr(analysis_tasks, "run_analysis", fake_run_analysis)
    monkeypatch.setattr(analysis_tasks, "build_config", lambda unit, overrides=None: {})

    analysis_tasks.run_analysis_task(current.pk)

    notification = Notification.objects.get()
    assert notification.unit_id == unit.id
    assert notification.analysis_run_id == current.pk
    assert notification.payload["after_grade"] == "WARNING"


def test_notification_failure_does_not_fail_the_analysis(unit, monkeypatch):
    """알림이 터져도 성공한 분석은 성공으로 남아야 한다."""
    from analysis import tasks as analysis_tasks

    _run(unit, 30.0, "CAUTION", "2024-03-01")
    current = _run(unit, 0.0, "NORMAL", "2024-04-01")

    def fake_run_analysis(ctx, benefit_overrides=None):
        AnalysisRun.objects.filter(pk=ctx.run.pk).update(
            status=RunStatus.SUCCESS, result_fi=62.0, result_grade="WARNING"
        )
        return {"status": RunStatus.SUCCESS}

    def boom(run):
        raise RuntimeError("알림 저장 실패")

    monkeypatch.setattr(analysis_tasks, "run_analysis", fake_run_analysis)
    monkeypatch.setattr(analysis_tasks, "build_config", lambda unit, overrides=None: {})
    monkeypatch.setattr(analysis_tasks, "notify_after_manual_run", boom)

    result = analysis_tasks.run_analysis_task(current.pk)

    assert result["status"] == RunStatus.SUCCESS
    current.refresh_from_db()
    assert current.status == RunStatus.SUCCESS


# --- 목록 필터 (대시보드 배너가 의존한다) --------------------------------


@pytest.fixture
def logged_in(api, normal_user, user_password):
    api.login(employee_no=normal_user.employee_no, password=user_password)
    return api


def test_unread_filter_returns_unread_notifications(unit, logged_in):
    """`?unread=true` 는 '읽지 않은 것' 이다.

    이 필터는 반대로 구현돼 있었고, 벨 아이콘이 파라미터를 쓰지 않아 드러나지 않았다.
    대시보드 배너가 이 필터에 의존하므로 계약을 고정한다.
    """
    unread = Notification.objects.create(unit=unit, title="미확인", is_read=False)
    Notification.objects.create(unit=unit, title="확인함", is_read=True)

    response = logged_in.get("/api/notifications/", {"unread": "true"})

    assert response.status_code == 200
    assert [row["id"] for row in response.data["results"]] == [unread.id]


def test_unread_false_returns_read_notifications(unit, logged_in):
    Notification.objects.create(unit=unit, title="미확인", is_read=False)
    read = Notification.objects.create(unit=unit, title="확인함", is_read=True)

    response = logged_in.get("/api/notifications/", {"unread": "false"})

    assert [row["id"] for row in response.data["results"]] == [read.id]


def test_unit_filter_scopes_notifications(unit, logged_in):
    other = Unit.objects.create(code="U9", name="9호기", rated_power_mw=160, min_load_mw=60)
    mine = Notification.objects.create(unit=unit, title="내 호기", is_read=False)
    Notification.objects.create(unit=other, title="다른 호기", is_read=False)

    response = logged_in.get("/api/notifications/", {"unit_id": unit.id, "unread": "true"})

    assert [row["id"] for row in response.data["results"]] == [mine.id]
