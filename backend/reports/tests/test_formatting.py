"""리포트 표기 규칙 (specs/16 §7 과 동일). DB 불필요."""

from datetime import date, datetime

import pytest

from reports import formatting as fmt


def test_fi_uses_one_decimal():
    assert fmt.fi(62.44) == "62.4"
    assert fmt.fi(None) == fmt.EMPTY


def test_currency_adds_eok_above_100m():
    assert fmt.currency(768_200_000) == "768,200,000 원 (7.68억)"
    assert fmt.currency(5_712_000) == "5,712,000 원"
    assert fmt.currency(768_200_000, with_eok=False) == "768,200,000 원"


def test_units():
    assert fmt.dp(3.8249) == "3.82 kPa"
    assert fmt.temp(112.44) == "112.4 ℃"
    assert fmt.power(148.23) == "148.2 MW"
    assert fmt.percent(59.44) == "59.4 %"
    assert fmt.count(52560) == "52,560"


def test_dates():
    assert fmt.ymd(date(2025, 9, 20)) == "2025-09-20"
    assert fmt.ymd_hm(datetime(2025, 9, 20, 14, 2)) == "2025-09-20 14:02"
    assert fmt.ymd(None) == fmt.EMPTY


@pytest.mark.parametrize(
    ("days", "status", "expected"),
    [
        (84, "OK", "D-84"),
        (0, "ALREADY_EXCEEDED", "이미 도달"),
        (None, "NO_TREND", "예측 불가"),
        (None, "INSUFFICIENT_DATA", "예측 불가"),
        (900, "BEYOND_HORIZON", "2년 내 도달 예상 없음"),
        (None, None, fmt.EMPTY),
    ],
)
def test_dday(days, status, expected):
    assert fmt.dday(days, status) == expected


def test_labels():
    assert fmt.grade("WARNING") == "경고"
    assert fmt.confidence("HIGH") == "높음"
    assert fmt.trend_status("ALREADY_EXCEEDED") == "이미 도달"
    assert fmt.grade("UNKNOWN") == fmt.EMPTY


def test_zero_is_distinguished_from_missing():
    assert fmt.fi(0) == "0.0"
    assert fmt.fi(None) == fmt.EMPTY
    assert fmt.currency(0) == "0 원"
