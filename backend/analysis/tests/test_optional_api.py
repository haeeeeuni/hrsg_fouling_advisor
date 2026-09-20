"""옵션 기능 API — 권한·계약 검증 (specs/19, specs/15 §12). PostgreSQL 필요."""

from __future__ import annotations

import pandas as pd
import pytest
from django.utils import timezone

from analysis.models import (
    AnalysisRun,
    AutoRecalcConfig,
    AutoRecalcPeriodMode,
    AutoRecalcTrigger,
    Notification,
    NotificationLevel,
    RunStatus,
)
from analysis.tasks_auto import notify_grade_change, resolve_period
from maintenance.models import CleaningEvent
from units.models import Unit

pytestmark = pytest.mark.django_db

COMPARISON_URL = "/api/units/comparison/"
BACKTEST_URL = "/api/backtests/"
NOTIFICATION_URL = "/api/notifications/"


def _aware(text: str):
    return timezone.make_aware(pd.Timestamp(text).to_pydatetime())


@pytest.fixture
def units(db):
    return [
        Unit.objects.create(code=code, name=f"{code}호기", rated_power_mw=160, min_load_mw=60)
        for code in ("U1", "U2", "U3")
    ]


def _run(unit, fi, grade, dday, at):
    run = AnalysisRun.objects.create(
        unit=unit,
        period_start=_aware("2024-01-01"),
        period_end=_aware(at),
        status=RunStatus.SUCCESS,
        result_fi=fi,
        result_grade=grade,
        result_dday=dday,
    )
    return run


# --- 권한 (AGENTS.md §8) ---


def test_anonymous_cannot_read_comparison(api):
    assert api.get(COMPARISON_URL).status_code == 401


def test_normal_user_cannot_start_backtest(api, normal_user, units):
    api.force_authenticate(normal_user)

    assert api.post(BACKTEST_URL, {"unit_id": units[0].id}, format="json").status_code == 403


def test_normal_user_cannot_change_auto_recalc(api, normal_user, units):
    api.force_authenticate(normal_user)
    url = f"/api/units/{units[0].id}/auto-recalc/"

    assert api.put(url, {"enabled": True}, format="json").status_code == 403


def test_normal_user_can_read_auto_recalc(api, normal_user, units):
    api.force_authenticate(normal_user)

    res = api.get(f"/api/units/{units[0].id}/auto-recalc/")

    assert res.status_code == 200
    assert res.data["enabled"] is False


# --- 자동 재계산 설정 (specs/19 §1.2) ---


def test_admin_updates_auto_recalc_config(api, admin_user, units):
    api.force_authenticate(admin_user)
    url = f"/api/units/{units[0].id}/auto-recalc/"

    res = api.put(url, {"enabled": True, "rolling_months": 6}, format="json")

    assert res.status_code == 200
    config = AutoRecalcConfig.objects.get(unit=units[0])
    assert config.enabled is True
    assert config.rolling_months == 6
    assert config.updated_by == admin_user


def test_model_retrain_is_off_by_default(api, admin_user, units):
    """오염 구간으로 학습하면 기준이 오염된다 (specs/19 §1.5)."""
    api.force_authenticate(admin_user)

    res = api.get(f"/api/units/{units[0].id}/auto-recalc/")

    assert res.data["retrain_model"] is False


def test_schedule_trigger_requires_cron(api, admin_user, units):
    api.force_authenticate(admin_user)

    res = api.put(
        f"/api/units/{units[0].id}/auto-recalc/",
        {"enabled": True, "trigger": AutoRecalcTrigger.SCHEDULE},
        format="json",
    )

    assert res.status_code == 400


# --- 기간 산정 (specs/19 §1.3) ---


def test_rolling_window_follows_latest_data(units):
    base = _run(units[0], 30.0, "NORMAL", 100, "2024-03-01")
    config = AutoRecalcConfig(
        unit=units[0], period_mode=AutoRecalcPeriodMode.ROLLING, rolling_months=6
    )

    start, end = resolve_period(config, base, _aware("2024-06-01"))

    assert end == _aware("2024-06-01")
    assert start < _aware("2024-06-01")
    assert start > _aware("2023-11-01")


def test_extend_mode_keeps_base_start(units):
    base = _run(units[0], 30.0, "NORMAL", 100, "2024-03-01")
    config = AutoRecalcConfig(unit=units[0], period_mode=AutoRecalcPeriodMode.EXTEND)

    start, end = resolve_period(config, base, _aware("2024-06-01"))

    assert start == base.period_start
    assert end == _aware("2024-06-01")


# --- 등급 상승 알림 (AC-19-2) ---


def test_ac_19_2_grade_escalation_creates_notification(units):
    base = _run(units[0], 30.0, "CAUTION", 90, "2024-03-01")
    later = _run(units[0], 62.0, "WARNING", 20, "2024-06-01")

    notification = notify_grade_change(units[0], base, later)

    assert notification is not None
    assert notification.level == NotificationLevel.WARNING
    assert notification.payload["before_grade"] == "CAUTION"
    assert notification.payload["after_grade"] == "WARNING"


def test_grade_improvement_creates_no_notification(units):
    base = _run(units[0], 62.0, "WARNING", 20, "2024-03-01")
    later = _run(units[0], 30.0, "CAUTION", 90, "2024-06-01")

    assert notify_grade_change(units[0], base, later) is None
    assert Notification.objects.count() == 0


def test_unchanged_grade_creates_no_notification(units):
    base = _run(units[0], 30.0, "CAUTION", 90, "2024-03-01")
    later = _run(units[0], 33.0, "CAUTION", 80, "2024-06-01")

    assert notify_grade_change(units[0], base, later) is None


def test_notification_list_reports_unread_count(api, normal_user, units):
    Notification.objects.create(unit=units[0], title="테스트 알림")
    api.force_authenticate(normal_user)

    res = api.get(NOTIFICATION_URL)

    assert res.status_code == 200
    assert res.data["unread_count"] == 1


def test_marking_notification_read_clears_count(api, normal_user, units):
    item = Notification.objects.create(unit=units[0], title="테스트 알림")
    api.force_authenticate(normal_user)

    api.post(f"{NOTIFICATION_URL}{item.id}/read/")

    item.refresh_from_db()
    assert item.is_read is True


# --- 백테스트 가용성 (AC-19-6) ---


def test_ac_19_6_backtest_rejected_with_one_cleaning(api, admin_user, units):
    CleaningEvent.objects.create(unit=units[0], cleaned_at=_aware("2024-02-01"))
    api.force_authenticate(admin_user)

    res = api.post(BACKTEST_URL, {"unit_id": units[0].id}, format="json")

    assert res.status_code == 400
    assert res.data["error"]["code"] == "BACKTEST_NOT_AVAILABLE"


def test_availability_flags_units_with_too_few_cleanings(api, normal_user, units):
    CleaningEvent.objects.create(unit=units[0], cleaned_at=_aware("2024-02-01"))
    CleaningEvent.objects.create(unit=units[0], cleaned_at=_aware("2024-06-01"))
    api.force_authenticate(normal_user)

    rows = {r["unit_code"]: r for r in api.get(f"{BACKTEST_URL}availability/").data["results"]}

    assert rows["U1"]["available"] is True
    assert rows["U2"]["available"] is False
    assert rows["U2"]["reason"]


# --- 호기 간 비교 (AC-19-7~9) ---


def test_ac_19_7_comparison_ranks_units(api, normal_user, units, seeded):
    _run(units[0], 20.0, "NORMAL", 300, "2024-06-01")
    _run(units[1], 70.0, "WARNING", 20, "2024-06-01")
    _run(units[2], 45.0, "CAUTION", 120, "2024-06-01")
    api.force_authenticate(normal_user)

    results = api.get(COMPARISON_URL).data["results"]

    assert [r["unit_code"] for r in results[:3]] == ["U2", "U3", "U1"]


def test_ac_19_8_unanalyzed_unit_is_marked(api, normal_user, units, seeded):
    _run(units[0], 20.0, "NORMAL", 300, "2024-06-01")
    api.force_authenticate(normal_user)

    results = api.get(COMPARISON_URL).data["results"]
    pending = [r for r in results if not r["has_analysis"]]

    assert len(pending) == 2
    assert all(r["priority_score"] is None for r in pending)


def test_comparison_uses_latest_successful_run_only(api, normal_user, units, seeded):
    _run(units[0], 80.0, "WARNING", 10, "2024-01-01")
    _run(units[0], 20.0, "NORMAL", 300, "2024-06-01")
    AnalysisRun.objects.create(
        unit=units[0],
        period_start=_aware("2024-01-01"),
        period_end=_aware("2024-07-01"),
        status=RunStatus.FAILED,
        result_fi=99.0,
    )
    api.force_authenticate(normal_user)

    row = next(r for r in api.get(COMPARISON_URL).data["results"] if r["unit_code"] == "U1")

    assert row["fi"] == 20.0


def test_comparison_can_be_filtered_to_selected_units(api, normal_user, units, seeded):
    for unit in units:
        _run(unit, 40.0, "CAUTION", 100, "2024-06-01")
    api.force_authenticate(normal_user)

    results = api.get(f"{COMPARISON_URL}?unit_ids={units[0].id},{units[1].id}").data["results"]

    assert {r["unit_code"] for r in results} == {"U1", "U2"}
