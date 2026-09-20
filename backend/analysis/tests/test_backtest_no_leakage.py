"""백테스트 미래 정보 누설 검증 (AC-19-4). PostgreSQL 필요.

specs/19 §2.6 — 컷오프 이후의 **데이터·세정 이력·청정 기준 기간**이 모델 학습이나
추세 적합에 어떤 경로로도 들어가면 안 된다. 이 파일은 그 경로를 하나씩 막는다.
"""

from __future__ import annotations

import pandas as pd
import pytest
from django.utils import timezone

from analysis import pipeline
from analysis.models import AnalysisRun, CleanBaselinePeriod, RunStatus
from analysis.pipeline import PipelineContext, build_config, load_measurements, resolve_baseline
from analysis.tests.factories import sawtooth_fouling, steady_frame
from analysis.tests.test_pipeline import load_measurements as bulk_load
from ingestion.models import Measurement
from maintenance.models import CleaningEvent
from units.models import ColumnMapping, Unit

pytestmark = pytest.mark.django_db


def _aware(text: str):
    return timezone.make_aware(pd.Timestamp(text).to_pydatetime())


@pytest.fixture
def unit(db):
    u = Unit.objects.create(
        code="BT1",
        name="백테스트호기",
        rated_power_mw=160,
        min_load_mw=60,
        sampling_interval_min=10,
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


@pytest.fixture
def loaded_unit(unit, seeded):
    n = 120 * 24 * 6
    frame = steady_frame(
        days=120, start="2024-01-01", fouling=sawtooth_fouling(n, cycles=2), seed=7
    )
    bulk_load(unit, frame)
    return unit


# --- 경로 1: 데이터 조회 ---


def test_load_measurements_stops_at_cutoff(loaded_unit):
    cutoff = _aware("2024-03-01")
    frame = load_measurements(
        loaded_unit, _aware("2024-01-01"), _aware("2024-05-01"), cutoff=cutoff
    )

    assert not frame.empty
    # 컷오프 이후 타임스탬프가 단 한 건도 없어야 한다.
    assert frame["timestamp"].max() <= pd.Timestamp("2024-03-01")
    assert Measurement.objects.filter(unit=loaded_unit, timestamp__gt=cutoff).exists()


def test_load_measurements_without_cutoff_reads_everything(loaded_unit):
    frame = load_measurements(loaded_unit, _aware("2024-01-01"), _aware("2024-05-01"))

    assert frame["timestamp"].max() > pd.Timestamp("2024-03-01")


# --- 경로 2: 세정 이력 (청정 기준 기간 + 추세 절단) ---


def test_resolve_baseline_ignores_cleanings_after_cutoff(loaded_unit):
    """컷오프 뒤의 세정을 기준으로 청정 기간을 잡으면 미래를 엿본 것이 된다."""
    CleaningEvent.objects.create(unit=loaded_unit, cleaned_at=_aware("2024-01-10"))
    future = CleaningEvent.objects.create(unit=loaded_unit, cleaned_at=_aware("2024-04-10"))

    config = build_config(loaded_unit)
    frame = load_measurements(loaded_unit, _aware("2024-01-01"), _aware("2024-03-01"))

    periods, _, _ = resolve_baseline(loaded_unit, config, frame, cutoff=_aware("2024-03-01"))
    start, _ = periods[0]

    # 1/10 세정 기준이어야 하고, 4/10 세정 기준이 되어서는 안 된다.
    assert start < pd.Timestamp("2024-02-01")
    assert start < pd.Timestamp(timezone.localtime(future.cleaned_at).replace(tzinfo=None))


def test_resolve_baseline_ignores_manual_period_after_cutoff(loaded_unit):
    CleanBaselinePeriod.objects.create(
        unit=loaded_unit, start_at=_aware("2024-04-01"), end_at=_aware("2024-04-20"), is_active=True
    )
    CleaningEvent.objects.create(unit=loaded_unit, cleaned_at=_aware("2024-01-10"))

    config = build_config(loaded_unit)
    frame = load_measurements(loaded_unit, _aware("2024-01-01"), _aware("2024-03-01"))

    periods, source, _ = resolve_baseline(loaded_unit, config, frame, cutoff=_aware("2024-03-01"))

    assert source != "MANUAL"
    assert all(start < pd.Timestamp("2024-03-01") for start, _ in periods)


def test_last_cleaning_for_trend_ignores_future_cleaning(loaded_unit):
    """추세 절단 기준도 컷오프 이전 세정만 본다 (specs/08 §3)."""
    CleaningEvent.objects.create(unit=loaded_unit, cleaned_at=_aware("2024-01-10"))
    CleaningEvent.objects.create(unit=loaded_unit, cleaned_at=_aware("2024-04-10"))

    with_cutoff = pipeline._last_cleaning_naive(loaded_unit, cutoff=_aware("2024-03-01"))
    without = pipeline._last_cleaning_naive(loaded_unit)

    assert with_cutoff == pd.Timestamp("2024-01-10")
    assert without == pd.Timestamp("2024-04-10")


# --- 경로 3: 전체 파이프라인 ---


def test_ac_19_4_pipeline_uses_no_data_after_cutoff(loaded_unit):
    """컷오프 실행의 FI 시계열 마지막 지점이 컷오프를 넘지 않는다."""
    CleaningEvent.objects.create(unit=loaded_unit, cleaned_at=_aware("2024-01-10"))
    cutoff = _aware("2024-03-01")

    run = AnalysisRun.objects.create(
        unit=loaded_unit,
        period_start=_aware("2024-01-01"),
        # 기간을 일부러 컷오프 뒤까지 넓게 잡아도 컷오프가 이긴다.
        period_end=_aware("2024-05-01"),
        status=RunStatus.RUNNING,
    )
    ctx = PipelineContext(
        run=run, unit=loaded_unit, config=build_config(loaded_unit), cutoff=cutoff
    )
    pipeline.run_analysis(ctx)

    last_point = run.fouling_points.order_by("-date").first()
    assert last_point is not None
    assert last_point.date <= timezone.localtime(cutoff).date()


def test_backtest_run_does_not_touch_operational_models(loaded_unit):
    """백테스트는 운영 중인 군집 정의·활성 모델 버전을 만들지 않는다 (specs/19 §2.6)."""
    from analysis.models import ClusterDefinition, ModelVersion

    CleaningEvent.objects.create(unit=loaded_unit, cleaned_at=_aware("2024-01-10"))
    before_models = ModelVersion.objects.count()
    before_clusters = ClusterDefinition.objects.count()

    run = AnalysisRun.objects.create(
        unit=loaded_unit,
        period_start=_aware("2024-01-01"),
        period_end=_aware("2024-03-01"),
        status=RunStatus.RUNNING,
    )
    ctx = PipelineContext(
        run=run,
        unit=loaded_unit,
        config=build_config(loaded_unit),
        cutoff=_aware("2024-03-01"),
    )
    pipeline.run_analysis(ctx)

    assert ModelVersion.objects.count() == before_models
    assert ClusterDefinition.objects.count() == before_clusters
    run.refresh_from_db()
    assert run.model_version_dp is None
    assert run.cluster_definition is None


def test_cutoff_result_differs_from_full_run(loaded_unit):
    """컷오프가 실제로 결과를 바꾸는지 — 인자가 조용히 무시되고 있지 않음을 보장한다."""
    CleaningEvent.objects.create(unit=loaded_unit, cleaned_at=_aware("2024-01-10"))

    def _run(cutoff):
        run = AnalysisRun.objects.create(
            unit=loaded_unit,
            period_start=_aware("2024-01-01"),
            period_end=_aware("2024-05-01"),
            status=RunStatus.RUNNING,
        )
        ctx = PipelineContext(
            run=run, unit=loaded_unit, config=build_config(loaded_unit), cutoff=cutoff
        )
        pipeline.run_analysis(ctx)
        run.refresh_from_db()
        return run

    cut = _run(_aware("2024-03-01"))
    full = _run(None)

    assert cut.fouling_points.count() < full.fouling_points.count()
