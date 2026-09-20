"""기대값 모델 재학습 (specs/06 §8, specs/13 §5.2).

재학습 결과는 **비활성 상태로 저장**된다. 관리자가 지표를 비교하고 승인해야
활성화되며, 그 전까지 기존 활성 모델이 그대로 쓰인다(AC-06-5).
"""

from __future__ import annotations

import logging

import pandas as pd
from celery import shared_task
from django.utils import timezone

from analysis.models import CleanBaselinePeriod, ModelTarget, ModelVersion
from analysis.pipeline import build_config, load_measurements, resolve_baseline, slice_baseline
from analysis.services import cleaning, clustering
from analysis.services import expected_model as em
from analysis.services.segmentation import classify, valid_frame
from common.jobs import report_progress
from units.models import Unit
from units.standard_fields import DEFAULT_PHYSICAL_RANGES, resolve_ranges

logger = logging.getLogger(__name__)

TARGET_MAP = {ModelTarget.DP: em.TARGET_DP, ModelTarget.STACK_TEMP: em.TARGET_ST}


@shared_task(bind=True, name="analysis.retrain_models")
def retrain_models(
    self,
    unit_id: int,
    targets: list[str],
    algorithm: str | None = None,
    baseline_period_ids: list[int] | None = None,
    user_id: int | None = None,
) -> dict:
    unit = Unit.objects.get(pk=unit_id)
    config = build_config(unit)
    if algorithm:
        config["model_algorithm"] = algorithm

    report_progress(self, 10, "데이터 조회")

    # 청정 기준 기간: 명시 지정 > 자동 산정
    if baseline_period_ids:
        periods = [
            (pd.Timestamp(p.start_at), pd.Timestamp(p.end_at))
            for p in CleanBaselinePeriod.objects.filter(unit=unit, pk__in=baseline_period_ids)
        ]
        if not periods:
            raise ValueError("지정한 청정 기준 기간을 찾을 수 없습니다.")
        tz = timezone.get_current_timezone()
        periods = [
            (
                s.tz_convert(tz).tz_localize(None) if s.tzinfo else s,
                e.tz_convert(tz).tz_localize(None) if e.tzinfo else e,
            )
            for s, e in periods
        ]
        source = "MANUAL"
    else:
        periods, source = None, None

    span_start = min(s for s, _ in periods) if periods else None
    frame = load_measurements(
        unit,
        timezone.make_aware(span_start.to_pydatetime()) if span_start is not None else _first(unit),
        timezone.now(),
    )
    if frame.empty:
        raise ValueError("학습할 운전 데이터가 없습니다.")

    report_progress(self, 30, "정제")
    ranges = resolve_ranges(
        config.get("physical_ranges") or DEFAULT_PHYSICAL_RANGES, unit.rated_power_mw
    )
    clean_result = cleaning.clean(frame, config, ranges)
    valid = valid_frame(classify(clean_result.frame, config).frame)
    valid = clustering.cluster(valid, config).frame

    if periods is None:
        periods, source, _ = resolve_baseline(unit, config, valid)

    baseline = slice_baseline(valid, periods)
    if baseline.empty:
        raise ValueError("청정 기준 기간에 유효 데이터가 없습니다.")

    report_progress(self, 55, "학습")
    created = []
    for target in targets:
        model = em.train(baseline, TARGET_MAP[target], config, clean_result.excluded_features)
        version = (
            ModelVersion.objects.filter(unit=unit, target=target)
            .order_by("-version")
            .values_list("version", flat=True)
            .first()
            or 0
        ) + 1

        # 승인 전까지 비활성. 기존 활성 모델은 건드리지 않는다.
        row = ModelVersion.objects.create(
            unit=unit,
            target=target,
            algorithm=model.algorithm,
            version=version,
            baseline_start=_aware(model.baseline_start),
            baseline_end=_aware(model.baseline_end),
            feature_list=model.feature_list,
            hyperparams=model.hyperparams,
            metrics=model.metrics,
            residual_mean=model.residual_mean,
            residual_std=model.residual_std,
            training_rows=model.training_rows,
            trained_by_id=user_id,
            is_active=False,
            notes=f"수동 재학습 (baseline_source={source})",
        )
        created.append(
            {
                "id": row.pk,
                "target": target,
                "version": version,
                "algorithm": model.algorithm,
                "metrics": model.metrics,
                "is_active": False,
            }
        )

    report_progress(self, 100, "완료")
    logger.info("retrain finished unit=%s created=%s", unit.code, [c["id"] for c in created])
    return {
        "unit_id": unit.id,
        "baseline_source": source,
        "baseline_points": int(len(baseline)),
        "created": created,
        "notice": "승인(활성화) 전까지 기존 활성 모델이 그대로 사용됩니다.",
    }


def _first(unit: Unit):
    from ingestion.models import Measurement

    return (
        Measurement.objects.filter(unit=unit)
        .order_by("timestamp")
        .values_list("timestamp", flat=True)
        .first()
        or timezone.now()
    )


def _aware(value):
    if value is None:
        return None
    stamp = pd.Timestamp(value).to_pydatetime()
    return timezone.make_aware(stamp) if timezone.is_naive(stamp) else stamp
