"""세정 회수 편익 산출 (specs/09).

세정으로 회복되는 출력·효율 이득과 세정 비용을 비교해
순편익, 회수기간, 최적 세정 시점을 제시한다.

순수 함수 모듈 — Django 모델을 import 하지 않는다.

**모든 수치는 계수 기반 추정치다.** 결과에는 적용 파라미터 스냅샷을 반드시 함께 남긴다
(specs/09 §9, AC-09-3).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

SCENARIO_NOW = "NOW"
SCENARIO_AT_THRESHOLD = "AT_THRESHOLD"
SCENARIO_PLANNED_OUTAGE = "PLANNED_OUTAGE"

SCENARIO_LABELS = {
    SCENARIO_NOW: "지금 세정",
    SCENARIO_AT_THRESHOLD: "임계치 도달 시 세정",
    SCENARIO_PLANNED_OUTAGE: "계획 정비 시 세정",
}

# 민감도 분석 대상 (specs/09 §5)
SENSITIVITY_KEYS = (
    "electricity_price",
    "cleaning_cost",
    "dp_power_loss_coeff",
    "outage_days",
)
SENSITIVITY_DELTA = 0.30


@dataclass
class BenefitResult:
    params_snapshot: dict[str, Any]

    delta_dp_kpa: float
    delta_stack_c: float

    power_loss_gt_mw: float
    power_loss_st_mw: float
    power_loss_total_mw: float

    daily_loss_cost: float
    daily_fuel_loss: float

    cleaning_cost: float
    outage_loss: float
    total_cleaning_cost: float

    gross_benefit: float
    gross_benefit_simple: float
    net_benefit: float
    payback_days: float | None
    roi_pct: float | None

    recommended_offset_days: int | None = None
    recommended_net_benefit: float | None = None
    scenarios: list[dict[str, Any]] = field(default_factory=list)
    sensitivity: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[dict[str, Any]] = field(default_factory=list)


# --- 4.1 현재 손실 출력 ---


def power_losses(
    delta_dp: float,
    delta_stack: float,
    params: dict[str, Any],
    rated_gt_mw: float,
    rated_st_mw: float | None,
    avg_st_power_mw: float | None = None,
) -> tuple[float, float, list[dict[str, Any]]]:
    """Δ차압·Δ스택온도 → GT/ST 출력 손실 (MW).

    Δ가 음수이면 0 으로 처리한다(오염이 아니다).
    """
    warnings: list[dict[str, Any]] = []
    delta_dp = max(float(delta_dp or 0.0), 0.0)
    delta_stack = max(float(delta_stack or 0.0), 0.0)

    loss_gt = rated_gt_mw * (params["dp_power_loss_coeff"] / 100) * delta_dp

    st_rating = rated_st_mw
    if not st_rating:
        if avg_st_power_mw:
            st_rating = avg_st_power_mw
            warnings.append(
                {
                    "code": "ST_RATING_ASSUMED",
                    "message": "ST 정격 출력이 없어 실측 평균 출력을 사용했습니다.",
                    "details": {"assumed_mw": round(float(st_rating), 2)},
                }
            )
        else:
            st_rating = rated_gt_mw * 0.5
            warnings.append(
                {
                    "code": "ST_RATING_ASSUMED",
                    "message": "ST 정격 출력이 등록되지 않아 GT 정격의 50%로 가정했습니다.",
                    "details": {"assumed_mw": round(float(st_rating), 2)},
                }
            )

    loss_st = st_rating * (params["stack_temp_loss_coeff"] / 100) * delta_stack
    return float(loss_gt), float(loss_st), warnings


# --- 4.2 / 4.3 일일 손실 ---


def daily_loss(power_loss_total_mw: float, params: dict[str, Any]) -> float:
    """MW 손실 → 원/일."""
    energy_mwh = power_loss_total_mw * params["operating_hours_per_day"] * params["capacity_factor"]
    return float(energy_mwh * 1000 * params["electricity_price"])


def daily_fuel_loss(
    delta_dp: float, params: dict[str, Any], avg_fuel_flow: float | None
) -> tuple[float, list[dict[str, Any]]]:
    """열소비율 악화에 따른 연료 측 추가 손실 (specs/09 §4.3).

    연료 사용량 데이터가 없으면 0 으로 두고 '미반영'을 알린다.
    """
    if not avg_fuel_flow:
        return 0.0, [
            {
                "code": "FUEL_LOSS_NOT_INCLUDED",
                "message": "연료 사용량 데이터가 없어 연료 손실을 반영하지 않았습니다.",
            }
        ]

    penalty_pct = params["heat_rate_penalty_coeff"] * max(float(delta_dp), 0.0)
    daily_fuel_cost = (
        avg_fuel_flow
        * params["operating_hours_per_day"]
        * params["capacity_factor"]
        * params["fuel_price"]
    )
    return float(daily_fuel_cost * penalty_pct / 100), []


# --- 4.4 세정 비용 ---


def cleaning_costs(params: dict[str, Any], rated_total_mw: float) -> tuple[float, float, float]:
    """세정 비용 + 정지 손실. outage_days=0 이면 운전 중 세정이라 정지 손실은 0."""
    outage_days = float(params["outage_days"])
    outage_loss = (
        rated_total_mw
        * 24
        * params["capacity_factor"]
        * outage_days
        * 1000
        * params["electricity_price"]
    )
    cost = float(params["cleaning_cost"])
    return cost, float(outage_loss), float(cost + outage_loss)


# --- 4.5 회수 편익 ---


def project_fi(fi_now: float, slope_per_day: float, days: np.ndarray) -> np.ndarray:
    """세정하지 않았을 때의 FI 투영 (0~100 클리핑)."""
    return np.clip(fi_now + slope_per_day * days, 0.0, 100.0)


def gross_benefit_precise(
    fi_now: float,
    slope_per_day: float,
    daily_recoverable: float,
    params: dict[str, Any],
    clean_offset_days: int = 0,
) -> float:
    """정밀식 — 일자별 FI 추세를 세정 시점부터 재투영해 일별 손실 차이를 합산한다.

    세정 후에도 오염이 다시 진행되므로 회수액은 시간에 따라 줄어든다(specs/09 §4.5).
    """
    horizon = int(params["evaluation_horizon_days"])
    if horizon <= 0 or fi_now <= 0 or daily_recoverable <= 0:
        return 0.0

    days = np.arange(horizon, dtype=float)
    outage = float(params["outage_days"])
    recovery = float(params["cleaning_recovery_ratio"])

    # 세정하지 않은 경우의 손실 (FI 에 비례)
    fi_no_clean = project_fi(fi_now, slope_per_day, days)

    # 세정한 경우: 정지 기간 후 잔류 오염에서 다시 진행.
    # 잔류 오염은 **세정 시점의 FI** 기준이다(분석 시점 FI 가 아니다).
    # 이를 혼동하면 늦게 세정할수록 유리해 보이는 왜곡이 생긴다.
    resume = clean_offset_days + outage
    fi_at_clean = float(np.clip(fi_now + slope_per_day * clean_offset_days, 0.0, 100.0))
    elapsed = np.maximum(days - resume, 0.0)
    fi_after = np.clip(fi_at_clean * (1 - recovery) + slope_per_day * elapsed, 0.0, 100.0)
    fi_cleaned = np.where(days < clean_offset_days, fi_no_clean, fi_after)

    # 손실은 FI 에 비례한다고 본다(Δdp·Δstack 이 오염도에 비례하므로).
    rate = daily_recoverable / fi_now
    saved = np.maximum(fi_no_clean - fi_cleaned, 0.0) * rate

    # 정지 기간에는 발전 자체가 없으므로 회수액도 없다(정지 손실은 별도로 뺀다).
    in_outage = (days >= clean_offset_days) & (days < resume)
    saved = np.where(in_outage, 0.0, saved)

    discount = float(params.get("discount_rate_annual") or 0.0)
    if discount > 0:
        saved = saved / (1 + discount) ** (days / 365.0)

    return float(saved.sum())


def gross_benefit_simple(daily_recoverable: float, params: dict[str, Any]) -> float:
    """간이식 — 선형 재오염 가정 (specs/09 §4.5). 비교값으로만 병기한다."""
    return float(daily_recoverable * int(params["evaluation_horizon_days"]) * 0.5)


# --- 4.6 최적 세정 시점 / 시나리오 ---


def optimal_offset(
    fi_now: float,
    slope_per_day: float,
    daily_recoverable: float,
    total_cleaning_cost: float,
    params: dict[str, Any],
) -> tuple[int | None, float]:
    """평가 기간 내 누적 순편익이 최대가 되는 세정 시점(오늘로부터 며칠 뒤).

    주의: 평가 기간이 고정이라 **끝단 효과**가 있다. 늦게 세정할수록 기간 종료 시점의
    오염도가 낮아져(잔류 = 세정 시점 FI × (1−회복률)) 권고일이 0 보다 약간 뒤로 밀린다.
    오염이 심할수록 그 폭은 작아진다(예: 기울기 0.18 → D+9). specs/09 §4.6 의 방법을
    그대로 따른 결과이며, 3개 시나리오 비교표와 함께 읽어야 한다.
    """
    horizon = int(params["evaluation_horizon_days"])
    if horizon <= 0:
        return None, 0.0

    # 하루 단위 전수 탐색은 365회 적분이라 비싸다. 7일 간격으로 훑고 주변을 좁힌다.
    def net_at(offset: int) -> float:
        gross = gross_benefit_precise(
            fi_now, slope_per_day, daily_recoverable, params, clean_offset_days=offset
        )
        return gross - total_cleaning_cost

    coarse = list(range(0, horizon, 7))
    best_coarse = max(coarse, key=net_at) if coarse else 0
    window = range(max(0, best_coarse - 7), min(horizon, best_coarse + 8))
    best = max(window, key=net_at)
    return int(best), net_at(best)


def build_scenarios(
    fi_now: float,
    slope_per_day: float,
    daily_recoverable: float,
    total_cleaning_cost: float,
    params: dict[str, Any],
    eta_days: int | None,
) -> list[dict[str, Any]]:
    """지금 / 임계치 도달 시 / 계획 정비 시 — 3개 시나리오 비교 (specs/09 §4.6)."""
    candidates = [
        (SCENARIO_NOW, 0),
        (SCENARIO_AT_THRESHOLD, eta_days),
        (SCENARIO_PLANNED_OUTAGE, int(params.get("planned_outage_days_ahead") or 0)),
    ]

    rows: list[dict[str, Any]] = []
    for key, offset in candidates:
        if offset is None:
            rows.append(
                {
                    "scenario": key,
                    "label": SCENARIO_LABELS[key],
                    "offset_days": None,
                    "gross_benefit": None,
                    "net_benefit": None,
                    "note": "임계치 도달 예상일을 산출할 수 없습니다.",
                }
            )
            continue
        gross = gross_benefit_precise(
            fi_now, slope_per_day, daily_recoverable, params, clean_offset_days=int(offset)
        )
        rows.append(
            {
                "scenario": key,
                "label": SCENARIO_LABELS[key],
                "offset_days": int(offset),
                "gross_benefit": round(gross),
                "net_benefit": round(gross - total_cleaning_cost),
                "note": "",
            }
        )
    return rows


# --- 5. 민감도 ---


def sensitivity_analysis(
    compute_net, params: dict[str, Any], delta: float = SENSITIVITY_DELTA
) -> list[dict[str, Any]]:
    """주요 파라미터를 ±delta 변동시켰을 때의 순편익 변화 (토네이도 차트용)."""
    base = compute_net(params)
    rows: list[dict[str, Any]] = []

    for key in SENSITIVITY_KEYS:
        if key not in params:
            continue
        low = compute_net({**params, key: params[key] * (1 - delta)})
        high = compute_net({**params, key: params[key] * (1 + delta)})
        rows.append(
            {
                "param": key,
                "base_value": params[key],
                "low_value": params[key] * (1 - delta),
                "high_value": params[key] * (1 + delta),
                "net_benefit_low": round(low),
                "net_benefit_high": round(high),
                "swing": round(abs(high - low)),
            }
        )

    rows.sort(key=lambda row: row["swing"], reverse=True)
    for row in rows:
        row["base_net_benefit"] = round(base)
    return rows


# --- 전체 ---


def compute(
    *,
    delta_dp: float,
    delta_stack: float,
    fi_now: float,
    slope_per_day: float,
    params: dict[str, Any],
    rated_gt_mw: float,
    rated_st_mw: float | None,
    eta_days: int | None = None,
    avg_st_power_mw: float | None = None,
    avg_fuel_flow: float | None = None,
    with_sensitivity: bool = True,
) -> BenefitResult:
    warnings: list[dict[str, Any]] = []

    def net_for(p: dict[str, Any]) -> float:
        loss_gt, loss_st, _ = power_losses(
            delta_dp, delta_stack, p, rated_gt_mw, rated_st_mw, avg_st_power_mw
        )
        cost_daily = daily_loss(loss_gt + loss_st, p)
        fuel, _ = daily_fuel_loss(delta_dp, p, avg_fuel_flow)
        recoverable = (cost_daily + fuel) * p["cleaning_recovery_ratio"]
        _, _, total = cleaning_costs(p, rated_gt_mw + (rated_st_mw or rated_gt_mw * 0.5))
        gross = gross_benefit_precise(fi_now, slope_per_day, recoverable, p)
        return gross - total

    loss_gt, loss_st, loss_warnings = power_losses(
        delta_dp, delta_stack, params, rated_gt_mw, rated_st_mw, avg_st_power_mw
    )
    warnings.extend(loss_warnings)
    loss_total = loss_gt + loss_st

    cost_daily = daily_loss(loss_total, params)
    fuel_daily, fuel_warnings = daily_fuel_loss(delta_dp, params, avg_fuel_flow)
    warnings.extend(fuel_warnings)

    recoverable = (cost_daily + fuel_daily) * float(params["cleaning_recovery_ratio"])

    rated_total = rated_gt_mw + (rated_st_mw or rated_gt_mw * 0.5)
    cost, outage_loss, total_cost = cleaning_costs(params, rated_total)

    gross = gross_benefit_precise(fi_now, slope_per_day, recoverable, params)
    gross_simple = gross_benefit_simple(recoverable, params)
    net = gross - total_cost

    if recoverable <= 0:
        payback = None
        roi = None
        warnings.append(
            {
                "code": "NO_ECONOMIC_BENEFIT",
                "message": "현재 오염 수준에서는 세정 경제성이 없습니다.",
            }
        )
    else:
        payback = float(total_cost / recoverable)
        roi = float(net / total_cost * 100) if total_cost else None

    best_offset, best_net = optimal_offset(fi_now, slope_per_day, recoverable, total_cost, params)
    scenarios = build_scenarios(fi_now, slope_per_day, recoverable, total_cost, params, eta_days)
    sensitivity = sensitivity_analysis(net_for, params) if with_sensitivity else []

    return BenefitResult(
        params_snapshot=dict(params),
        delta_dp_kpa=max(float(delta_dp or 0.0), 0.0),
        delta_stack_c=max(float(delta_stack or 0.0), 0.0),
        power_loss_gt_mw=loss_gt,
        power_loss_st_mw=loss_st,
        power_loss_total_mw=loss_total,
        daily_loss_cost=cost_daily,
        daily_fuel_loss=fuel_daily,
        cleaning_cost=cost,
        outage_loss=outage_loss,
        total_cleaning_cost=total_cost,
        gross_benefit=gross,
        gross_benefit_simple=gross_simple,
        net_benefit=net,
        payback_days=payback,
        roi_pct=roi,
        recommended_offset_days=best_offset,
        recommended_net_benefit=best_net,
        scenarios=scenarios,
        sensitivity=sensitivity,
        warnings=warnings,
    )
