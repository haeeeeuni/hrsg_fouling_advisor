"""백테스트 집계 (specs/19 §2).

과거 세정 시점을 정답으로 두고 "그 이전 데이터만으로 예측했다면 얼마나 맞았는가"를
검증해 모델 신뢰도를 정량화한다.

순수 함수 모듈 — Django 모델을 import 하지 않는다. 실제 파이프라인 재실행은
호출부(tasks_auto)가 담당하고, 여기는 **오차 계산과 집계**만 한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

import numpy as np


@dataclass
class CaseResult:
    """세정 이벤트 하나에 대한 예측 결과."""

    cleaning_event_id: int
    actual_date: date
    cutoff_date: date
    predicted_date: date | None = None
    error_days: int | None = None
    fi_at_cutoff: float | None = None
    fi_at_actual: float | None = None
    trend_status: str = ""
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "cleaning_event_id": self.cleaning_event_id,
            "actual_date": self.actual_date.isoformat(),
            "cutoff_date": self.cutoff_date.isoformat(),
            "predicted_date": self.predicted_date.isoformat() if self.predicted_date else None,
            "error_days": self.error_days,
            "fi_at_cutoff": _round(self.fi_at_cutoff),
            "fi_at_actual": _round(self.fi_at_actual),
            "trend_status": self.trend_status,
            "note": self.note,
        }


@dataclass
class BacktestSummary:
    cases: list[CaseResult] = field(default_factory=list)
    hit_window_days: int = 30

    def evaluated(self) -> list[CaseResult]:
        return [c for c in self.cases if c.error_days is not None]

    def to_dict(self) -> dict[str, Any]:
        errors = [c.error_days for c in self.evaluated()]
        if not errors:
            return {
                "case_count": len(self.cases),
                "evaluated_count": 0,
                "mae_days": None,
                "bias_days": None,
                "hit_rate": None,
                "hit_window_days": self.hit_window_days,
            }

        array = np.array(errors, dtype=float)
        hits = int(np.sum(np.abs(array) <= self.hit_window_days))
        return {
            "case_count": len(self.cases),
            "evaluated_count": len(errors),
            # 평균 절대 오차 — 예측이 얼마나 빗나갔는가
            "mae_days": round(float(np.mean(np.abs(array))), 1),
            # 편향 — 양수면 늦게, 음수면 이르게 예측하는 경향
            "bias_days": round(float(np.mean(array)), 1),
            "hit_rate": round(hits / len(errors), 4),
            "hit_window_days": self.hit_window_days,
        }


def build_case(
    *,
    cleaning_event_id: int,
    actual_date: date,
    cutoff_date: date,
    predicted_date: date | None,
    trend_status: str,
    fi_at_cutoff: float | None = None,
    fi_at_actual: float | None = None,
    note: str = "",
) -> CaseResult:
    """예측 도달일과 실제 세정일의 오차(일)를 계산한다.

    오차 = 예측 도달일 − 실제 세정일. 양수면 실제보다 늦게 예측한 것이다.
    """
    error = (predicted_date - actual_date).days if predicted_date else None
    return CaseResult(
        cleaning_event_id=cleaning_event_id,
        actual_date=actual_date,
        cutoff_date=cutoff_date,
        predicted_date=predicted_date,
        error_days=error,
        fi_at_cutoff=fi_at_cutoff,
        fi_at_actual=fi_at_actual,
        trend_status=trend_status,
        note=note,
    )


def suggest_coefficients(
    predicted_benefits: list[float], actual_benefits: list[float]
) -> dict[str, Any]:
    """예측 편익 대비 실제 회복 기반 편익의 과대/과소 경향 (specs/19 §2.3).

    보정 배수만 제시하고 **적용은 관리자 판단**에 맡긴다.
    """
    # 실적이 음수(세정 후 오히려 악화)인 경우도 제외하지 않는다 — 빼면 보정이 낙관 쪽으로 쏠린다.
    pairs = [
        (p, a)
        for p, a in zip(predicted_benefits, actual_benefits, strict=False)
        if p is not None and a is not None and p > 0
    ]
    if not pairs:
        return {"available": False, "reason": "비교할 실적 편익이 없습니다."}

    ratios = np.array([a / p for p, a in pairs], dtype=float)
    # 음수 배수는 계수로 쓸 수 없으므로 0 에서 끊는다.
    factor = max(0.0, float(np.median(ratios)))
    return {
        "available": True,
        "sample_count": len(pairs),
        "median_actual_over_predicted": round(factor, 4),
        "tendency": "과대예측" if factor < 1 else "과소예측",
        "suggested_multiplier": {
            "dp_power_loss_coeff": round(factor, 4),
            "stack_temp_loss_coeff": round(factor, 4),
        },
        "note": "손실 계수에 곱할 보정 배수 제안입니다. 적용 여부는 관리자가 판단합니다.",
    }


def _round(value: float | None) -> float | None:
    return round(float(value), 2) if value is not None else None
