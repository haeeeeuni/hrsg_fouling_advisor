"""합성 데이터 빌더 — 성질 기반 검증용 (AGENTS.md §8).

의도를 하나씩 분리한 작은 시계열을 만든다. 샘플 생성기(scripts/)와 달리
"이 성질만 성립하는" 최소 데이터가 목적이다.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

DEFAULT_CONFIG: dict = {
    # 정제
    "rolling_window_h": 3,
    "mad_k": 5.0,
    "stuck_points": 30,
    "gap_fill_max_points": 3,
    "step_change_sigma": 5.0,
    "sampling_interval_min": 10,
    "max_missing_rate_pct": 50,
    # 구간
    "min_load_mw": 60,
    "rated_power_mw": 160,
    "min_analysis_load_pct": 40,
    "ramp_threshold_mw_per_min": 1.0,
    "ramp_settle_min": 30,
    "startup_settle_min": 120,
    "shutdown_lead_min": 60,
    "db_settle_min": 60,
    "stability_window_min": 30,
    "load_std_max_mw": 2.0,
    "exh_temp_std_max_c": 5.0,
    "min_segment_min": 60,
    "min_valid_points": 500,
    # 군집
    "cluster_method": "RULE",
    "load_band_edges": [40, 60, 80, 95],
    "season_definition": "MONTH",
    "kmeans_k": 4,
    "min_cluster_points": 10,
    "drop_sparse_clusters": False,
    "out_of_domain_mahalanobis": 3.0,
    # 모델
    "model_algorithm": "GBR",
    "use_delta_t_for_dp": False,
    "gbr_hyperparams": {
        "max_iter": 80,
        "learning_rate": 0.1,
        "max_depth": 3,
        "min_samples_leaf": 5,
    },
    "ridge_alpha": 1.0,
    "ridge_poly_degree": 2,
    "r2_good": 0.85,
    "r2_warn": 0.70,
    "mae_stack_good_c": 3.0,
    "mae_stack_warn_c": 6.0,
    "mae_dp_good_pct": 5.0,
    "mae_dp_warn_pct": 10.0,
    "baseline_length_days": 30,
    "baseline_offset_days": 1,
    "min_baseline_points": 100,
    # FI
    "normalization_method": "SIGMA",
    "sigma_ref": 6.0,
    "dp_ref_pct": 30,
    "st_ref_c": 15,
    "smoothing_window_h": 24,
    "current_window_days": 7,
    "weight_dp": 0.6,
    "weight_stack_temp": 0.4,
    "grade_caution_min": 30,
    "grade_warning_min": 60,
    "fouling_threshold": 60,
    # 추세 (specs/08)
    "trend_window_days": 180,
    "min_trend_points": 30,
    "max_forecast_days": 730,
    "trend_model": "AUTO",
    "trend_p_value_max": 0.05,
    # 편익 (specs/09 §3.1)
    "electricity_price": 120,
    "fuel_price": 900,
    "cleaning_cost": 30_000_000,
    "outage_days": 2.0,
    "dp_power_loss_coeff": 0.35,
    "stack_temp_loss_coeff": 0.12,
    "heat_rate_penalty_coeff": 0.30,
    "operating_hours_per_day": 20,
    "capacity_factor": 0.85,
    "cleaning_recovery_ratio": 0.9,
    "evaluation_horizon_days": 365,
    "discount_rate_annual": 0.0,
    "planned_outage_days_ahead": 180,
    "rated_st_power_mw": 80.0,
}


def config(**overrides) -> dict:
    return {**DEFAULT_CONFIG, **overrides}


def steady_frame(
    days: int = 60,
    interval_min: int = 10,
    start: str = "2024-01-01",
    fouling: np.ndarray | None = None,
    seed: int = 0,
) -> pd.DataFrame:
    """정상 정격 운전만 있는 깨끗한 시계열.

    fouling 이 주어지면 그 비율만큼 차압·스택온도를 끌어올린다(오염 주입).
    """
    rng = np.random.default_rng(seed)
    index = pd.date_range(
        start, periods=int(days * 24 * 60 / interval_min), freq=f"{interval_min}min"
    )
    n = len(index)

    if fouling is None:
        fouling = np.zeros(n)

    ambient = 15 + 8 * np.sin(2 * np.pi * np.arange(n) / (24 * 60 / interval_min))
    power = 140 + 5 * np.sin(2 * np.pi * np.arange(n) / (7 * 24 * 60 / interval_min))
    flow = 400 * (power / 160)

    dp_clean = 2.5 * (flow / 450) ** 2
    stack_clean = 95 + 12 * (power / 160) + 0.15 * ambient

    return pd.DataFrame(
        {
            "timestamp": index,
            "gt_power_mw": power + rng.normal(0, 0.3, n),
            "ambient_temp_c": ambient + rng.normal(0, 0.2, n),
            "gt_exhaust_temp_c": 560 + 60 * (power / 160) - 0.4 * ambient + rng.normal(0, 0.5, n),
            "exhaust_flow": flow + rng.normal(0, 1.0, n),
            "hrsg_gas_dp_kpa": dp_clean * (1 + 0.35 * fouling) + rng.normal(0, 0.005, n),
            "stack_temp_c": stack_clean + 14 * fouling + rng.normal(0, 0.15, n),
            "duct_burner_on": np.zeros(n, dtype=bool),
            "st_power_mw": 70 * (power / 160),
            "steam_flow_tph": 180 * (power / 160),
            "feedwater_temp_c": 60 + 0.2 * ambient,
            "ambient_pressure_kpa": 101.3 + rng.normal(0, 0.1, n),
            # 완전 상수 컬럼은 고착(stuck)으로 정확히 잡히므로 실제 계측기처럼 미세 잡음을 준다.
            "humidity_pct": 60.0 + rng.normal(0, 0.3, n),
            "fuel_flow": flow * 45,
            "igv_position_pct": 40 + 55 * (power / 160),
            "gt_backpressure_kpa": dp_clean * 1.05,
        }
    )


def linear_fouling(n: int, rate_per_point: float = 1 / 8640) -> np.ndarray:
    """0 에서 시작해 선형 증가하는 오염도."""
    return np.minimum(np.arange(n) * rate_per_point, 1.0)


def sawtooth_fouling(n: int, cycles: int = 3) -> np.ndarray:
    """세정마다 0 으로 리셋되는 톱니 오염도."""
    per_cycle = n // cycles
    return np.concatenate(
        [np.linspace(0, 0.8, per_cycle) for _ in range(cycles)] + [np.zeros(n - per_cycle * cycles)]
    )[:n]
