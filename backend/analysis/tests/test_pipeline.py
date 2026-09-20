"""분석 파이프라인 통합 검증 (AC-14-3, specs/15 §6). PostgreSQL 필요."""

import pandas as pd
import pytest
from django.utils import timezone

from analysis.models import AnalysisRun, FoulingIndexPoint, ModelVersion, RunStatus
from analysis.tests.factories import sawtooth_fouling, steady_frame
from ingestion.models import Measurement
from maintenance.models import CleaningEvent
from units.models import ColumnMapping, Unit

pytestmark = pytest.mark.django_db

ANALYSIS_URL = "/api/analysis-runs/"


@pytest.fixture
def unit(db):
    u = Unit.objects.create(
        code="U1", name="1호기", rated_power_mw=160, min_load_mw=60, sampling_interval_min=10
    )
    for field in (
        "timestamp",
        "gt_power_mw",
        "ambient_temp_c",
        "gt_exhaust_temp_c",
        "exhaust_flow",
        "hrsg_gas_dp_kpa",
        "stack_temp_c",
        "duct_burner_on",
    ):
        ColumnMapping.objects.create(unit=u, standard_field=field, source_column=field)
    return u


def load_measurements(unit, frame):
    tz = timezone.get_current_timezone()
    Measurement.objects.bulk_create(
        [
            Measurement(
                unit=unit,
                timestamp=timezone.make_aware(row["timestamp"].to_pydatetime(), tz),
                gt_power_mw=row["gt_power_mw"],
                ambient_temp_c=row["ambient_temp_c"],
                gt_exhaust_temp_c=row["gt_exhaust_temp_c"],
                exhaust_flow=row["exhaust_flow"],
                hrsg_gas_dp_kpa=row["hrsg_gas_dp_kpa"],
                stack_temp_c=row["stack_temp_c"],
                duct_burner_on=bool(row["duct_burner_on"]),
                st_power_mw=row["st_power_mw"],
                steam_flow_tph=row["steam_flow_tph"],
                feedwater_temp_c=row["feedwater_temp_c"],
                ambient_pressure_kpa=row["ambient_pressure_kpa"],
                humidity_pct=row["humidity_pct"],
            )
            for row in frame.to_dict(orient="records")
        ],
        batch_size=2000,
    )


@pytest.fixture
def unit_with_fouling(unit, seeded):
    """90일간 오염이 진행되다 중간에 세정되는 데이터."""
    n = 90 * 24 * 6
    frame = steady_frame(days=90, start="2024-01-01", fouling=sawtooth_fouling(n, cycles=2), seed=3)
    load_measurements(unit, frame)
    CleaningEvent.objects.create(
        unit=unit,
        cleaned_at=timezone.make_aware(pd.Timestamp("2024-02-15").to_pydatetime()),
    )
    return unit


def start_analysis(api, user, unit, **extra):
    api.force_authenticate(user)
    return api.post(
        ANALYSIS_URL,
        {
            "unit_id": unit.id,
            "period_start": "2024-01-01T00:00:00+09:00",
            "period_end": "2024-04-01T00:00:00+09:00",
            **extra,
        },
        format="json",
    )


# --- 권한 / 계약 ---


def test_anonymous_cannot_start_analysis(api, unit):
    assert api.post(ANALYSIS_URL, {}, format="json").status_code == 401


def test_ac_15_4_returns_202_with_job_id(api, normal_user, unit_with_fouling):
    res = start_analysis(api, normal_user, unit_with_fouling)

    assert res.status_code == 202
    assert res.data["job_id"]
    assert res.data["analysis_run_id"]


def test_ac_15_5_concurrent_analysis_on_same_unit_is_rejected(api, normal_user, unit):
    AnalysisRun.objects.create(
        unit=unit,
        period_start=timezone.now(),
        period_end=timezone.now(),
        status=RunStatus.RUNNING,
    )

    res = start_analysis(api, normal_user, unit)

    assert res.status_code == 409
    assert res.data["error"]["code"] == "ANALYSIS_ALREADY_RUNNING"


def test_period_end_must_follow_start(api, normal_user, unit):
    api.force_authenticate(normal_user)

    res = api.post(
        ANALYSIS_URL,
        {
            "unit_id": unit.id,
            "period_start": "2024-04-01T00:00:00+09:00",
            "period_end": "2024-01-01T00:00:00+09:00",
        },
        format="json",
    )

    assert res.status_code == 400


def test_missing_data_fails_with_clear_reason(api, normal_user, unit, seeded):
    res = start_analysis(api, normal_user, unit)

    run = AnalysisRun.objects.get(pk=res.data["analysis_run_id"])
    assert run.status == RunStatus.FAILED
    assert "INSUFFICIENT_DATA" in run.error_message


# --- 파이프라인 결과 ---


def test_analysis_succeeds_and_records_summary(api, normal_user, unit_with_fouling):
    res = start_analysis(api, normal_user, unit_with_fouling)

    run = AnalysisRun.objects.get(pk=res.data["analysis_run_id"])
    assert run.status == RunStatus.SUCCESS
    assert run.result_fi is not None
    assert run.result_grade in {"NORMAL", "CAUTION", "WARNING"}
    assert run.duration_sec is not None


def test_ac_14_3_run_stores_everything_needed_to_reproduce(api, normal_user, unit_with_fouling):
    """AC-14-3: AnalysisRun 만 보고도 결과를 동일하게 재현할 정보가 모두 저장된다."""
    res = start_analysis(api, normal_user, unit_with_fouling)
    run = AnalysisRun.objects.get(pk=res.data["analysis_run_id"])

    assert run.settings_snapshot
    assert run.settings_snapshot["fouling_threshold"] == 60
    assert run.model_version_dp is not None
    assert run.model_version_st is not None
    assert run.cluster_definition is not None
    assert run.executed_by is not None
    assert run.data_stats["row_valid"] > 0


def test_model_versions_are_created_and_activated(api, normal_user, unit_with_fouling):
    start_analysis(api, normal_user, unit_with_fouling)

    versions = ModelVersion.objects.filter(unit=unit_with_fouling)
    assert versions.count() == 2
    assert versions.filter(is_active=True).count() == 2
    assert all(v.residual_std > 0 for v in versions)


def test_fouling_points_are_saved_with_overall_and_clusters(api, normal_user, unit_with_fouling):
    res = start_analysis(api, normal_user, unit_with_fouling)
    run_id = res.data["analysis_run_id"]

    points = FoulingIndexPoint.objects.filter(analysis_run_id=run_id)
    assert points.filter(cluster_key="").exists()  # 전체 집계
    assert points.exclude(cluster_key="").exists()  # 군집별


def test_ac_07_4_no_fi_outside_zero_hundred_is_stored(api, normal_user, unit_with_fouling):
    """AC-07-4: FI 가 0 미만 또는 100 초과로 저장되는 경우가 없다."""
    res = start_analysis(api, normal_user, unit_with_fouling)

    points = FoulingIndexPoint.objects.filter(analysis_run_id=res.data["analysis_run_id"])
    assert not points.filter(fi_value__lt=0).exists()
    assert not points.filter(fi_value__gt=100).exists()


def test_fi_drops_after_cleaning_event(api, normal_user, unit_with_fouling):
    """세정 이후 FI 가 회복되어야 한다 (G1)."""
    res = start_analysis(api, normal_user, unit_with_fouling)
    points = (
        FoulingIndexPoint.objects.filter(
            analysis_run_id=res.data["analysis_run_id"], cluster_key=""
        )
        .exclude(fi_value__isnull=True)
        .order_by("date")
    )
    values = [p.fi_value for p in points]

    assert max(values) > 20
    assert min(values) < max(values) * 0.5


def test_settings_override_is_applied_and_snapshotted(api, normal_user, unit_with_fouling):
    res = start_analysis(
        api, normal_user, unit_with_fouling, settings_override={"fouling_threshold": 45}
    )

    run = AnalysisRun.objects.get(pk=res.data["analysis_run_id"])
    assert run.settings_snapshot["fouling_threshold"] == 45


# --- 결과 조회 엔드포인트 ---


def test_result_endpoints_return_data(api, normal_user, unit_with_fouling):
    res = start_analysis(api, normal_user, unit_with_fouling)
    run_id = res.data["analysis_run_id"]

    fi = api.get(f"{ANALYSIS_URL}{run_id}/fouling-index/")
    quality = api.get(f"{ANALYSIS_URL}{run_id}/data-quality/")
    metrics = api.get(f"{ANALYSIS_URL}{run_id}/model-metrics/")
    clusters = api.get(f"{ANALYSIS_URL}{run_id}/clusters/")
    residuals = api.get(f"{ANALYSIS_URL}{run_id}/residuals/")

    assert fi.status_code == 200 and len(fi.data) > 0
    assert quality.data["row_valid"] > 0
    assert quality.data["excluded_by_reason"]
    assert metrics.data["dp"]["metrics"]["r2"] is not None
    assert len(clusters.data) > 0
    assert len(residuals.data) > 0


def test_fouling_index_defaults_to_overall_series(api, normal_user, unit_with_fouling):
    """차트 데이터는 일 단위 집계로만 반환한다 (specs/18 §1)."""
    res = start_analysis(api, normal_user, unit_with_fouling)
    run_id = res.data["analysis_run_id"]

    rows = api.get(f"{ANALYSIS_URL}{run_id}/fouling-index/").data

    assert all(row["cluster_key"] == "" for row in rows)
    dates = [row["date"] for row in rows]
    assert len(dates) == len(set(dates))


def test_only_admin_can_delete_run(api, normal_user, admin_user, unit_with_fouling):
    res = start_analysis(api, normal_user, unit_with_fouling)
    run_id = res.data["analysis_run_id"]

    assert api.delete(f"{ANALYSIS_URL}{run_id}/").status_code == 403

    api.force_authenticate(admin_user)
    assert api.delete(f"{ANALYSIS_URL}{run_id}/").status_code == 204


def test_run_list_filters_by_unit(api, normal_user, unit_with_fouling):
    start_analysis(api, normal_user, unit_with_fouling)

    res = api.get(ANALYSIS_URL, {"unit_id": unit_with_fouling.id})

    assert res.data["count"] == 1


# --- Phase 4 : 추세 / 편익 ---


def test_trend_and_benefit_are_produced(api, normal_user, unit_with_fouling):
    res = start_analysis(api, normal_user, unit_with_fouling)
    run = AnalysisRun.objects.get(pk=res.data["analysis_run_id"])

    assert run.trend is not None
    assert run.trend.status in {
        "OK",
        "ALREADY_EXCEEDED",
        "NO_TREND",
        "BEYOND_HORIZON",
        "INSUFFICIENT_DATA",
    }
    assert run.benefit is not None
    assert run.benefit.params_snapshot


def test_summary_fields_include_dday_and_net_benefit(api, normal_user, unit_with_fouling):
    res = start_analysis(api, normal_user, unit_with_fouling)
    run = AnalysisRun.objects.get(pk=res.data["analysis_run_id"])

    assert run.result_net_benefit is not None
    # D-day 는 추세가 확인될 때만 채워진다.
    assert run.result_dday is None or isinstance(run.result_dday, int)


def test_trend_and_benefit_endpoints(api, normal_user, unit_with_fouling):
    res = start_analysis(api, normal_user, unit_with_fouling)
    run_id = res.data["analysis_run_id"]

    trend = api.get(f"{ANALYSIS_URL}{run_id}/trend/")
    benefit = api.get(f"{ANALYSIS_URL}{run_id}/benefit/")

    assert trend.status_code == 200
    assert "status" in trend.data
    assert benefit.status_code == 200
    assert benefit.data["power_loss_total_mw"] is not None
    assert len(benefit.data["scenarios"]) == 3
    assert len(benefit.data["sensitivity"]) == 4


def test_benefit_params_override_is_applied_and_snapshotted(api, normal_user, unit_with_fouling):
    """specs/09 §3.2 — 분석별 임시 입력값."""
    res = start_analysis(
        api,
        normal_user,
        unit_with_fouling,
        benefit_params_override={"electricity_price": 200, "cleaning_cost": 25_000_000},
    )
    run = AnalysisRun.objects.get(pk=res.data["analysis_run_id"])

    assert run.benefit.params_snapshot["electricity_price"] == 200
    assert run.benefit.params_snapshot["cleaning_cost"] == 25_000_000


def test_ac_09_2_override_does_not_change_admin_defaults(api, normal_user, unit_with_fouling):
    """AC-09-2: 분석별 임시 입력값을 바꿔도 관리자 기본 설정값은 바뀌지 않는다."""
    from units.models import Setting

    before = Setting.objects.get(key="electricity_price").value

    start_analysis(
        api, normal_user, unit_with_fouling, benefit_params_override={"electricity_price": 999}
    )

    assert Setting.objects.get(key="electricity_price").value == before


def test_negative_benefit_param_is_rejected(api, normal_user, unit_with_fouling):
    """specs/09 §8 — 파라미터 음수 입력은 400."""
    res = start_analysis(
        api, normal_user, unit_with_fouling, benefit_params_override={"cleaning_cost": -1}
    )

    assert res.status_code == 400
    assert res.data["error"]["code"] == "VALIDATION_ERROR"


def test_unknown_benefit_param_is_rejected(api, normal_user, unit_with_fouling):
    res = start_analysis(api, normal_user, unit_with_fouling, benefit_params_override={"nope": 1})

    assert res.status_code == 400


# --- 편익 재계산 (specs/15 §6) ---


def recalc(api, run_id, **params):
    return api.post(
        f"{ANALYSIS_URL}{run_id}/recalculate-benefit/",
        {"benefit_params_override": params},
        format="json",
    )


def test_recalculate_benefit_updates_without_rerunning_analysis(
    api, normal_user, unit_with_fouling
):
    res = start_analysis(api, normal_user, unit_with_fouling)
    run_id = res.data["analysis_run_id"]
    before = api.get(f"{ANALYSIS_URL}{run_id}/benefit/").data
    model_version_before = AnalysisRun.objects.get(pk=run_id).model_version_dp_id

    after = recalc(api, run_id, electricity_price=240)

    assert after.status_code == 200
    assert after.data["daily_loss_cost"] == pytest.approx(before["daily_loss_cost"] * 2)
    # 분석 자체는 재실행되지 않는다.
    assert AnalysisRun.objects.get(pk=run_id).model_version_dp_id == model_version_before


def test_recalculate_keeps_deltas_from_stored_analysis(api, normal_user, unit_with_fouling):
    res = start_analysis(api, normal_user, unit_with_fouling)
    run_id = res.data["analysis_run_id"]
    before = api.get(f"{ANALYSIS_URL}{run_id}/benefit/").data

    after = recalc(api, run_id, cleaning_cost=10_000_000)

    assert after.data["delta_dp_kpa"] == pytest.approx(before["delta_dp_kpa"])
    assert after.data["delta_stack_c"] == pytest.approx(before["delta_stack_c"])


def test_recalculate_rejects_negative_params(api, normal_user, unit_with_fouling):
    res = start_analysis(api, normal_user, unit_with_fouling)

    assert recalc(api, res.data["analysis_run_id"], outage_days=-1).status_code == 400


def test_recalculate_requires_successful_run(api, normal_user, unit):
    run = AnalysisRun.objects.create(
        unit=unit,
        period_start=timezone.now(),
        period_end=timezone.now(),
        status=RunStatus.FAILED,
    )
    api.force_authenticate(normal_user)

    assert recalc(api, run.id, electricity_price=200).status_code == 409


def test_anonymous_cannot_recalculate(api, unit):
    run = AnalysisRun.objects.create(
        unit=unit,
        period_start=timezone.now(),
        period_end=timezone.now(),
        status=RunStatus.SUCCESS,
    )

    assert recalc(api, run.id, electricity_price=200).status_code == 401
