"""호기 간 세정 우선순위 (specs/19 §3, AC-19-7~9). 순수 함수 — DB 불필요."""

from __future__ import annotations

from analysis.services import priority


def row(code: str, **kwargs) -> dict:
    base = {
        "unit_code": code,
        "has_analysis": True,
        "fi": 30.0,
        "slope_per_day": 0.1,
        "daily_loss_cost": 1_000_000.0,
        "eta_days": 100,
        "already_exceeded": False,
    }
    return {**base, **kwargs}


# --- 정규화 ---


def test_minmax_maps_extremes_to_zero_and_one():
    assert priority.minmax([10.0, 20.0, 30.0]) == [0.0, 0.5, 1.0]


def test_minmax_all_equal_gives_neutral_half():
    """전부 같으면 어느 호기도 우위가 아니므로 0.5 로 둔다."""
    assert priority.minmax([5.0, 5.0, 5.0]) == [0.5, 0.5, 0.5]


def test_minmax_treats_missing_as_zero():
    assert priority.minmax([None, 10.0, 20.0]) == [0.0, 0.0, 1.0]


def test_minmax_all_missing_is_all_zero():
    assert priority.minmax([None, None]) == [0.0, 0.0]


# --- 임박도 ---


def test_urgency_is_higher_for_closer_dday():
    assert priority.urgency(10, False) > priority.urgency(100, False)


def test_urgency_maxes_out_when_threshold_already_exceeded():
    assert priority.urgency(None, True) == 1.0
    assert priority.urgency(5, True) == 1.0


def test_urgency_is_zero_without_forecast():
    assert priority.urgency(None, False) == 0.0


# --- 순위 ---


def test_ac_19_7_ranks_three_units_worst_first():
    rows = [
        row("U1", fi=20.0, slope_per_day=0.05, daily_loss_cost=500_000, eta_days=300),
        row("U2", fi=70.0, slope_per_day=0.40, daily_loss_cost=3_000_000, eta_days=20),
        row("U3", fi=45.0, slope_per_day=0.20, daily_loss_cost=1_500_000, eta_days=120),
    ]

    ranked = priority.rank(rows)

    assert [r["unit_code"] for r in ranked] == ["U2", "U3", "U1"]
    assert [r["rank"] for r in ranked] == [1, 2, 3]
    assert ranked[0]["priority_score"] > ranked[-1]["priority_score"]


def test_ac_19_8_unanalyzed_unit_gets_no_score():
    rows = [row("U1"), {"unit_code": "U2", "has_analysis": False}]

    ranked = priority.rank(rows)
    pending = next(r for r in ranked if r["unit_code"] == "U2")

    assert pending["priority_score"] is None
    assert pending["rank"] is None
    assert pending["note"] == "분석 필요"


def test_all_units_unanalyzed_returns_no_ranking():
    ranked = priority.rank([{"unit_code": "U1", "has_analysis": False}])

    assert ranked[0]["priority_score"] is None


def test_ac_19_9_weight_change_reorders_immediately():
    """손실 비용만 큰 호기 vs FI만 높은 호기 — 가중치에 따라 순위가 뒤집힌다."""
    rows = [
        row("HIGH_FI", fi=90.0, slope_per_day=0.1, daily_loss_cost=100_000, eta_days=200),
        row("HIGH_LOSS", fi=10.0, slope_per_day=0.1, daily_loss_cost=5_000_000, eta_days=200),
    ]

    fi_first = priority.rank(rows, {"fi": 1.0, "slope": 0.0, "daily_loss": 0.0, "urgency": 0.0})
    loss_first = priority.rank(rows, {"fi": 0.0, "slope": 0.0, "daily_loss": 1.0, "urgency": 0.0})

    assert fi_first[0]["unit_code"] == "HIGH_FI"
    assert loss_first[0]["unit_code"] == "HIGH_LOSS"


def test_components_are_reported_for_traceability():
    """점수만으로 단정하지 않고 근거 지표를 함께 제시한다 (specs/19 §3.2)."""
    ranked = priority.rank([row("U1", fi=10.0), row("U2", fi=90.0)])

    assert set(ranked[0]["components"]) == {"fi", "slope", "daily_loss", "urgency"}


def test_score_stays_within_unit_interval():
    rows = [row("U1", fi=0.0, eta_days=None), row("U2", fi=100.0, already_exceeded=True)]

    for item in priority.rank(rows):
        assert 0.0 <= item["priority_score"] <= 1.0
