"""오염도 추세 예측 및 임계치 도달 예상일 (specs/08).

FI_daily 시계열의 진행 추세를 모델링해 임계치 도달 예상일(D-day)을 산출한다.

**가장 중요한 규칙: 추세 구간은 최근 세정 이후로 절단한다.**
오염은 세정에서 리셋되므로 세정 전후를 섞으면 기울기가 무의미해진다(AC-08-3).

순수 함수 모듈 — Django 모델을 import 하지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

MODEL_LINEAR = "LINEAR"
MODEL_ROBUST = "ROBUST"
MODEL_EXPONENTIAL = "EXPONENTIAL"
MODEL_AUTO = "AUTO"

STATUS_OK = "OK"
STATUS_ALREADY_EXCEEDED = "ALREADY_EXCEEDED"
STATUS_NO_TREND = "NO_TREND"
STATUS_BEYOND_HORIZON = "BEYOND_HORIZON"
STATUS_INSUFFICIENT_DATA = "INSUFFICIENT_DATA"

# 단순한 모델을 우선하는 순서 (동률일 때 앞쪽을 고른다 — specs/08 §4)
MODEL_PREFERENCE = (MODEL_LINEAR, MODEL_ROBUST, MODEL_EXPONENTIAL)

Z95 = 1.959963984540054


@dataclass
class TrendFit:
    model_type: str
    predict: Any  # callable(t_days) -> FI
    coefficients: dict[str, float]
    slope_per_day: float
    r2: float
    mae: float
    validation_mae: float
    p_value: float
    residual_std: float


@dataclass
class TrendResult:
    status: str
    model_type: str | None = None
    fit_start: pd.Timestamp | None = None
    fit_end: pd.Timestamp | None = None
    coefficients: dict[str, float] = field(default_factory=dict)
    slope_per_day: float | None = None
    r2: float | None = None
    mae: float | None = None
    p_value: float | None = None
    threshold_used: float | None = None
    current_fi: float | None = None
    eta_date: pd.Timestamp | None = None
    eta_days: int | None = None
    eta_lower_date: pd.Timestamp | None = None
    eta_upper_date: pd.Timestamp | None = None
    caution_eta_date: pd.Timestamp | None = None
    warning_eta_date: pd.Timestamp | None = None
    exceeded_days: int | None = None
    weekly_increase: float | None = None
    days_since_cleaning: int | None = None
    uncertain: bool = False
    message: str = ""
    warnings: list[dict[str, Any]] = field(default_factory=list)


# --- 추세 구간 결정 (specs/08 §3) ---


def select_window(
    daily: pd.DataFrame,
    last_cleaning: pd.Timestamp | None,
    config: dict[str, Any],
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    """추세 적합에 쓸 구간을 고른다.

    1) 최근 세정 이후만 사용한다.
    2) 세정 이력이 없으면 최근 trend_window_days 구간.
    """
    warnings: list[dict[str, Any]] = []
    if daily.empty:
        return daily, warnings

    frame = daily.dropna(subset=["fi_value"]).sort_values("date").copy()
    frame["date"] = pd.to_datetime(frame["date"])

    if last_cleaning is not None:
        cutoff = pd.Timestamp(last_cleaning).normalize()
        trimmed = frame[frame["date"] > cutoff]
        if len(trimmed) < len(frame):
            warnings.append(
                {
                    "code": "TREND_TRIMMED_AT_CLEANING",
                    "message": "추세 구간을 최근 세정 이후로 잘랐습니다.",
                    "details": {"cleaned_at": cutoff.date().isoformat()},
                }
            )
        frame = trimmed
    else:
        window_start = frame["date"].max() - pd.Timedelta(days=int(config["trend_window_days"]))
        frame = frame[frame["date"] >= window_start]

    return frame, warnings


# --- 개별 모델 적합 ---


def _weights(frame: pd.DataFrame) -> np.ndarray:
    """표본 수와 신뢰도를 회귀 가중치로 쓴다 (specs/08 §4)."""
    counts = frame.get("sample_count")
    weights = (
        counts.to_numpy(dtype=float) if counts is not None else np.ones(len(frame), dtype=float)
    )
    weights = np.where(np.isfinite(weights) & (weights > 0), weights, 1.0)

    confidence = frame.get("confidence")
    if confidence is not None:
        factor = confidence.map({"HIGH": 1.0, "MEDIUM": 0.7, "LOW": 0.4}).fillna(1.0)
        weights = weights * factor.to_numpy(dtype=float)
    return weights


def _scores(y: np.ndarray, y_hat: np.ndarray, weights: np.ndarray) -> tuple[float, float]:
    residual = y - y_hat
    mae = float(np.average(np.abs(residual), weights=weights))
    total = float(np.average((y - np.average(y, weights=weights)) ** 2, weights=weights))
    explained = float(np.average(residual**2, weights=weights))
    r2 = 1 - explained / total if total > 0 else float("nan")
    return r2, mae


def fit_linear(t: np.ndarray, y: np.ndarray, weights: np.ndarray) -> TrendFit:
    from scipy import stats

    slope, intercept = np.polyfit(t, y, 1, w=np.sqrt(weights))
    predict = lambda days: intercept + slope * np.asarray(days, dtype=float)  # noqa: E731
    r2, mae = _scores(y, predict(t), weights)

    # 추세 유의성은 가중치 없는 단순 회귀의 p 값으로 판단한다.
    p_value = float(stats.linregress(t, y).pvalue) if len(t) > 2 else 1.0

    return TrendFit(
        model_type=MODEL_LINEAR,
        predict=predict,
        coefficients={"intercept": float(intercept), "slope": float(slope)},
        slope_per_day=float(slope),
        r2=r2,
        mae=mae,
        validation_mae=mae,
        p_value=p_value,
        residual_std=float(np.std(y - predict(t), ddof=1)) if len(t) > 2 else 0.0,
    )


def fit_robust(t: np.ndarray, y: np.ndarray, weights: np.ndarray) -> TrendFit:
    """Theil–Sen — 이상점에 강하다 (specs/08 §4)."""
    from scipy import stats

    result = stats.theilslopes(y, t)
    slope, intercept = float(result[0]), float(result[1])
    predict = lambda days: intercept + slope * np.asarray(days, dtype=float)  # noqa: E731
    r2, mae = _scores(y, predict(t), weights)
    p_value = float(stats.linregress(t, y).pvalue) if len(t) > 2 else 1.0

    return TrendFit(
        model_type=MODEL_ROBUST,
        predict=predict,
        coefficients={"intercept": intercept, "slope": slope},
        slope_per_day=slope,
        r2=r2,
        mae=mae,
        validation_mae=mae,
        p_value=p_value,
        residual_std=float(np.std(y - predict(t), ddof=1)) if len(t) > 2 else 0.0,
    )


def fit_exponential(t: np.ndarray, y: np.ndarray, weights: np.ndarray) -> TrendFit:
    """포화형 FI(t) = C·(1 − exp(−k·t)) — 진행이 가속/둔화하는 경우 (specs/08 §4).

    수렴에 실패하면 호출부가 선형으로 폴백한다.
    """
    from scipy.optimize import curve_fit

    def model(days, c, k):
        return c * (1 - np.exp(-k * np.asarray(days, dtype=float)))

    span = max(float(t.max()), 1.0)
    popt, _ = curve_fit(
        model,
        t,
        y,
        p0=[max(float(y.max()) * 1.5, 1.0), 1.0 / span],
        bounds=([0.0, 1e-6], [1000.0, 1.0]),
        sigma=1.0 / np.sqrt(weights),
        maxfev=5000,
    )
    c, k = float(popt[0]), float(popt[1])
    predict = lambda days: model(days, c, k)  # noqa: E731
    r2, mae = _scores(y, predict(t), weights)

    # 순간 기울기는 관측 마지막 지점 기준으로 본다.
    slope = float(c * k * np.exp(-k * t.max()))
    from scipy import stats

    p_value = float(stats.linregress(t, y).pvalue) if len(t) > 2 else 1.0

    return TrendFit(
        model_type=MODEL_EXPONENTIAL,
        predict=predict,
        coefficients={"c": c, "k": k},
        slope_per_day=slope,
        r2=r2,
        mae=mae,
        validation_mae=mae,
        p_value=p_value,
        residual_std=float(np.std(y - predict(t), ddof=1)) if len(t) > 2 else 0.0,
    )


def _validation_mae(fitter, t: np.ndarray, y: np.ndarray, weights: np.ndarray) -> float:
    """뒤쪽 30% 를 검증 구간으로 떼어 MAE 를 잰다 (시계열이므로 셔플하지 않는다)."""
    split = int(len(t) * 0.7)
    if split < 3 or len(t) - split < 2:
        return float("nan")
    try:
        fit = fitter(t[:split], y[:split], weights[:split])
    except Exception:  # noqa: BLE001 - 적합 실패는 후보에서 제외
        return float("inf")
    return float(np.mean(np.abs(y[split:] - fit.predict(t[split:]))))


def fit_all(t: np.ndarray, y: np.ndarray, weights: np.ndarray) -> list[TrendFit]:
    fits: list[TrendFit] = []
    for fitter in (fit_linear, fit_robust, fit_exponential):
        try:
            fit = fitter(t, y, weights)
        except Exception:  # noqa: BLE001 - 수렴 실패 모델은 후보에서 뺀다(specs/08 §9)
            continue
        fit.validation_mae = _validation_mae(fitter, t, y, weights)
        fits.append(fit)
    return fits


def choose(fits: list[TrendFit], preferred: str = MODEL_AUTO) -> TrendFit | None:
    """검증 MAE 최소 모델을 고르고, 동률이면 단순한 모델을 우선한다 (specs/08 §4)."""
    if not fits:
        return None
    if preferred != MODEL_AUTO:
        chosen = next((f for f in fits if f.model_type == preferred), None)
        if chosen is not None:
            return chosen

    def key(fit: TrendFit) -> tuple:
        score = fit.validation_mae if np.isfinite(fit.validation_mae) else fit.mae
        # 소수 3자리까지 같으면 동률로 보고 단순한 모델을 택한다.
        return (round(score, 3), MODEL_PREFERENCE.index(fit.model_type))

    return min(fits, key=key)


# --- D-day 산출 (specs/08 §5) ---


def solve_threshold_day(
    fit: TrendFit, threshold: float, start_day: float, max_days: float
) -> float | None:
    """FI(t*) = threshold 를 만족하는 최소 t* (t* > start_day)."""
    if fit.model_type == MODEL_EXPONENTIAL:
        c, k = fit.coefficients["c"], fit.coefficients["k"]
        if c <= threshold:
            return None  # 포화값이 임계치에 못 미친다
        target = -np.log(1 - threshold / c) / k
        return float(target) if target > start_day else None

    slope = fit.coefficients["slope"]
    if slope <= 0:
        return None
    target = (threshold - fit.coefficients["intercept"]) / slope
    return float(target) if target > start_day else None


def _band_day(
    fit: TrendFit, threshold: float, start_day: float, max_days: float, offset: float
) -> float | None:
    """예측구간을 offset 만큼 평행 이동한 곡선이 임계치를 넘는 날."""
    shifted = TrendFit(
        model_type=fit.model_type,
        predict=fit.predict,
        coefficients={**fit.coefficients},
        slope_per_day=fit.slope_per_day,
        r2=fit.r2,
        mae=fit.mae,
        validation_mae=fit.validation_mae,
        p_value=fit.p_value,
        residual_std=fit.residual_std,
    )
    if fit.model_type == MODEL_EXPONENTIAL:
        shifted.coefficients["c"] = fit.coefficients["c"] + offset
    else:
        shifted.coefficients["intercept"] = fit.coefficients["intercept"] + offset
    return solve_threshold_day(shifted, threshold, start_day, max_days)


def forecast(
    daily: pd.DataFrame,
    config: dict[str, Any],
    current_fi: float | None,
    last_cleaning: pd.Timestamp | None = None,
) -> TrendResult:
    """추세 적합 → D-day 산출 전체."""
    threshold = float(config["fouling_threshold"])
    frame, warnings = select_window(daily, last_cleaning, config)

    min_points = int(config["min_trend_points"])
    if len(frame) < min_points:
        return TrendResult(
            status=STATUS_INSUFFICIENT_DATA,
            threshold_used=threshold,
            current_fi=current_fi,
            message=(
                f"추세 예측에는 유효 일자가 {min_points}일 이상 필요합니다(현재 {len(frame)}일)."
            ),
            warnings=warnings,
        )

    fit_start = frame["date"].min()
    fit_end = frame["date"].max()
    t = (frame["date"] - fit_start).dt.days.to_numpy(dtype=float)
    y = frame["fi_value"].to_numpy(dtype=float)
    weights = _weights(frame)

    fits = fit_all(t, y, weights)
    chosen = choose(fits, config.get("trend_model", MODEL_AUTO))
    if chosen is None:
        return TrendResult(
            status=STATUS_NO_TREND,
            threshold_used=threshold,
            current_fi=current_fi,
            message="추세 모델을 적합할 수 없습니다.",
            warnings=warnings,
        )
    if len(fits) < 3:
        warnings.append(
            {
                "code": "TREND_MODEL_SKIPPED",
                "message": "일부 추세 모델이 수렴하지 않아 후보에서 제외했습니다.",
                "details": {"fitted": [f.model_type for f in fits]},
            }
        )

    last_day = float(t.max())
    fi_now = current_fi if current_fi is not None else float(chosen.predict(last_day))

    common = {
        "model_type": chosen.model_type,
        "fit_start": fit_start,
        "fit_end": fit_end,
        "coefficients": chosen.coefficients,
        "slope_per_day": chosen.slope_per_day,
        "r2": chosen.r2,
        "mae": chosen.mae,
        "p_value": chosen.p_value,
        "threshold_used": threshold,
        "current_fi": fi_now,
        "weekly_increase": chosen.slope_per_day * 7,
        "days_since_cleaning": (
            int((fit_end - pd.Timestamp(last_cleaning).normalize()).days)
            if last_cleaning is not None
            else None
        ),
        "warnings": warnings,
    }

    # 등급 전환 예상일은 상태와 무관하게 가능한 만큼 계산한다.
    max_days = float(config["max_forecast_days"])
    common["caution_eta_date"] = _to_date(
        fit_start,
        solve_threshold_day(chosen, float(config["grade_caution_min"]), last_day, max_days),
    )
    common["warning_eta_date"] = _to_date(
        fit_start,
        solve_threshold_day(chosen, float(config["grade_warning_min"]), last_day, max_days),
    )

    # 1) 이미 임계치 도달
    if fi_now >= threshold:
        exceeded = frame[frame["fi_value"] >= threshold]
        first_exceed = exceeded["date"].min() if not exceeded.empty else fit_end
        return TrendResult(
            status=STATUS_ALREADY_EXCEEDED,
            eta_days=0,
            eta_date=fit_end,
            exceeded_days=int((fit_end - first_exceed).days),
            message="이미 임계치에 도달했습니다.",
            **common,
        )

    # 2) 기울기가 0 이하이거나 통계적으로 유의하지 않음
    if chosen.slope_per_day <= 0 or chosen.p_value > float(config["trend_p_value_max"]):
        return TrendResult(
            status=STATUS_NO_TREND,
            message="도달 예측 불가 — 추세가 확인되지 않습니다.",
            **common,
        )

    target_day = solve_threshold_day(chosen, threshold, last_day, max_days)
    if target_day is None or (target_day - last_day) > max_days:
        return TrendResult(
            status=STATUS_BEYOND_HORIZON,
            message=f"{int(max_days)}일 내 도달 예상이 없습니다.",
            **common,
        )

    eta_days = int(round(target_day - last_day))
    band = Z95 * chosen.residual_std
    lower_day = _band_day(chosen, threshold, last_day, max_days, +band)  # 빠른 쪽
    upper_day = _band_day(chosen, threshold, last_day, max_days, -band)  # 늦은 쪽

    eta_lower = _to_date(fit_start, lower_day)
    eta_upper = _to_date(fit_start, upper_day)

    # 신뢰구간 폭이 D-day 의 2배를 넘으면 불확실성 높음 (specs/08 §5)
    uncertain = False
    if eta_lower is not None and eta_upper is not None:
        uncertain = (eta_upper - eta_lower).days > max(eta_days, 1) * 2

    return TrendResult(
        status=STATUS_OK,
        eta_days=eta_days,
        eta_date=_to_date(fit_start, target_day),
        eta_lower_date=eta_lower,
        eta_upper_date=eta_upper,
        uncertain=uncertain,
        **common,
    )


def _to_date(origin: pd.Timestamp, day: float | None) -> pd.Timestamp | None:
    if day is None or not np.isfinite(day):
        return None
    return (origin + pd.Timedelta(days=float(day))).normalize()
