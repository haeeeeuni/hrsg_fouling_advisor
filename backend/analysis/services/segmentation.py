"""운전 구간 분류 및 유효 구간 추출 (specs/04 §7).

순수 함수 모듈. 오염 신호는 미세하므로 여기서 잡음을 얼마나 걷어내느냐가
정확도의 대부분을 결정한다.

**제외는 원본 삭제가 아니라 플래그다.** segment_state / is_valid / exclusion_reason 을
부여할 뿐이고, 호출부가 유효 구간만 골라 쓴다(AGENTS.md §5.3).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from units.standard_fields import TIMESTAMP

# segment_state 값
STARTUP = "STARTUP"
SHUTDOWN = "SHUTDOWN"
OFFLINE = "OFFLINE"
LOAD_RAMP = "LOAD_RAMP"
DUCT_BURNER = "DUCT_BURNER"
UNSTABLE = "UNSTABLE"
LOW_LOAD = "LOW_LOAD"
SHORT_SEGMENT = "SHORT_SEGMENT"
STEADY = "STEADY"

# UI 요약에 쓰는 제외 사유 묶음 (specs/04 §8)
EXCLUSION_GROUPS: dict[str, tuple[str, ...]] = {
    "기동/정지": (STARTUP, SHUTDOWN, OFFLINE),
    "부하 급변": (LOAD_RAMP,),
    "덕트버너": (DUCT_BURNER,),
    "저부하/불안정": (LOW_LOAD, UNSTABLE),
    "짧은 구간": (SHORT_SEGMENT,),
}


@dataclass
class SegmentationResult:
    frame: pd.DataFrame  # segment_state / segment_id / is_valid / exclusion_reason 포함
    stats: dict[str, Any] = field(default_factory=dict)
    warnings: list[dict[str, Any]] = field(default_factory=list)


def _points_for(minutes: float, interval_min: int) -> int:
    """분 단위 시간을 샘플 개수로 환산한다."""
    if interval_min <= 0:
        return 0
    return int(np.ceil(minutes / interval_min))


def _forward_mask(mask: pd.Series, points: int) -> pd.Series:
    """True 이후 points 개까지 True 를 확장한다(사후 제외 구간)."""
    if points <= 0:
        return mask
    return mask.rolling(points + 1, min_periods=1).max().astype(bool)


def _backward_mask(mask: pd.Series, points: int) -> pd.Series:
    """True 이전 points 개까지 True 를 확장한다(사전 제외 구간)."""
    if points <= 0:
        return mask
    reversed_mask = mask[::-1].rolling(points + 1, min_periods=1).max()[::-1]
    return reversed_mask.astype(bool)


def classify(frame: pd.DataFrame, config: dict[str, Any]) -> SegmentationResult:
    """각 시점에 segment_state 를 부여하고 유효 구간을 표시한다."""
    out = frame.copy()
    if out.empty:
        out["segment_state"] = pd.Series(dtype=str)
        out["segment_id"] = pd.Series(dtype="Int64")
        out["is_valid"] = pd.Series(dtype=bool)
        out["exclusion_reason"] = pd.Series(dtype=str)
        return SegmentationResult(frame=out, stats={"row_total": 0, "row_valid": 0})

    interval = config["sampling_interval_min"]
    min_load = config["min_load_mw"]
    rated = config["rated_power_mw"]
    power = out["gt_power_mw"]

    online = power >= min_load

    # --- OFFLINE ---
    state = pd.Series(STEADY, index=out.index, dtype=object)
    state[~online] = OFFLINE

    # --- STARTUP : 정지→운전 전환 및 이후 startup_settle_min ---
    started = online & ~online.shift(1, fill_value=False)
    startup = _forward_mask(started, _points_for(config["startup_settle_min"], interval))

    # --- SHUTDOWN : 운전→정지 전환 및 직전 shutdown_lead_min ---
    stopping = (~online) & online.shift(1, fill_value=False)
    shutdown = _backward_mask(stopping, _points_for(config["shutdown_lead_min"], interval))

    state[online & startup] = STARTUP
    state[online & shutdown] = SHUTDOWN

    # --- DUCT_BURNER : 가동 중 및 OFF 전환 후 db_settle_min ---
    if "duct_burner_on" in out.columns:
        burner = out["duct_burner_on"].fillna(False).astype(bool)
        burner_window = _forward_mask(burner, _points_for(config["db_settle_min"], interval))
        state[online & (state == STEADY) & burner_window] = DUCT_BURNER

    # --- LOAD_RAMP : 부하 변화율 초과 및 이후 ramp_settle_min ---
    delta_t_min = out[TIMESTAMP].diff().dt.total_seconds() / 60
    ramp_rate = (power.diff() / delta_t_min.replace(0, np.nan)).abs()
    ramping = (ramp_rate > config["ramp_threshold_mw_per_min"]).fillna(False)
    ramp_window = _forward_mask(ramping, _points_for(config["ramp_settle_min"], interval))
    state[online & (state == STEADY) & ramp_window] = LOAD_RAMP

    # --- 저부하 : 정격 대비 최소 부하율 미만 ---
    load_ratio_pct = power / rated * 100
    low_load = load_ratio_pct < config["min_analysis_load_pct"]
    state[online & (state == STEADY) & low_load] = LOW_LOAD

    # --- 안정성 조건 : 최근 윈도의 표준편차 ---
    stability_points = max(_points_for(config["stability_window_min"], interval), 2)
    load_std = power.rolling(stability_points, min_periods=2).std()
    unstable = (load_std > config["load_std_max_mw"]).fillna(False)

    if "gt_exhaust_temp_c" in out.columns:
        exh_std = out["gt_exhaust_temp_c"].rolling(stability_points, min_periods=2).std()
        unstable |= (exh_std > config["exh_temp_std_max_c"]).fillna(False)

    state[online & (state == STEADY) & unstable] = UNSTABLE

    out["segment_state"] = state

    # --- 유효 세그먼트 : 연속 STEADY 묶음 중 최소 길이 이상 ---
    is_steady = state == STEADY
    block = (is_steady != is_steady.shift(1)).cumsum()
    out["segment_id"] = np.where(is_steady, block, np.nan)

    min_points = max(_points_for(config["min_segment_min"], interval), 1)
    sizes = out.loc[is_steady, "segment_id"].value_counts()
    short_ids = set(sizes[sizes < min_points].index)
    too_short = is_steady & out["segment_id"].isin(short_ids)
    out.loc[too_short, "segment_state"] = SHORT_SEGMENT
    out.loc[too_short, "segment_id"] = np.nan

    out["is_valid"] = out["segment_state"] == STEADY
    out["exclusion_reason"] = np.where(out["is_valid"], "", out["segment_state"])
    out["segment_id"] = out["segment_id"].astype("Int64")

    stats = _build_stats(out)
    warnings = _build_warnings(out, stats, config)
    return SegmentationResult(frame=out, stats=stats, warnings=warnings)


def _build_stats(frame: pd.DataFrame) -> dict[str, Any]:
    """정제 요약 — UI 표시 필수 (specs/04 §8)."""
    total = len(frame)
    valid = int(frame["is_valid"].sum())
    counts = frame["segment_state"].value_counts().to_dict()

    by_reason = {
        label: int(sum(counts.get(state, 0) for state in states))
        for label, states in EXCLUSION_GROUPS.items()
    }

    return {
        "row_total": total,
        "row_valid": valid,
        "valid_ratio": round(valid / total, 4) if total else 0.0,
        "excluded_by_reason": by_reason,
        "state_counts": {key: int(value) for key, value in counts.items()},
        "segment_count": int(frame["segment_id"].nunique(dropna=True)),
    }


def _build_warnings(
    frame: pd.DataFrame, stats: dict[str, Any], config: dict[str, Any]
) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []

    # 유효 비율 20% 미만이면 품질 주의 (specs/04 §9)
    if stats["row_total"] and stats["valid_ratio"] < 0.20:
        warnings.append(
            {
                "code": "LOW_VALID_RATIO",
                "message": "유효 운전 구간이 부족합니다. 데이터 품질에 주의하세요.",
                "details": {"valid_ratio": stats["valid_ratio"]},
            }
        )

    # 덕트버너가 항상 ON 이면 규칙이 전 구간을 먹어치운다 (specs/04 §9)
    if "duct_burner_on" in frame.columns and len(frame):
        on_ratio = frame["duct_burner_on"].fillna(False).astype(bool).mean()
        if on_ratio > 0.95:
            warnings.append(
                {
                    "code": "DUCT_BURNER_ALWAYS_ON",
                    "message": (
                        "덕트버너가 거의 항상 ON 입니다. 매핑을 확인하거나 "
                        "덕트버너 제외 규칙 비활성화를 검토하세요."
                    ),
                    "details": {"on_ratio": round(float(on_ratio), 4)},
                }
            )

    return warnings


def valid_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """유효(STEADY) 구간만 추출한다."""
    return frame[frame["is_valid"]].copy()
