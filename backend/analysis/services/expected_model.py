"""기대 차압·기대 스택온도 예측 모델 (specs/06).

"같은 운전 조건에서 **청정 상태**라면 나왔어야 할 값"을 예측한다.
실측값과의 차이(잔차)가 오염의 직접 신호다.

순수 함수 모듈 — Django 모델을 import 하지 않는다.
청정 기준 기간의 **결정**은 호출부(pipeline)가 하고, 여기는 (start, end) 목록을 입력으로 받는다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from common.constants import RANDOM_SEED

TARGET_DP = "DP"
TARGET_ST = "STACK_TEMP"

ALGO_RIDGE = "RIDGE"
ALGO_GBR = "GBR"

# 타깃별 실제 컬럼
TARGET_COLUMN = {TARGET_DP: "hrsg_gas_dp_kpa", TARGET_ST: "stack_temp_c"}
TARGET_COLUMN_FALLBACK = {TARGET_DP: "gt_backpressure_kpa"}

# 공통 기저 피처 (specs/06 §3.2)
BASE_FEATURES = ("gt_power_mw", "ambient_temp_c", "gt_exhaust_temp_c")
FLOW_FEATURES = ("exhaust_flow", "fuel_flow", "igv_position_pct")
OPTIONAL_FEATURES = ("ambient_pressure_kpa", "humidity_pct")
ST_ONLY_FEATURES = ("steam_flow_tph", "feedwater_temp_c")

# 타깃 누설 금지 (specs/06 §3.3) — 각 타깃에서 절대 피처가 될 수 없는 컬럼
FORBIDDEN_FEATURES: dict[str, tuple[str, ...]] = {
    TARGET_DP: ("hrsg_gas_dp_kpa", "gt_backpressure_kpa"),
    # stack_temp_c 파생값(delta_t 포함)은 MODEL_ST 에서 전면 금지
    TARGET_ST: ("stack_temp_c", "delta_t"),
}


class TrainingFailed(Exception):
    """수치 불안정 등으로 학습에 실패."""


@dataclass
class TrainedModel:
    target: str
    algorithm: str
    pipeline: Any
    feature_list: list[str]
    hyperparams: dict[str, Any]
    metrics: dict[str, float]
    residual_mean: float
    residual_std: float
    training_rows: int
    baseline_start: pd.Timestamp | None = None
    baseline_end: pd.Timestamp | None = None
    warnings: list[dict[str, Any]] = field(default_factory=list)


def resolve_target_column(target: str, frame: pd.DataFrame) -> str | None:
    """타깃 컬럼을 고른다. 차압이 없으면 GT 배압으로 대체한다 (specs/06 §3.1)."""
    primary = TARGET_COLUMN[target]
    if primary in frame.columns and frame[primary].notna().any():
        return primary
    fallback = TARGET_COLUMN_FALLBACK.get(target)
    if fallback and fallback in frame.columns and frame[fallback].notna().any():
        return fallback
    return None


def build_features(
    frame: pd.DataFrame,
    target: str,
    config: dict[str, Any],
    excluded: list[str] | None = None,
) -> tuple[pd.DataFrame, list[str]]:
    """타깃별 피처 행렬을 만든다.

    **타깃 누설 금지**가 이 함수의 가장 중요한 책임이다(AC-06-4).
    """
    excluded = set(excluded or [])
    forbidden = set(FORBIDDEN_FEATURES[target])
    out = pd.DataFrame(index=frame.index)

    def add(name: str, values: pd.Series) -> None:
        if name in forbidden or name in excluded:
            return
        out[name] = values

    for column in BASE_FEATURES:
        if column in frame.columns:
            add(column, frame[column])

    # 유량 계열은 사용 가능한 것 중 하나만 쓴다 (specs/06 §3.2)
    def flow_usable(name: str) -> bool:
        return name in frame.columns and name not in excluded and frame[name].notna().any()

    flow_column = next((c for c in FLOW_FEATURES if flow_usable(c)), None)
    if flow_column:
        add(flow_column, frame[flow_column])
        # 차압은 유량 제곱에 비례한다 — 물리적 근거가 있는 파생 피처 (specs/06 §3.3)
        add("flow_squared", frame[flow_column] ** 2)

    for column in OPTIONAL_FEATURES:
        if column in frame.columns and frame[column].notna().any():
            add(column, frame[column])

    if target == TARGET_ST:
        for column in ST_ONLY_FEATURES:
            if column in frame.columns and frame[column].notna().any():
                add(column, frame[column])

    if "gt_power_mw" in frame.columns and config.get("rated_power_mw"):
        add("load_ratio", frame["gt_power_mw"] / config["rated_power_mw"])

    # delta_t 는 기본 비활성 — stack_temp_c 가 오염 지표라 대리 누설이 된다 (specs/06 §3.3)
    if (
        target == TARGET_DP
        and config.get("use_delta_t_for_dp")
        and {"gt_exhaust_temp_c", "stack_temp_c"} <= set(frame.columns)
    ):
        out["delta_t"] = frame["gt_exhaust_temp_c"] - frame["stack_temp_c"]

    # 규칙 기반 군집을 쓰면 부하대·계절을 원-핫으로 넣는다
    for column in ("load_band", "season"):
        if column in frame.columns and frame[column].notna().any():
            dummies = pd.get_dummies(frame[column], prefix=column, dtype=float)
            out = pd.concat([out, dummies], axis=1)

    assert_no_leakage(list(out.columns), target)
    return out, list(out.columns)


def assert_no_leakage(feature_names: list[str], target: str) -> None:
    """피처 목록에 금지 항목이 섞이지 않았는지 검사한다 (AC-06-4)."""
    forbidden = set(FORBIDDEN_FEATURES[target])
    leaked = [name for name in feature_names if name in forbidden]
    if leaked:
        raise TrainingFailed(f"{target} 모델에 타깃 누설 피처가 포함되었습니다: {leaked}")


def _make_pipeline(algorithm: str, config: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
    from sklearn.ensemble import HistGradientBoostingRegressor
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import Ridge
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import PolynomialFeatures, StandardScaler

    if algorithm == ALGO_RIDGE:
        hyperparams = {
            "alpha": config.get("ridge_alpha", 1.0),
            "poly_degree": config.get("ridge_poly_degree", 2),
        }
        pipeline = Pipeline(
            [
                ("impute", SimpleImputer(strategy="median")),
                ("poly", PolynomialFeatures(degree=hyperparams["poly_degree"], include_bias=False)),
                ("scale", StandardScaler()),
                ("model", Ridge(alpha=hyperparams["alpha"], random_state=RANDOM_SEED)),
            ]
        )
        return pipeline, hyperparams

    hyperparams = dict(config.get("gbr_hyperparams") or {})
    hyperparams.setdefault("max_iter", 300)
    hyperparams.setdefault("learning_rate", 0.05)
    hyperparams.setdefault("max_depth", 3)
    hyperparams.setdefault("min_samples_leaf", 20)
    pipeline = Pipeline(
        [
            (
                "model",
                HistGradientBoostingRegressor(random_state=RANDOM_SEED, **hyperparams),
            )
        ]
    )
    return pipeline, hyperparams


def _metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

    mae = float(mean_absolute_error(y_true, y_pred))
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    r2 = float(r2_score(y_true, y_pred)) if len(y_true) > 1 else float("nan")
    denominator = np.where(np.abs(y_true) < 1e-9, np.nan, np.abs(y_true))
    mape = float(np.nanmean(np.abs((y_true - y_pred) / denominator)) * 100)
    return {"mae": mae, "rmse": rmse, "r2": r2, "mape": mape}


def train(
    baseline_frame: pd.DataFrame,
    target: str,
    config: dict[str, Any],
    excluded_features: list[str] | None = None,
) -> TrainedModel:
    """청정 기준 기간 데이터로 학습한다 (specs/06 §5).

    시계열이므로 **무작위 셔플 분할을 쓰지 않는다.** 시간 순 70/30 분할 + TimeSeriesSplit CV.
    """
    from sklearn.model_selection import TimeSeriesSplit

    warnings: list[dict[str, Any]] = []
    target_column = resolve_target_column(target, baseline_frame)
    if target_column is None:
        raise TrainingFailed(f"{target} 타깃 컬럼을 찾을 수 없습니다.")

    frame = baseline_frame.sort_values("timestamp")
    features, feature_names = build_features(frame, target, config, excluded_features)

    y_all = frame[target_column]
    usable = y_all.notna() & features.notna().any(axis=1)
    features, y_all = features[usable], y_all[usable]

    if len(features) < 20:
        raise TrainingFailed("학습 표본이 부족합니다.")

    split = int(len(features) * 0.7)
    x_train, x_valid = features.iloc[:split], features.iloc[split:]
    y_train, y_valid = y_all.iloc[:split], y_all.iloc[split:]

    algorithm = config.get("model_algorithm", ALGO_GBR)
    try:
        pipeline, hyperparams = _make_pipeline(algorithm, config)
        pipeline.fit(x_train, y_train)
    except Exception as exc:  # noqa: BLE001 - 어떤 수치 오류든 RIDGE 로 폴백한다.
        if algorithm == ALGO_RIDGE:
            raise TrainingFailed(str(exc)) from exc
        warnings.append(
            {
                "code": "ALGORITHM_FALLBACK",
                "message": "기대값 모델 학습에 실패해 RIDGE 로 전환했습니다.",
                "details": {"reason": str(exc)},
            }
        )
        algorithm = ALGO_RIDGE
        pipeline, hyperparams = _make_pipeline(algorithm, config)
        pipeline.fit(x_train, y_train)

    y_pred = pipeline.predict(x_valid)
    metrics = _metrics(y_valid.to_numpy(), y_pred)

    # 교차검증 지표 병기 (specs/06 §5)
    cv_maes, cv_r2s = [], []
    if len(features) >= 60:
        for train_idx, test_idx in TimeSeriesSplit(n_splits=5).split(features):
            fold, _ = _make_pipeline(algorithm, config)
            try:
                fold.fit(features.iloc[train_idx], y_all.iloc[train_idx])
                fold_metrics = _metrics(
                    y_all.iloc[test_idx].to_numpy(), fold.predict(features.iloc[test_idx])
                )
            except Exception:  # noqa: BLE001 - 폴드 실패는 건너뛴다.
                continue
            cv_maes.append(fold_metrics["mae"])
            cv_r2s.append(fold_metrics["r2"])
    if cv_maes:
        metrics["cv_mae"] = float(np.mean(cv_maes))
        metrics["cv_r2"] = float(np.nanmean(cv_r2s))

    # 정규화 기준이 되는 잔차 통계 — FI 산출의 분모다 (specs/06 §6)
    residuals = y_valid.to_numpy() - y_pred
    residual_std = float(np.std(residuals, ddof=1)) if len(residuals) > 1 else 0.0
    residual_std = max(residual_std, 1e-6)  # σ≈0 하한 (specs/07 §7)

    return TrainedModel(
        target=target,
        algorithm=algorithm,
        pipeline=pipeline,
        feature_list=feature_names,
        hyperparams=hyperparams,
        metrics=metrics,
        residual_mean=float(np.mean(residuals)),
        residual_std=residual_std,
        training_rows=int(len(x_train)),
        baseline_start=frame["timestamp"].min(),
        baseline_end=frame["timestamp"].max(),
        warnings=warnings,
    )


def predict(model: TrainedModel, frame: pd.DataFrame, config: dict[str, Any]) -> pd.Series:
    """학습된 모델로 기대값을 예측한다. 피처 구성은 학습 때와 동일해야 한다."""
    features, _ = build_features(frame, model.target, config)

    # 학습에 없던 컬럼은 버리고, 빠진 컬럼은 0 으로 채워 순서를 맞춘다.
    features = features.reindex(columns=model.feature_list, fill_value=0.0)

    predictions = np.full(len(frame), np.nan)
    usable = features.notna().any(axis=1).to_numpy()
    if usable.any():
        predictions[usable] = model.pipeline.predict(features[usable])
    return pd.Series(predictions, index=frame.index)


def grade_metrics(target: str, metrics: dict[str, float], mean_value: float, config: dict) -> str:
    """양호 / 주의 / 불량 배지 (specs/06 §5)."""
    r2 = metrics.get("r2", float("nan"))
    mae = metrics.get("mae", float("nan"))

    if target == TARGET_ST:
        mae_good = config["mae_stack_good_c"]
        mae_warn = config["mae_stack_warn_c"]
    else:
        mae_good = mean_value * config["mae_dp_good_pct"] / 100
        mae_warn = mean_value * config["mae_dp_warn_pct"] / 100

    if np.isnan(r2) or np.isnan(mae):
        return "POOR"
    if r2 >= config["r2_good"] and mae <= mae_good:
        return "GOOD"
    if r2 >= config["r2_warn"] and mae <= mae_warn:
        return "FAIR"
    return "POOR"
