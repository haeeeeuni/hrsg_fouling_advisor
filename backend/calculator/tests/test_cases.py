"""가상 검증 사례 10건 — 손계산 기대값과 일치 (검수 2, specs/05 AC-05-2).

기대값은 명세의 식(specs/05 §6)을 그대로 옮긴 독립 계산으로 만들었다(cases.json).
실무진의 검증 사례를 받으면 같은 형식으로 교체한다 `[실무 논의]` P10.
"""

import json
from pathlib import Path

import pytest

from calculator.services.loss import compute_loss, evaluate_method
from calculator.services.types import GtSpec, LossInputs, MethodSpec
from reference.param_defs import default_params

DATA = json.loads((Path(__file__).parent / "cases.json").read_text(encoding="utf-8"))
PARAMS = default_params()


def gt_spec(key: str) -> GtSpec:
    rated_gt, rated_st = DATA["gt_models"][key]
    # 상태 판정은 이 검증의 대상이 아니므로 한계값은 넉넉하게 둔다.
    return GtSpec(rated_gt, rated_st, 99, 100, 999, 1000)


@pytest.mark.parametrize("case", DATA["cases"], ids=[c["name"] for c in DATA["cases"]])
def test_matches_hand_calculation(case):
    gt = gt_spec(case["gt"])
    cost, outage_days, recovery = DATA["methods"][case["method"]]
    method = MethodSpec(1, case["method"], cost, outage_days, recovery)

    loss = compute_loss(LossInputs(**case["inputs"]), gt, PARAMS)
    result = evaluate_method(
        loss.daily_loss_won, case["inputs"]["smp_won_per_kwh"], gt, method, PARAMS
    )

    expected = case["expected"]
    assert loss.power_loss_total_mw == pytest.approx(expected["power_loss_total_mw"], abs=1e-6)
    assert loss.daily_loss_won == pytest.approx(expected["daily_loss_won"], abs=0.01)
    assert result.outage_loss_won == pytest.approx(expected["outage_loss_won"], abs=0.01)
    assert result.net_benefit_won == pytest.approx(expected["net_benefit_won"], abs=0.01)
    if expected["payback_days"] is None:
        assert result.payback_days is None
    else:
        assert result.payback_days == pytest.approx(expected["payback_days"], abs=1e-3)


def test_there_are_ten_cases():
    assert len(DATA["cases"]) == 10
