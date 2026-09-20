"""백테스트 집계 (specs/19 §2, AC-19-5). 순수 함수 — DB 불필요."""

from __future__ import annotations

from datetime import date

from analysis.services import backtest as bt


def case(actual: str, predicted: str | None, event_id: int = 1) -> bt.CaseResult:
    return bt.build_case(
        cleaning_event_id=event_id,
        actual_date=date.fromisoformat(actual),
        cutoff_date=date.fromisoformat("2024-01-01"),
        predicted_date=date.fromisoformat(predicted) if predicted else None,
        trend_status="OK" if predicted else "NO_TREND",
    )


# --- 개별 오차 ---


def test_error_is_predicted_minus_actual():
    """양수 = 실제보다 늦게 예측(세정을 미루라고 잘못 말한 쪽)."""
    assert case("2024-03-01", "2024-03-11").error_days == 10
    assert case("2024-03-01", "2024-02-20").error_days == -10


def test_case_without_forecast_has_no_error():
    assert case("2024-03-01", None).error_days is None


# --- 집계 ---


def test_ac_19_5_reports_per_case_and_overall_mae():
    summary = bt.BacktestSummary(
        cases=[
            case("2024-03-01", "2024-03-11", 1),
            case("2024-06-01", "2024-05-22", 2),
            case("2024-09-01", "2024-09-06", 3),
        ]
    )

    result = summary.to_dict()

    assert result["case_count"] == 3
    assert result["evaluated_count"] == 3
    assert result["mae_days"] == 8.3  # (10 + 10 + 5) / 3
    assert result["bias_days"] == 1.7  # (10 - 10 + 5) / 3


def test_hit_rate_counts_cases_inside_window():
    summary = bt.BacktestSummary(
        cases=[
            case("2024-03-01", "2024-03-11", 1),  # 10일 — 적중
            case("2024-06-01", "2024-08-01", 2),  # 61일 — 실패
        ],
        hit_window_days=30,
    )

    assert summary.to_dict()["hit_rate"] == 0.5


def test_hit_window_is_configurable():
    summary = bt.BacktestSummary(cases=[case("2024-03-01", "2024-04-10")], hit_window_days=60)

    assert summary.to_dict()["hit_rate"] == 1.0


def test_unpredicted_cases_are_counted_but_not_averaged():
    summary = bt.BacktestSummary(
        cases=[case("2024-03-01", "2024-03-11", 1), case("2024-06-01", None, 2)]
    )

    result = summary.to_dict()

    assert result["case_count"] == 2
    assert result["evaluated_count"] == 1
    assert result["mae_days"] == 10.0


def test_summary_without_any_forecast_is_empty_not_error():
    summary = bt.BacktestSummary(cases=[case("2024-03-01", None)])

    result = summary.to_dict()

    assert result["mae_days"] is None
    assert result["hit_rate"] is None


def test_case_serializes_dates_as_iso():
    payload = case("2024-03-01", "2024-03-11").to_dict()

    assert payload["actual_date"] == "2024-03-01"
    assert payload["predicted_date"] == "2024-03-11"


# --- 손실 계수 보정 제안 (specs/19 §2.3) ---


def test_overprediction_suggests_multiplier_below_one():
    suggestion = bt.suggest_coefficients([100.0, 200.0], [50.0, 100.0])

    assert suggestion["available"] is True
    assert suggestion["median_actual_over_predicted"] == 0.5
    assert suggestion["tendency"] == "과대예측"


def test_underprediction_is_labeled_accordingly():
    assert bt.suggest_coefficients([100.0], [150.0])["tendency"] == "과소예측"


def test_suggestion_unavailable_without_actuals():
    assert bt.suggest_coefficients([100.0], [])["available"] is False


def test_negative_actual_recovery_is_not_dropped():
    """세정 후 오히려 악화된 사례를 빼면 보정이 낙관 쪽으로 쏠린다."""
    suggestion = bt.suggest_coefficients([100.0, 100.0, 100.0], [-50.0, 10.0, 20.0])

    assert suggestion["sample_count"] == 3
    assert suggestion["median_actual_over_predicted"] == 0.1


def test_suggested_multiplier_never_goes_negative():
    suggestion = bt.suggest_coefficients([100.0], [-50.0])

    assert suggestion["suggested_multiplier"]["dp_power_loss_coeff"] == 0.0
