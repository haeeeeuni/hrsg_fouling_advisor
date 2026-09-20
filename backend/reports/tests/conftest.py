"""리포트 테스트 공통 픽스처."""

from datetime import date

import pytest


@pytest.fixture
def points():
    return [
        {
            "date": date(2024, 1, 1 + i % 28),
            "fi_value": 10 + i * 1.5,
            "grade": "CAUTION",
            "sample_count": 300,
            "confidence": "HIGH",
            "measured_dp": 2.0 + i * 0.02,
            "expected_dp": 2.0,
            "residual_dp": i * 0.02,
            "measured_st": 110 + i * 0.3,
            "expected_st": 110.0,
            "residual_st": i * 0.3,
        }
        for i in range(30)
    ]


@pytest.fixture
def context(points):
    return {
        "report_title": "HRSG 가스측 오염도 진단 리포트",
        "unit_name": "U1 1호기 HRSG",
        "plant_name": "○○복합화력",
        "period_start": "2024-01-01",
        "period_end": "2024-12-31",
        "executed_by": "홍길동",
        "executed_at": "2025-09-20 14:02",
        "generated_at": "2025-09-20 14:05",
        "current_fi": 62.4,
        "grade": "WARNING",
        "confidence": "HIGH",
        "eta_days": 84,
        "trend_status": "OK",
        "net_benefit": 768_200_000,
        "threshold": 60,
        "data_stats": {
            "row_total": 52560,
            "row_valid": 31204,
            "valid_ratio": 0.594,
            "segment_count": 384,
            "baseline_points": 3093,
            "baseline_source": "AUTO_FROM_CLEANING",
            "out_of_domain_ratio": 0.02,
            "excluded_by_reason": {"기동/정지": 4102, "부하 급변": 6880, "덕트버너": 7512},
        },
        "clusters": [
            {
                "cluster_key": "L3-SU",
                "label": "고부하·여름",
                "sample_count": 8200,
                "share_pct": 26.3,
                "avg_load_ratio_pct": 88.2,
                "avg_ambient_temp_c": 24.1,
                "avg_dp_kpa": 2.31,
                "avg_stack_temp_c": 115.2,
                "is_sparse": False,
            },
            {
                "cluster_key": "L1-WI",
                "label": "저부하·겨울",
                "sample_count": 120,
                "share_pct": 0.4,
                "avg_load_ratio_pct": 48.0,
                "avg_ambient_temp_c": -1.2,
                "avg_dp_kpa": 1.8,
                "avg_stack_temp_c": 104.0,
                "is_sparse": True,
            },
        ],
        "settings_snapshot": {"fouling_threshold": 60, "weight_dp": 0.6, "sigma_ref": 6.0},
        "model_dp": {
            "algorithm": "GBR",
            "version": 3,
            "baseline_start": "2024-07-06",
            "baseline_end": "2024-08-05",
            "training_rows": 2165,
            "metrics": {"mae": 0.039, "rmse": 0.051, "r2": 0.991},
            "residual_std": 0.0287,
            "feature_list": ["gt_power_mw"],
            "hyperparams": {"max_iter": 300},
        },
        "model_st": {
            "algorithm": "GBR",
            "version": 3,
            "baseline_start": "2024-07-06",
            "baseline_end": "2024-08-05",
            "training_rows": 2165,
            "metrics": {"mae": 1.233, "rmse": 1.61, "r2": 0.612},
            "residual_std": 1.2871,
            "feature_list": ["gt_power_mw"],
            "hyperparams": {"max_iter": 300},
        },
        "fouling_points": points,
        "cleaning_dates": [date(2024, 1, 15)],
        "trend": {
            "model_type": "LINEAR",
            "status": "OK",
            "slope_per_day": 0.18,
            "weekly_increase": 1.26,
            "fit_start": "2024-07-05",
            "fit_end": "2024-12-31",
            "r2": 0.893,
            "mae": 1.2,
            "p_value": 1e-20,
            "eta_days": 84,
            "eta_date": "2025-12-13",
            "eta_lower_date": "2025-11-02",
            "eta_upper_date": "2026-02-01",
            "caution_eta_date": "2025-08-01",
            "warning_eta_date": "2025-12-13",
            "days_since_cleaning": 181,
            "threshold_used": 60,
            "uncertain": False,
        },
        "benefit": {
            "delta_dp_kpa": 3.39,
            "delta_stack_c": 9.38,
            "power_loss_total_mw": 2.8,
            "power_loss_gt_mw": 1.9,
            "power_loss_st_mw": 0.9,
            "daily_loss_cost": 5_712_000,
            "daily_fuel_loss": 0,
            "cleaning_cost": 30_000_000,
            "outage_loss": 244_800_000,
            "total_cleaning_cost": 274_800_000,
            "gross_benefit": 1_043_000_000,
            "gross_benefit_simple": 900_000_000,
            "net_benefit": 768_200_000,
            "payback_days": 48,
            "roi_pct": 279,
            "recommended_cleaning_date": "2025-12-01",
            "params_snapshot": {
                "electricity_price": 120,
                "dp_power_loss_coeff": 0.35,
                "stack_temp_loss_coeff": 0.12,
                "cleaning_recovery_ratio": 0.9,
                "evaluation_horizon_days": 365,
            },
            "scenarios": [
                {"label": "지금 세정", "offset_days": 0, "net_benefit": 768_200_000},
                {"label": "임계치 도달 시 세정", "offset_days": 84, "net_benefit": 701_000_000},
                {"label": "계획 정비 시 세정", "offset_days": 180, "net_benefit": 612_000_000},
            ],
            "sensitivity": [
                {
                    "param": "outage_days",
                    "net_benefit_low": 900_000_000,
                    "net_benefit_high": 600_000_000,
                    "swing": 300_000_000,
                }
            ],
        },
        "warnings": ["예측 정확도가 낮습니다(R² 0.61). 모델 재학습을 권장합니다."],
        "conclusion": (
            "1호기 HRSG의 현재 오염도 지수는 62.4(경고)이며, 임계치 60을 이미 초과했습니다."
        ),
        "assumption_note": "가정 — 전력단가 120원/kWh. 계수 기반 추정치입니다.",
    }


@pytest.fixture
def comparison_context(context):
    return {
        **context,
        "report_title": "세정 전후 비교 리포트",
        "comparison": {
            "before_start": "2023-11-30",
            "before_end": "2023-12-30",
            "after_start": "2024-01-02",
            "after_end": "2024-02-01",
            "common_clusters": ["L1-WI", "L3-WI"],
            "recovery_ratio": 0.948,
            "metrics": {
                "rows": [
                    {
                        "key": "fi",
                        "label": "오염도 지수 FI",
                        "before": 81.4,
                        "after": 4.2,
                        "delta": -77.2,
                        "delta_pct": -94.9,
                        "is_primary": True,
                    },
                    {
                        "key": "residual_dp",
                        "label": "차압 잔차 (kPa)",
                        "before": 0.39,
                        "after": 0.03,
                        "delta": -0.36,
                        "delta_pct": None,
                        "is_primary": True,
                    },
                ],
                "n_before": 3096,
                "n_after": 2987,
                "cluster_count": 2,
            },
            "cluster_metrics": [
                {
                    "cluster_key": "L3-WI",
                    "n_before": 1500,
                    "n_after": 1400,
                    "metrics": [
                        {
                            "key": "residual_dp",
                            "label": "차압 잔차",
                            "before": 0.4,
                            "after": 0.03,
                            "delta": -0.37,
                            "delta_pct": None,
                            "is_primary": True,
                        }
                    ],
                    "p_values": {},
                }
            ],
            "p_values": {"residual_dp": {"t_p_value": 1e-30, "u_p_value": 1e-30}},
        },
    }
