"""세정 전후 비교 실행 (specs/12 §2).

파이프라인과 같은 정제·군집화·기대값 예측을 비교 구간에 다시 적용한다.
**세정 전후 모델 버전이 다르면 동일 버전으로 재계산해 기준을 통일한다** (specs/12 §2.6).
"""

from __future__ import annotations

import logging

import pandas as pd
from django.utils import timezone

from analysis.models import ClusterDefinition, ComparisonReport, ModelTarget, ModelVersion
from analysis.pipeline import build_config, load_measurements
from analysis.services import cleaning, clustering
from analysis.services import comparison as cmp
from analysis.services import expected_model as em
from analysis.services import fouling_index as fx
from analysis.services.segmentation import classify, valid_frame
from common.exceptions import Conflict
from maintenance.models import CleaningEvent
from units.standard_fields import DEFAULT_PHYSICAL_RANGES, resolve_ranges

logger = logging.getLogger(__name__)


def _naive(value) -> pd.Timestamp:
    stamp = pd.Timestamp(value)
    if stamp.tzinfo is not None:
        stamp = stamp.tz_convert(timezone.get_current_timezone()).tz_localize(None)
    return stamp


def _active_model(unit, target: str) -> ModelVersion | None:
    return ModelVersion.objects.filter(unit=unit, target=target, is_active=True).first()


def run_comparison(
    event: CleaningEvent,
    window_days: int = 30,
    before_offset_days: int = 0,
    after_offset_days: int = 1,
    user=None,
) -> ComparisonReport:
    unit = event.unit
    config = build_config(unit)

    windows = cmp.build_windows(
        _naive(event.cleaned_at),
        _naive(event.cleaned_end_at) if event.cleaned_end_at else None,
        window_days=window_days,
        before_offset_days=before_offset_days,
        after_offset_days=after_offset_days,
    )

    # 전/후 구간을 한 번에 불러 같은 정제·군집 기준을 적용한다.
    frame = load_measurements(
        unit,
        timezone.make_aware(windows.before_start.to_pydatetime()),
        timezone.make_aware(windows.after_end.to_pydatetime()),
    )
    if frame.empty:
        raise Conflict(code="COMPARISON_NO_DATA", message="비교 구간에 운전 데이터가 없습니다.")

    ranges = resolve_ranges(
        config.get("physical_ranges") or DEFAULT_PHYSICAL_RANGES, unit.rated_power_mw
    )
    clean_result = cleaning.clean(frame, config, ranges)
    valid = valid_frame(classify(clean_result.frame, config).frame)
    if valid.empty:
        raise Conflict(
            code="COMPARISON_NO_VALID_DATA", message="비교 구간에 유효 운전 데이터가 없습니다."
        )

    # 동일 ClusterDefinition 을 재사용해 전/후가 같은 기준으로 묶이게 한다.
    definition = ClusterDefinition.objects.filter(unit=unit, is_active=True).first()
    cluster_result = clustering.cluster(
        valid, config, params=definition.params if definition else None
    )
    valid = cluster_result.frame

    model_dp = _active_model(unit, ModelTarget.DP)
    model_st = _active_model(unit, ModelTarget.STACK_TEMP)
    warnings: list[dict] = []

    # 활성 모델이 없으면 비교 구간의 세정 후 데이터로 즉석 학습한다.
    baseline = cmp.slice_window(valid, windows.after_start, windows.after_end)
    trained = {}
    for target, key in ((em.TARGET_DP, "dp"), (em.TARGET_ST, "st")):
        try:
            trained[key] = em.train(baseline, target, config, clean_result.excluded_features)
        except em.TrainingFailed as exc:
            raise Conflict(
                code="COMPARISON_MODEL_FAILED",
                message=f"비교용 기대값 모델을 학습할 수 없습니다: {exc}",
            ) from exc

    if model_dp or model_st:
        warnings.append(
            {
                "code": "COMPARISON_MODEL_REBUILT",
                "message": (
                    "전후 비교는 동일 기준을 쓰기 위해 "
                    "세정 후 구간으로 모델을 재학습해 계산했습니다."
                ),
            }
        )

    dp_column = em.resolve_target_column(em.TARGET_DP, valid)
    residuals = fx.compute_residuals(
        valid,
        em.predict(trained["dp"], valid, config),
        em.predict(trained["st"], valid, config),
        dp_column,
    )

    # 비교표의 FI 는 포인트 단위로 계산한다(일별 집계 전).
    stats = {
        "dp": {"mean": trained["dp"].residual_mean, "std": trained["dp"].residual_std},
        "st": {"mean": trained["st"].residual_mean, "std": trained["st"].residual_std},
    }
    window_h = config["smoothing_window_h"]
    residuals["score_dp"] = fx.normalize_sigma(
        fx.smooth(residuals["residual_dp"], residuals["timestamp"], window_h),
        stats["dp"]["mean"],
        stats["dp"]["std"],
        config["sigma_ref"],
    )
    residuals["score_st"] = fx.normalize_sigma(
        fx.smooth(residuals["residual_st"], residuals["timestamp"], window_h),
        stats["st"]["mean"],
        stats["st"]["std"],
        config["sigma_ref"],
    )
    residuals["fi"], _ = fx.weighted_fi(
        residuals["score_dp"],
        residuals["score_st"],
        config["weight_dp"],
        config["weight_stack_temp"],
    )

    result = cmp.compare(residuals, windows, int(config["min_cluster_points"]))
    warnings.extend(result.warnings)

    report = ComparisonReport.objects.create(
        unit=unit,
        cleaning_event=event,
        created_by=user,
        window_days=window_days,
        before_offset_days=before_offset_days,
        after_offset_days=after_offset_days,
        before_start=timezone.make_aware(windows.before_start.to_pydatetime()),
        before_end=timezone.make_aware(windows.before_end.to_pydatetime()),
        after_start=timezone.make_aware(windows.after_start.to_pydatetime()),
        after_end=timezone.make_aware(windows.after_end.to_pydatetime()),
        model_version_dp=model_dp,
        model_version_st=model_st,
        metrics=result.metrics,
        cluster_metrics=result.cluster_metrics,
        p_values=result.p_values,
        common_clusters=result.common_clusters,
        recovery_ratio=result.recovery_ratio,
        warnings=warnings,
    )
    logger.info(
        "comparison created unit=%s event=%s clusters=%s",
        unit.code,
        event.id,
        result.common_clusters,
    )
    return report
