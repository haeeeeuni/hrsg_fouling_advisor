"""기대값 모델 검증 (specs/06 §11). DB 불필요.

가장 중요한 검증은 **타깃 누설 차단**(AC-06-4)이다.
"""

import numpy as np
import pytest

from analysis.services import clustering as cl
from analysis.services import expected_model as em
from analysis.tests.factories import config, linear_fouling, steady_frame


@pytest.fixture(scope="module")
def clean_baseline():
    return steady_frame(days=30, seed=1)


# --- AC-06-4 : 타깃 누설 금지 ---


def test_ac_06_4_stack_model_never_sees_stack_temp(clean_baseline):
    """AC-06-4: 스택온도 모델 피처에 stack_temp_c 파생값이 포함되지 않는다."""
    _, names = em.build_features(clean_baseline, em.TARGET_ST, config())

    assert "stack_temp_c" not in names
    assert "delta_t" not in names


def test_dp_model_never_sees_dp_columns(clean_baseline):
    _, names = em.build_features(clean_baseline, em.TARGET_DP, config())

    assert "hrsg_gas_dp_kpa" not in names
    assert "gt_backpressure_kpa" not in names


def test_delta_t_is_off_by_default(clean_baseline):
    """정정된 specs/06 §3.3 — stack_temp_c 는 오염 지표라 대리 누설이 된다."""
    _, names = em.build_features(clean_baseline, em.TARGET_DP, config())

    assert "delta_t" not in names


def test_delta_t_can_be_enabled_explicitly(clean_baseline):
    _, names = em.build_features(clean_baseline, em.TARGET_DP, config(use_delta_t_for_dp=True))

    assert "delta_t" in names


def test_delta_t_stays_forbidden_for_stack_model_even_if_enabled(clean_baseline):
    _, names = em.build_features(clean_baseline, em.TARGET_ST, config(use_delta_t_for_dp=True))

    assert "delta_t" not in names


def test_leakage_guard_raises():
    with pytest.raises(em.TrainingFailed):
        em.assert_no_leakage(["gt_power_mw", "stack_temp_c"], em.TARGET_ST)


# --- 피처 구성 ---


def test_physically_motivated_flow_squared_is_present(clean_baseline):
    """차압은 유량 제곱에 비례한다 (specs/06 §3.3)."""
    _, names = em.build_features(clean_baseline, em.TARGET_DP, config())

    assert "flow_squared" in names


def test_only_one_flow_feature_is_used(clean_baseline):
    _, names = em.build_features(clean_baseline, em.TARGET_DP, config())

    assert len(set(names) & set(em.FLOW_FEATURES)) == 1


def test_stack_model_gets_steam_and_feedwater(clean_baseline):
    _, names = em.build_features(clean_baseline, em.TARGET_ST, config())

    assert "steam_flow_tph" in names
    assert "feedwater_temp_c" in names


def test_excluded_features_are_honoured(clean_baseline):
    _, names = em.build_features(clean_baseline, em.TARGET_DP, config(), excluded=["humidity_pct"])

    assert "humidity_pct" not in names


def test_cluster_columns_are_one_hot_encoded(clean_baseline):
    clustered = cl.cluster(clean_baseline, config()).frame

    _, names = em.build_features(clustered, em.TARGET_DP, config())

    assert any(name.startswith("load_band_") for name in names)
    assert any(name.startswith("season_") for name in names)


# --- 타깃 컬럼 대체 ---


def test_backpressure_is_used_when_dp_is_absent(clean_baseline):
    frame = clean_baseline.copy()
    frame["hrsg_gas_dp_kpa"] = np.nan

    assert em.resolve_target_column(em.TARGET_DP, frame) == "gt_backpressure_kpa"


def test_dp_is_preferred_when_present(clean_baseline):
    assert em.resolve_target_column(em.TARGET_DP, clean_baseline) == "hrsg_gas_dp_kpa"


# --- 학습 ---


def test_ac_06_1_dp_model_reaches_target_r2(clean_baseline):
    """AC-06-1: 청정 기준 기간으로 학습한 차압 모델의 검증 R² 가 0.85 이상이다."""
    model = em.train(clean_baseline, em.TARGET_DP, config())

    assert model.metrics["r2"] >= 0.85


def test_ac_06_3_same_data_and_settings_reproduce_metrics(clean_baseline):
    """AC-06-3: 같은 데이터·설정으로 재학습하면 동일한 지표가 재현된다."""
    first = em.train(clean_baseline, em.TARGET_DP, config())
    second = em.train(clean_baseline, em.TARGET_DP, config())

    assert first.metrics["r2"] == pytest.approx(second.metrics["r2"])
    assert first.residual_std == pytest.approx(second.residual_std)


def test_ac_06_2_model_records_training_context(clean_baseline):
    """AC-06-2: 학습 기간·지표·피처·하이퍼파라미터가 저장된다."""
    model = em.train(clean_baseline, em.TARGET_DP, config())

    assert model.baseline_start is not None
    assert model.baseline_end is not None
    assert model.feature_list
    assert model.hyperparams
    assert {"mae", "rmse", "r2", "mape"} <= set(model.metrics)
    assert model.training_rows > 0


def test_residual_stats_are_stored_for_fi_normalization(clean_baseline):
    """specs/06 §6 — 잔차 μ·σ 가 FI 정규화의 기준이 된다."""
    model = em.train(clean_baseline, em.TARGET_DP, config())

    assert model.residual_std > 0
    assert abs(model.residual_mean) < model.residual_std * 3


def test_cross_validation_metrics_are_attached(clean_baseline):
    model = em.train(clean_baseline, em.TARGET_DP, config())

    assert "cv_mae" in model.metrics
    assert "cv_r2" in model.metrics


def test_time_ordered_split_is_used_not_shuffle(clean_baseline):
    """시계열이므로 무작위 셔플 분할을 쓰지 않는다 (specs/06 §5)."""
    model = em.train(clean_baseline, em.TARGET_DP, config())

    # 학습 표본 수가 전체의 약 70% 여야 한다.
    assert model.training_rows == pytest.approx(len(clean_baseline) * 0.7, rel=0.05)


def test_ridge_algorithm_is_selectable(clean_baseline):
    model = em.train(clean_baseline, em.TARGET_DP, config(model_algorithm="RIDGE"))

    assert model.algorithm == "RIDGE"
    assert model.metrics["r2"] > 0.5


def test_insufficient_samples_raise(clean_baseline):
    with pytest.raises(em.TrainingFailed):
        em.train(clean_baseline.iloc[:5], em.TARGET_DP, config())


def test_missing_target_column_raises(clean_baseline):
    frame = clean_baseline.copy()
    frame["hrsg_gas_dp_kpa"] = np.nan
    frame["gt_backpressure_kpa"] = np.nan

    with pytest.raises(em.TrainingFailed):
        em.train(frame, em.TARGET_DP, config())


# --- 예측 ---


def test_prediction_tracks_clean_data(clean_baseline):
    model = em.train(clean_baseline, em.TARGET_DP, config())

    predicted = em.predict(model, clean_baseline, config())

    residual = clean_baseline.hrsg_gas_dp_kpa - predicted
    assert residual.abs().median() < 0.05


def test_fouling_shows_up_as_positive_residual():
    """오염이 진행되면 잔차가 양수로 커져야 한다 — 이 시스템의 전제."""
    cfg = config()
    baseline = steady_frame(days=30, seed=2)
    model = em.train(baseline, em.TARGET_DP, cfg)

    n_later = 30 * 24 * 6
    fouled = steady_frame(
        days=30, start="2024-03-01", fouling=linear_fouling(n_later, 1 / n_later), seed=2
    )
    residual = fouled.hrsg_gas_dp_kpa - em.predict(model, fouled, cfg)

    assert residual.iloc[:100].median() < residual.iloc[-100:].median()
    assert residual.iloc[-100:].median() > 0


# --- 지표 등급 (specs/06 §5) ---


@pytest.mark.parametrize(
    ("r2", "mae", "expected"),
    [(0.95, 1.0, "GOOD"), (0.80, 4.0, "FAIR"), (0.50, 10.0, "POOR")],
)
def test_stack_metric_grades(r2, mae, expected):
    grade = em.grade_metrics(em.TARGET_ST, {"r2": r2, "mae": mae}, 110.0, config())

    assert grade == expected


def test_dp_mae_threshold_scales_with_mean():
    good = em.grade_metrics(em.TARGET_DP, {"r2": 0.9, "mae": 0.1}, 3.0, config())
    poor = em.grade_metrics(em.TARGET_DP, {"r2": 0.9, "mae": 1.0}, 3.0, config())

    assert good == "GOOD"
    assert poor == "POOR"


def test_nan_metrics_grade_poor():
    assert em.grade_metrics(em.TARGET_DP, {"r2": float("nan"), "mae": 1.0}, 3.0, config()) == "POOR"
