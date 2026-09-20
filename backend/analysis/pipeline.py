"""분석 파이프라인 오케스트레이터 (AGENTS.md §3).

서비스들을 순서대로 호출하고 결과를 DB에 저장하는 **얇은 조립층**이다.
판정 로직은 analysis/services/* 의 순수 함수가 전부 담당한다.

    정제 → 구간분류 → 군집화 → 기대값 예측 → 오염도 지수
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

import numpy as np
import pandas as pd
from django.db import transaction
from django.utils import timezone

from analysis.models import (
    AnalysisRun,
    BaselineSource,
    BenefitResult,
    CleanBaselinePeriod,
    ClusterDefinition,
    FoulingIndexPoint,
    ModelTarget,
    ModelVersion,
    RunStatus,
    TrendForecast,
)
from analysis.services import benefit as bf
from analysis.services import cleaning, clustering
from analysis.services import expected_model as em
from analysis.services import fouling_index as fx
from analysis.services import trend as tr
from analysis.services.segmentation import classify, valid_frame
from ingestion.models import Measurement
from maintenance.models import CleaningEvent
from units.models import Unit
from units.settings_resolver import get_effective_settings
from units.standard_fields import ALL_FIELD_KEYS, DEFAULT_PHYSICAL_RANGES, resolve_ranges

logger = logging.getLogger(__name__)

STAGE_LOAD = "데이터 조회"
STAGE_CLEAN = "정제"
STAGE_SEGMENT = "구간 분류"
STAGE_CLUSTER = "군집화"
STAGE_MODEL = "기대값 예측"
STAGE_FI = "오염도 지수"
STAGE_TREND = "추세"
STAGE_BENEFIT = "편익"

MEASUREMENT_COLUMNS = ["timestamp", *[k for k in ALL_FIELD_KEYS if k != "timestamp"]]

# 편익 산출에 쓰는 설정 키 (specs/09 §3.1). 분석별 임시 override 대상이기도 하다.
BENEFIT_KEYS: tuple[str, ...] = (
    "electricity_price",
    "fuel_price",
    "cleaning_cost",
    "outage_days",
    "dp_power_loss_coeff",
    "stack_temp_loss_coeff",
    "heat_rate_penalty_coeff",
    "operating_hours_per_day",
    "capacity_factor",
    "cleaning_recovery_ratio",
    "evaluation_horizon_days",
    "discount_rate_annual",
    "planned_outage_days_ahead",
    "sensitivity_delta_pct",
)


class PipelineError(Exception):
    def __init__(self, stage: str, code: str, message: str) -> None:
        self.stage = stage
        self.code = code
        super().__init__(message)


@dataclass
class PipelineContext:
    run: AnalysisRun
    unit: Unit
    config: dict[str, Any]
    progress: Any = None  # callable(percent, stage)
    # 백테스트 전용. 이 시각 이후의 데이터·세정 이력은 **어떤 경로로도** 쓰지 않는다
    # (specs/19 §2.6 미래 정보 누설 금지, AC-19-4).
    cutoff: Any = None

    def report(self, percent: int, stage: str) -> None:
        if self.progress:
            self.progress(percent, stage)


def load_measurements(unit: Unit, start, end, cutoff=None) -> pd.DataFrame:
    """(unit, timestamp) 인덱스를 타도록 필터 순서를 유지한다 (specs/18 §1).

    cutoff 가 주어지면 그 시각 이후 데이터는 아예 읽지 않는다(백테스트 누설 차단).
    """
    if cutoff is not None:
        end = min(end, cutoff)
    rows = (
        Measurement.objects.filter(unit=unit, timestamp__gte=start, timestamp__lte=end)
        .order_by("timestamp")
        .values(*MEASUREMENT_COLUMNS)
    )
    frame = pd.DataFrame.from_records(rows, columns=MEASUREMENT_COLUMNS)
    if not frame.empty:
        # 분석은 KST 기준 naive 로 다룬다(DB 는 UTC 저장 — AGENTS.md §4).
        frame["timestamp"] = (
            pd.to_datetime(frame["timestamp"], utc=True)
            .dt.tz_convert(timezone.get_current_timezone())
            .dt.tz_localize(None)
        )
    return frame


def resolve_baseline(unit: Unit, config: dict[str, Any], frame: pd.DataFrame, cutoff=None) -> tuple:
    """청정 기준 기간 결정 (specs/06 §2).

    우선순위: 관리자 지정 → 세정 이력 기반 → 데이터 최초 N일(+경고)

    cutoff 가 주어지면 그 시각 이후에 끝나는 기준 기간과 그 이후의 세정 이력은
    '아직 일어나지 않은 일'이므로 후보에서 뺀다(AC-19-4 미래 정보 누설 금지).
    """
    warnings: list[dict[str, Any]] = []

    manual_qs = CleanBaselinePeriod.objects.filter(unit=unit, is_active=True)
    if cutoff is not None:
        manual_qs = manual_qs.filter(end_at__lte=cutoff)
    manual = list(manual_qs)
    if manual:
        periods = [(pd.Timestamp(p.start_at), pd.Timestamp(p.end_at)) for p in manual]
        return _naive(periods), BaselineSource.MANUAL, warnings

    cleaning_qs = CleaningEvent.objects.filter(unit=unit)
    if cutoff is not None:
        cleaning_qs = cleaning_qs.filter(cleaned_at__lte=cutoff)
    last_cleaning = cleaning_qs.order_by("-cleaned_at").first()
    if last_cleaning is not None:
        end_at = last_cleaning.cleaned_end_at or last_cleaning.cleaned_at
        start = pd.Timestamp(end_at) + pd.Timedelta(days=config["baseline_offset_days"])
        stop = start + pd.Timedelta(days=config["baseline_length_days"])
        return _naive([(start, stop)]), BaselineSource.AUTO_FROM_CLEANING, warnings

    warnings.append(
        {
            "code": "BASELINE_NOT_CONFIRMED",
            "message": "청정 기준 기간이 지정되지 않았습니다. 결과 신뢰도가 낮을 수 있습니다.",
        }
    )
    start = frame["timestamp"].min()
    stop = start + pd.Timedelta(days=config["baseline_length_days"])
    return [(start, stop)], BaselineSource.AUTO_FIRST_DATA, warnings


def _naive(periods: list[tuple]) -> list[tuple]:
    tz = timezone.get_current_timezone()
    out = []
    for start, stop in periods:
        start = start.tz_convert(tz).tz_localize(None) if start.tzinfo else start
        stop = stop.tz_convert(tz).tz_localize(None) if stop.tzinfo else stop
        out.append((start, stop))
    return out


def slice_baseline(frame: pd.DataFrame, periods: list[tuple]) -> pd.DataFrame:
    mask = pd.Series(False, index=frame.index)
    for start, stop in periods:
        mask |= (frame["timestamp"] >= start) & (frame["timestamp"] < stop)
    return frame[mask]


def run_analysis(
    ctx: PipelineContext, benefit_overrides: dict[str, Any] | None = None
) -> dict[str, Any]:
    """전 단계를 실행하고 결과를 저장한다."""
    started = time.monotonic()
    run, unit, config = ctx.run, ctx.unit, ctx.config
    warnings: list[dict[str, Any]] = []

    # --- 데이터 조회 ---
    ctx.report(5, STAGE_LOAD)
    frame = load_measurements(unit, run.period_start, run.period_end, ctx.cutoff)
    if frame.empty:
        raise PipelineError(STAGE_LOAD, "INSUFFICIENT_DATA", "선택 기간에 데이터가 없습니다.")

    # --- 정제 ---
    ctx.report(15, STAGE_CLEAN)
    ranges = resolve_ranges(
        config.get("physical_ranges") or DEFAULT_PHYSICAL_RANGES, unit.rated_power_mw
    )
    clean_result = cleaning.clean(frame, config, ranges)
    warnings.extend(clean_result.warnings)

    # --- 구간 분류 ---
    ctx.report(30, STAGE_SEGMENT)
    seg = classify(clean_result.frame, config)
    warnings.extend(seg.warnings)
    valid = valid_frame(seg.frame)

    if len(valid) < config["min_valid_points"]:
        raise PipelineError(
            STAGE_SEGMENT,
            "INSUFFICIENT_VALID_DATA",
            f"유효 포인트가 부족합니다({len(valid)} < {config['min_valid_points']}). "
            "분석 기간을 넓히거나 필터 임계값을 완화해 주세요.",
        )

    # --- 군집화 ---
    ctx.report(45, STAGE_CLUSTER)
    cluster_result = clustering.cluster(valid, config)
    warnings.extend(cluster_result.warnings)
    valid = cluster_result.frame

    # --- 기대값 예측 ---
    ctx.report(60, STAGE_MODEL)
    periods, source, baseline_warnings = resolve_baseline(unit, config, valid, ctx.cutoff)
    warnings.extend(baseline_warnings)
    baseline = slice_baseline(valid, periods)

    if len(baseline) < config["min_baseline_points"]:
        warnings.append(
            {
                "code": "INSUFFICIENT_BASELINE",
                "message": "청정 기준 기간의 유효 포인트가 부족합니다. 기간 확장을 검토하세요.",
                "details": {"points": len(baseline), "required": config["min_baseline_points"]},
            }
        )
    if baseline.empty:
        raise PipelineError(STAGE_MODEL, "NO_BASELINE", "청정 기준 기간에 유효 데이터가 없습니다.")

    models: dict[str, em.TrainedModel] = {}
    grades: list[str] = []
    residual_stats: dict[str, dict[str, float]] = {}
    for target, key in ((em.TARGET_DP, "dp"), (em.TARGET_ST, "st")):
        try:
            model = em.train(baseline, target, config, clean_result.excluded_features)
        except em.TrainingFailed as exc:
            raise PipelineError(STAGE_MODEL, "MODEL_TRAINING_FAILED", str(exc)) from exc
        models[key] = model
        warnings.extend(model.warnings)
        column = em.resolve_target_column(target, valid)
        grade = em.grade_metrics(target, model.metrics, float(valid[column].mean()), config)
        grades.append(grade)
        residual_stats[key] = {"mean": model.residual_mean, "std": model.residual_std}
        if grade == "POOR":
            warnings.append(
                {
                    "code": "MODEL_METRICS_POOR",
                    "message": f"{target} 모델 예측 정확도가 낮습니다. 재학습을 권장합니다.",
                    "details": {"metrics": model.metrics},
                }
            )

    dp_column = em.resolve_target_column(em.TARGET_DP, valid)
    residuals = fx.compute_residuals(
        valid,
        em.predict(models["dp"], valid, config),
        em.predict(models["st"], valid, config),
        dp_column,
    )

    # 도메인 밖 비율 — 기대값 신뢰도에 반영 (specs/06 §10)
    distance = clustering.mahalanobis_distance(valid, cluster_result.params)
    out_of_domain_ratio = float(
        (distance > config["out_of_domain_mahalanobis"]).mean() if distance.notna().any() else 0.0
    )

    # --- 오염도 지수 ---
    ctx.report(80, STAGE_FI)
    fi_result = fx.compute(residuals, config, residual_stats, grades, out_of_domain_ratio)
    warnings.extend(fi_result.warnings)

    # --- 추세 / D-day ---
    ctx.report(85, STAGE_TREND)
    last_cleaning = _last_cleaning_naive(unit, ctx.cutoff)
    trend_result = tr.forecast(fi_result.points, config, fi_result.current_fi, last_cleaning)
    warnings.extend(trend_result.warnings)

    # --- 편익 ---
    ctx.report(92, STAGE_BENEFIT)
    benefit_result = compute_benefit(
        unit=unit,
        config=config,
        valid=valid,
        fi_now=fi_result.current_fi,
        slope_per_day=trend_result.slope_per_day,
        eta_days=trend_result.eta_days,
        overrides=benefit_overrides,
    )
    warnings.extend(benefit_result.warnings)

    # --- 저장 ---
    ctx.report(96, "결과 저장")
    with transaction.atomic():
        # 백테스트는 과거 시점 재현이므로 운영 중인 군집 정의·활성 모델을 바꾸지 않는다.
        persist = ctx.cutoff is None
        cluster_def = _save_cluster_definition(unit, cluster_result, config) if persist else None
        version_dp = _save_model_version(unit, models["dp"], ModelTarget.DP) if persist else None
        version_st = (
            _save_model_version(unit, models["st"], ModelTarget.STACK_TEMP) if persist else None
        )
        _save_fouling_points(run, fi_result.points)
        _save_trend(run, trend_result)
        _save_benefit(run, benefit_result, trend_result)

        run.status = RunStatus.SUCCESS
        run.duration_sec = round(time.monotonic() - started, 2)
        run.cluster_definition = cluster_def
        run.model_version_dp = version_dp
        run.model_version_st = version_st
        run.column_mapping_version = unit.mapping_versions.order_by("-version").first()
        run.data_stats = {
            **clean_result.stats,
            **seg.stats,
            "baseline_source": source,
            "baseline_points": int(len(baseline)),
            "out_of_domain_ratio": round(out_of_domain_ratio, 4),
            "cluster_summary": cluster_result.summary.to_dict(orient="records"),
        }
        run.warnings = warnings
        run.result_fi = fi_result.current_fi
        run.result_grade = fi_result.grade or ""
        run.result_confidence = fi_result.confidence
        run.result_dday = trend_result.eta_days
        run.result_net_benefit = (
            round(benefit_result.net_benefit) if benefit_result.net_benefit is not None else None
        )
        run.benefit_params_snapshot = benefit_result.params_snapshot
        run.save()

    ctx.report(100, "완료")
    logger.info(
        "analysis finished run_id=%s fi=%s grade=%s duration=%ss",
        run.id,
        run.result_fi,
        run.result_grade,
        run.duration_sec,
    )
    return {
        "analysis_run_id": run.id,
        "current_fi": fi_result.current_fi,
        "grade": fi_result.grade,
        "confidence": fi_result.confidence,
        "eta_days": trend_result.eta_days,
        "trend_status": trend_result.status,
        "net_benefit": run.result_net_benefit,
    }


def _save_cluster_definition(unit, result, config) -> ClusterDefinition:
    version = (
        ClusterDefinition.objects.filter(unit=unit)
        .order_by("-version")
        .values_list("version", flat=True)
        .first()
        or 0
    ) + 1
    ClusterDefinition.objects.filter(unit=unit).update(is_active=False)
    return ClusterDefinition.objects.create(
        unit=unit,
        method=result.params.get("method", config["cluster_method"]),
        version=version,
        params=result.params,
        is_active=True,
    )


def _save_model_version(unit, model: em.TrainedModel, target: str) -> ModelVersion:
    version = (
        ModelVersion.objects.filter(unit=unit, target=target)
        .order_by("-version")
        .values_list("version", flat=True)
        .first()
        or 0
    ) + 1
    ModelVersion.objects.filter(unit=unit, target=target).update(is_active=False)
    return ModelVersion.objects.create(
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
        is_active=True,
    )


def _aware(value):
    if value is None:
        return None
    stamp = pd.Timestamp(value).to_pydatetime()
    return timezone.make_aware(stamp) if timezone.is_naive(stamp) else stamp


def _save_fouling_points(run: AnalysisRun, points: pd.DataFrame) -> None:
    if points.empty:
        return
    FoulingIndexPoint.objects.filter(analysis_run=run).delete()
    objects = [
        FoulingIndexPoint(
            analysis_run=run,
            date=pd.Timestamp(row["date"]).date(),
            cluster_key=row["cluster_key"] or "",
            fi_value=_clean_number(row.get("fi_value")),
            score_dp=_clean_number(row.get("score_dp")),
            score_st=_clean_number(row.get("score_st")),
            residual_dp=_clean_number(row.get("residual_dp")),
            residual_st=_clean_number(row.get("residual_st")),
            expected_dp=_clean_number(row.get("expected_dp")),
            expected_st=_clean_number(row.get("expected_st")),
            measured_dp=_clean_number(row.get("measured_dp")),
            measured_st=_clean_number(row.get("measured_st")),
            sample_count=int(row.get("sample_count") or 0),
            confidence=row.get("confidence") or "",
            grade=row.get("grade") or "",
        )
        for row in points.to_dict(orient="records")
    ]
    FoulingIndexPoint.objects.bulk_create(objects, batch_size=2000)


def _clean_number(value):
    if value is None or pd.isna(value):
        return None
    return float(value)


def build_config(unit: Unit, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    """유효 설정값 + 호기 속성 + 분석별 임시 override 를 합친 실행 설정."""
    config = get_effective_settings(unit.id)
    config.update(
        {
            "rated_power_mw": unit.rated_power_mw,
            "rated_st_power_mw": unit.rated_st_power_mw,
            "min_load_mw": unit.min_load_mw,
            "sampling_interval_min": unit.sampling_interval_min,
            "dp_source": unit.dp_source,
            "flow_source": unit.flow_source,
        }
    )
    if overrides:
        config.update(overrides)
    return config


def _last_cleaning_naive(unit: Unit, cutoff=None) -> pd.Timestamp | None:
    """추세 절단 기준이 되는 최근 세정 일자 (KST naive).

    cutoff 이후의 세정은 '아직 일어나지 않은 일'이므로 제외한다(AC-19-4).
    """
    queryset = CleaningEvent.objects.filter(unit=unit)
    if cutoff is not None:
        queryset = queryset.filter(cleaned_at__lte=cutoff)
    event = queryset.order_by("-cleaned_at").first()
    if event is None:
        return None
    at = event.cleaned_end_at or event.cleaned_at
    stamp = pd.Timestamp(at)
    if stamp.tzinfo is not None:
        stamp = stamp.tz_convert(timezone.get_current_timezone()).tz_localize(None)
    return stamp


def current_deltas(valid: pd.DataFrame, config: dict[str, Any]) -> tuple[float, float]:
    """최근 current_window_days 의 평균 잔차 = 현재 Δ차압·Δ스택온도 (specs/09 §4.1).

    군집별로 계산한 뒤 표본 수 가중 평균한다(운전 조건에 따라 손실이 다르므로).
    """
    if valid.empty or "residual_dp" not in valid.columns:
        return 0.0, 0.0

    window_days = int(config["current_window_days"])
    cutoff = valid["timestamp"].max() - pd.Timedelta(days=window_days)
    recent = valid[valid["timestamp"] > cutoff]
    if recent.empty:
        recent = valid

    grouped = recent.groupby("cluster_key", dropna=True).agg(
        dp=("residual_dp", "mean"), st=("residual_st", "mean"), n=("residual_dp", "size")
    )
    if grouped.empty:
        return 0.0, 0.0

    weights = grouped["n"].to_numpy(dtype=float)
    deltas = []
    for column in ("dp", "st"):
        values = grouped[column].to_numpy(dtype=float)
        mask = ~pd.isna(values)
        deltas.append(float(np.average(values[mask], weights=weights[mask])) if mask.any() else 0.0)
    return deltas[0], deltas[1]


def compute_benefit(
    *,
    unit: Unit,
    config: dict[str, Any],
    valid: pd.DataFrame,
    fi_now: float | None,
    slope_per_day: float | None,
    eta_days: int | None,
    overrides: dict[str, Any] | None = None,
) -> bf.BenefitResult:
    """편익 산출. overrides 는 이 분석에만 적용되고 관리자 기본값을 바꾸지 않는다."""
    params = {key: config[key] for key in BENEFIT_KEYS if key in config}
    if overrides:
        params.update({k: v for k, v in overrides.items() if k in BENEFIT_KEYS})

    delta_dp, delta_stack = current_deltas(valid, config)
    avg_st = float(valid["st_power_mw"].mean()) if "st_power_mw" in valid.columns else None
    avg_fuel = float(valid["fuel_flow"].mean()) if "fuel_flow" in valid.columns else None

    return bf.compute(
        delta_dp=delta_dp,
        delta_stack=delta_stack,
        fi_now=fi_now or 0.0,
        slope_per_day=slope_per_day or 0.0,
        params=params,
        rated_gt_mw=unit.rated_power_mw,
        rated_st_mw=unit.rated_st_power_mw,
        eta_days=eta_days,
        avg_st_power_mw=avg_st if avg_st and not pd.isna(avg_st) else None,
        avg_fuel_flow=avg_fuel if avg_fuel and not pd.isna(avg_fuel) else None,
    )


def _save_trend(run: AnalysisRun, result: tr.TrendResult) -> None:
    TrendForecast.objects.update_or_create(
        analysis_run=run,
        defaults={
            "model_type": result.model_type or "",
            "fit_start": result.fit_start.date() if result.fit_start is not None else None,
            "fit_end": result.fit_end.date() if result.fit_end is not None else None,
            "coefficients": result.coefficients,
            "slope_per_day": result.slope_per_day,
            "r2": _finite(result.r2),
            "mae": _finite(result.mae),
            "p_value": _finite(result.p_value),
            "threshold_used": result.threshold_used,
            "current_fi": result.current_fi,
            "eta_date": _date(result.eta_date),
            "eta_days": result.eta_days,
            "eta_lower_date": _date(result.eta_lower_date),
            "eta_upper_date": _date(result.eta_upper_date),
            "caution_eta_date": _date(result.caution_eta_date),
            "warning_eta_date": _date(result.warning_eta_date),
            "exceeded_days": result.exceeded_days,
            "weekly_increase": result.weekly_increase,
            "days_since_cleaning": result.days_since_cleaning,
            "uncertain": result.uncertain,
            "status": result.status,
            "message": result.message[:200],
        },
    )


def _save_benefit(run: AnalysisRun, result: bf.BenefitResult, trend_result: tr.TrendResult) -> None:
    recommended_date = None
    if result.recommended_offset_days is not None:
        recommended_date = timezone.localdate() + timedelta(
            days=int(result.recommended_offset_days)
        )

    BenefitResult.objects.update_or_create(
        analysis_run=run,
        defaults={
            "params_snapshot": result.params_snapshot,
            "delta_dp_kpa": result.delta_dp_kpa,
            "delta_stack_c": result.delta_stack_c,
            "power_loss_gt_mw": result.power_loss_gt_mw,
            "power_loss_st_mw": result.power_loss_st_mw,
            "power_loss_total_mw": result.power_loss_total_mw,
            "daily_loss_cost": result.daily_loss_cost,
            "daily_fuel_loss": result.daily_fuel_loss,
            "cleaning_cost": result.cleaning_cost,
            "outage_loss": result.outage_loss,
            "total_cleaning_cost": result.total_cleaning_cost,
            "gross_benefit": result.gross_benefit,
            "gross_benefit_simple": result.gross_benefit_simple,
            "net_benefit": result.net_benefit,
            "payback_days": result.payback_days,
            "roi_pct": result.roi_pct,
            "recommended_offset_days": result.recommended_offset_days,
            "recommended_cleaning_date": recommended_date,
            "recommended_net_benefit": result.recommended_net_benefit,
            "scenarios": result.scenarios,
            "sensitivity": result.sensitivity,
            "warnings": result.warnings,
        },
    )


def _finite(value):
    if value is None or not np.isfinite(value):
        return None
    return float(value)


def _date(value):
    return pd.Timestamp(value).date() if value is not None else None


def recalculate_benefit_for_run(run: AnalysisRun, overrides: dict[str, Any]) -> Any:
    """저장된 분석 결과에서 편익만 다시 계산한다 (specs/15 §6).

    분석을 재실행하지 않으므로 Δ차압·Δ스택온도와 추세 기울기는 이미 저장된 값을 쓴다.
    """
    from analysis.models import BenefitResult as BenefitRow

    config = build_config(run.unit)
    config.update(run.settings_snapshot or {})

    stored = getattr(run, "benefit", None)
    forecast = getattr(run, "trend", None)
    if stored is None:
        raise PipelineError(STAGE_BENEFIT, "NO_BENEFIT", "편익 결과가 없습니다.")

    params = {key: config[key] for key in BENEFIT_KEYS if key in config}
    params.update({k: v for k, v in (overrides or {}).items() if k in BENEFIT_KEYS})

    result = bf.compute(
        delta_dp=stored.delta_dp_kpa or 0.0,
        delta_stack=stored.delta_stack_c or 0.0,
        fi_now=run.result_fi or 0.0,
        slope_per_day=(forecast.slope_per_day if forecast else 0.0) or 0.0,
        params=params,
        rated_gt_mw=run.unit.rated_power_mw,
        rated_st_mw=run.unit.rated_st_power_mw,
        eta_days=forecast.eta_days if forecast else None,
        avg_fuel_flow=(stored.params_snapshot or {}).get("_avg_fuel_flow"),
    )

    _save_benefit(run, result, forecast)
    run.result_net_benefit = round(result.net_benefit) if result.net_benefit is not None else None
    run.benefit_params_snapshot = result.params_snapshot
    run.save(update_fields=["result_net_benefit", "benefit_params_snapshot"])
    return BenefitRow.objects.get(analysis_run=run)
