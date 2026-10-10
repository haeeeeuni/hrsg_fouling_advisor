"""포화온도 — IAPWS-IF97 Region 4 역방향 식 (specs/05 §5.2).

공개 공식이라 외부 라이브러리 없이 구현한다. 검증값(IF97 표 35):
0.1 MPa → 372.755919 K, 1 MPa → 453.035632 K, 10 MPa → 584.149488 K.
"""

from __future__ import annotations

import math

ATMOSPHERIC_BAR = 1.01325
KELVIN_OFFSET = 273.15

# 유효 범위: 삼중점 압력 ~ 임계 압력
MIN_PRESSURE_MPA = 611.213e-6
CRITICAL_PRESSURE_MPA = 22.064

# IF97 Region 4 계수 n1~n10
_N = (
    0.11670521452767e4,
    -0.72421316703206e6,
    -0.17073846940092e2,
    0.12020824702470e5,
    -0.32325550322333e7,
    0.14915108613530e2,
    -0.48232657361591e4,
    0.40511340542057e6,
    -0.23855557567849,
    0.65017534844798e3,
)


def saturation_temperature_k(pressure_mpa: float) -> float:
    """절대압(MPa) → 포화온도(K)."""
    if not MIN_PRESSURE_MPA <= pressure_mpa <= CRITICAL_PRESSURE_MPA:
        raise ValueError(
            f"압력은 {MIN_PRESSURE_MPA} ~ {CRITICAL_PRESSURE_MPA} MPa(절대압) 범위여야 합니다."
        )
    n1, n2, n3, n4, n5, n6, n7, n8, n9, n10 = _N
    beta = pressure_mpa**0.25
    e = beta**2 + n3 * beta + n6
    f = n1 * beta**2 + n4 * beta + n7
    g = n2 * beta**2 + n5 * beta + n8
    d = 2 * g / (-f - math.sqrt(f**2 - 4 * e * g))
    return (n10 + d - math.sqrt((n10 + d) ** 2 - 4 * (n9 + n10 * d))) / 2


def saturation_temperature_c_from_barg(drum_pressure_barg: float) -> float:
    """게이지압(bar) → 포화온도(℃). 대기압 1.01325 bar 를 더해 절대압으로 바꾼다."""
    absolute_mpa = (drum_pressure_barg + ATMOSPHERIC_BAR) / 10
    return saturation_temperature_k(absolute_mpa) - KELVIN_OFFSET
