"""호기 간 세정 우선순위 (specs/19 §3).

절대 차압·스택온도는 설비마다 달라 비교 불가하므로 **FI와 잔차 기반 지표만** 쓴다.
점수만으로 단정하지 않고 근거 지표를 함께 제시한다.

순수 함수 모듈 — Django 모델을 import 하지 않는다.
"""

from __future__ import annotations

from typing import Any

import numpy as np

DEFAULT_WEIGHTS: dict[str, float] = {
    "fi": 0.30,
    "slope": 0.20,
    "daily_loss": 0.35,
    "urgency": 0.15,
}


def minmax(values: list[float | None]) -> list[float]:
    """비교 대상 호기들 사이의 min-max 정규화 (specs/19 §3.3).

    값이 없으면 0, 전부 같으면 모두 0.5 로 둔다(한쪽으로 쏠리지 않게).
    """
    numeric = [v for v in values if v is not None and np.isfinite(v)]
    if not numeric:
        return [0.0] * len(values)

    low, high = min(numeric), max(numeric)
    if high - low < 1e-12:
        return [0.5 if v is not None else 0.0 for v in values]
    return [
        (float(v) - low) / (high - low) if v is not None and np.isfinite(v) else 0.0 for v in values
    ]


def urgency(eta_days: int | None, already_exceeded: bool) -> float:
    """임박도 = 1 / max(D-day, 1). 이미 도달했으면 최대값."""
    if already_exceeded:
        return 1.0
    if eta_days is None:
        return 0.0
    return 1.0 / max(int(eta_days), 1)


def rank(rows: list[dict[str, Any]], weights: dict[str, float] | None = None) -> list[dict]:
    """호기별 지표에서 우선순위 점수를 내고 순위를 매긴다.

    rows 의 각 항목은 unit_code / fi / slope_per_day / daily_loss_cost /
    eta_days / already_exceeded 를 갖는다. 분석 결과가 없는 호기는
    `has_analysis=False` 로 두면 점수 없이 '분석 필요'로 표시된다(AC-19-8).
    """
    active = [r for r in rows if r.get("has_analysis")]
    inactive = [r for r in rows if not r.get("has_analysis")]

    if not active:
        return [{**r, "priority_score": None, "rank": None} for r in rows]

    w = {**DEFAULT_WEIGHTS, **(weights or {})}
    total_weight = sum(w.values()) or 1.0

    normalized = {
        "fi": minmax([r.get("fi") for r in active]),
        "slope": minmax([r.get("slope_per_day") for r in active]),
        "daily_loss": minmax([r.get("daily_loss_cost") for r in active]),
        "urgency": minmax(
            [urgency(r.get("eta_days"), bool(r.get("already_exceeded"))) for r in active]
        ),
    }

    scored = []
    for index, row in enumerate(active):
        components = {key: normalized[key][index] for key in normalized}
        score = sum(w[key] * components[key] for key in components) / total_weight
        scored.append(
            {
                **row,
                "priority_score": round(float(score), 4),
                "components": {k: round(v, 4) for k, v in components.items()},
            }
        )

    scored.sort(key=lambda r: r["priority_score"], reverse=True)
    for position, row in enumerate(scored, start=1):
        row["rank"] = position

    return scored + [
        {**r, "priority_score": None, "rank": None, "note": "분석 필요"} for r in inactive
    ]
