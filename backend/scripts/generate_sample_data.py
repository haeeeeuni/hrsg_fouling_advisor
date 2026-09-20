#!/usr/bin/env python
"""가상 운전 데이터 생성 스크립트 (specs/17).

오염이 서서히 진행되다 세정 시점에 회복되는 패턴이 2~3회 반복되는 데이터를 만든다.
전 파이프라인(업로드 → 정제 → 모델 → FI → 추세 → 편익 → 리포트)의 검증 기준이다.

Django 에 의존하지 않는 독립 스크립트다(--to-db 옵션 제외).

사용 예:
    python scripts/generate_sample_data.py --unit-code U1 --start 2023-01-01 --months 24 \
        --cleanings 3 --seed 42 --out sample_unit1.csv \
        --maintenance-out sample_unit1_maintenance.csv --truth-out sample_unit1_truth.csv
"""

from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

# specs/17 §4.1 영문 헤더 (표준 항목명과 동일)
ENGLISH_HEADERS = [
    "timestamp",
    "gt_power_mw",
    "ambient_temp_c",
    "gt_exhaust_temp_c",
    "exhaust_flow",
    "fuel_flow",
    "igv_position_pct",
    "hrsg_gas_dp_kpa",
    "gt_backpressure_kpa",
    "stack_temp_c",
    "duct_burner_on",
    "st_power_mw",
    "steam_flow_tph",
    "feedwater_temp_c",
    "ambient_pressure_kpa",
    "humidity_pct",
]

# specs/17 §4.2 한글 헤더 (컬럼 매핑 검증용)
KOREAN_HEADERS = [
    "시각",
    "GT출력(MW)",
    "대기온도(℃)",
    "GT배기온도(℃)",
    "배기유량(kg/s)",
    "연료유량(Nm3/h)",
    "IGV개도(%)",
    "HRSG가스차압(kPa)",
    "GT배압(kPa)",
    "스택온도(℃)",
    "덕트버너상태",
    "ST출력(MW)",
    "증기유량(t/h)",
    "급수온도(℃)",
    "대기압(kPa)",
    "습도(%)",
]

CLEANING_METHODS = ["화학세정", "수세", "드라이아이스"]

# specs/17 §3.2~3.3 기저 물리 모델 계수
K_DP = 2.5  # 청정 상태 정격 차압 [kPa]
REF_FLOW = 450.0  # 기준 배기유량 [kg/s]
DP_FOULING_GAIN = 0.35
STACK_FOULING_GAIN = 14.0  # [℃]
TAU_DAYS = 180.0
F_MAX = 1.0


@dataclass
class Cleaning:
    at: datetime
    method: str
    cost: int
    outage_days: int
    residual: float


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="HRSG 가상 운전 데이터 생성기")
    p.add_argument("--unit-code", default="U1")
    p.add_argument("--start", default="2023-01-01")
    p.add_argument("--months", type=int, default=24)
    p.add_argument("--interval-min", type=int, default=10)
    p.add_argument("--rated-mw", type=float, default=160.0)
    p.add_argument("--rated-st-mw", type=float, default=80.0)
    p.add_argument("--cleanings", type=int, default=3)
    p.add_argument(
        "--fouling-rate", type=float, default=None, help="일당 오염 진행 속도(기본 자동)"
    )
    p.add_argument("--noise-level", type=float, default=1.0)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--out", required=True, help="운전 데이터 CSV 경로")
    p.add_argument("--maintenance-out", default=None, help="정비 이력 CSV 경로")
    p.add_argument("--truth-out", default=None, help="정답 fouling_level 시계열 CSV 경로")
    p.add_argument("--korean-headers", action="store_true", help="한글 컬럼명으로 출력")
    p.add_argument("--messy", action="store_true", help="결측·이상치·형식 오류를 주입")
    return p


def plan_cleanings(
    rng: np.random.Generator, start: datetime, end: datetime, count: int
) -> list[Cleaning]:
    """전체 기간을 count+1 구간으로 나눈 경계 부근(±15일)에 배치한다 (specs/17 §3.4)."""
    if count <= 0:
        return []
    total_days = (end - start).days
    events: list[Cleaning] = []
    for i in range(1, count + 1):
        base = start + timedelta(days=total_days * i / (count + 1))
        jitter = int(rng.integers(-15, 16))
        at = base + timedelta(days=jitter)
        events.append(
            Cleaning(
                at=at,
                method=str(rng.choice(CLEANING_METHODS)),
                cost=int(rng.integers(20, 35)) * 1_000_000,
                outage_days=2,
                # 완전 회복이 아닌 현실적 회복 (specs/17 §3.4)
                residual=float(rng.uniform(0.05, 0.15)),
            )
        )
    return events


def load_profile(index: pd.DatetimeIndex, rated_mw: float, rng: np.random.Generator) -> np.ndarray:
    """일간·주간 부하 패턴 (specs/17 §3.1).

    실제 운전에서 부하는 시간대 블록 안에서 거의 평탄하다. 포인트마다 무작위로 튀게 만들면
    부하 변화율이 항상 임계를 넘어 전처리 필터가 전 구간을 LOAD_RAMP 로 버린다.
    → 블록 수준은 **날짜별로** 뽑고, 그 위에 완만한 잡음만 얹는다.
    """
    hour = index.hour.to_numpy()
    is_weekend = index.dayofweek.to_numpy() >= 5

    # 날짜별 기저 수준 (주간 고부하 / 야간 중부하)
    day_codes, day_index = pd.factorize(index.normalize())
    day_high = rng.uniform(0.85, 1.00, len(day_index))[day_codes]
    day_low = rng.uniform(0.55, 0.75, len(day_index))[day_codes]

    ratio = np.where((hour >= 6) & (hour < 22), day_high, day_low)
    ratio = np.where(is_weekend, ratio * 0.9, ratio)

    # 운전 중 미세 변동 (10분당 약 0.1 MW/min 수준 — 급변 임계 1.0 MW/min 아래)
    ratio = ratio + rng.normal(0, 0.005, len(index))
    return rated_mw * np.clip(ratio, 0.3, 1.05)


def ambient_series(index: pd.DatetimeIndex, rng: np.random.Generator, noise: float) -> np.ndarray:
    doy = index.dayofyear.to_numpy()
    hour = index.hour.to_numpy()
    return (
        14
        + 12 * np.sin(2 * np.pi * (doy - 100) / 365)
        + 5 * np.sin(2 * np.pi * (hour - 9) / 24)
        + rng.normal(0, 1.5 * noise, len(index))
    )


def apply_outages(
    power: np.ndarray, index: pd.DatetimeIndex, cleanings: list[Cleaning], rng: np.random.Generator
) -> np.ndarray:
    """세정 정지 + 연 2회 계획 정비 정지 + 주 1~2회 야간 정지."""
    power = power.copy()
    ts = index.to_numpy()

    for event in cleanings:
        start = np.datetime64(event.at)
        end = np.datetime64(event.at + timedelta(days=event.outage_days))
        power[(ts >= start) & (ts < end)] = 0.0

    # 연 2회 계획 정비 (7~10일)
    year_starts = pd.date_range(index[0], index[-1], freq="YS")
    for year_start in year_starts:
        for offset_days in (60, 240):
            begin = year_start + timedelta(days=offset_days + int(rng.integers(-10, 11)))
            length = int(rng.integers(7, 11))
            mask = (ts >= np.datetime64(begin)) & (
                ts < np.datetime64(begin + timedelta(days=length))
            )
            power[mask] = 0.0

    # 주 1~2회 야간 정지 (기동/정지 구간 생성 — 전처리 필터 검증용)
    weeks = pd.date_range(index[0], index[-1], freq="W")
    for week in weeks:
        for _ in range(int(rng.integers(1, 3))):
            begin = week + timedelta(
                days=float(rng.integers(0, 7)), hours=float(rng.integers(22, 24))
            )
            length_h = int(rng.integers(4, 9))
            mask = (ts >= np.datetime64(begin)) & (
                ts < np.datetime64(begin + timedelta(hours=length_h))
            )
            power[mask] = 0.0

    return power


def duct_burner_series(index: pd.DatetimeIndex, rng: np.random.Generator) -> np.ndarray:
    """고부하 시간대 중 랜덤 15%의 날에 2~6시간 가동 (specs/17 §3.5)."""
    on = np.zeros(len(index), dtype=bool)
    days = pd.Series(index.date).unique()
    ts = index.to_numpy()

    for day in days:
        if rng.random() > 0.15:
            continue
        start_hour = int(rng.integers(8, 16))
        length_h = int(rng.integers(2, 7))
        begin = datetime.combine(day, datetime.min.time()) + timedelta(hours=start_hour)
        mask = (ts >= np.datetime64(begin)) & (
            ts < np.datetime64(begin + timedelta(hours=length_h))
        )
        on |= mask
    return on


def fouling_levels(
    index: pd.DatetimeIndex,
    cleanings: list[Cleaning],
    duct_on: np.ndarray,
    fouling_rate: float | None,
) -> np.ndarray:
    """세정 사이클마다 누적되는 포화형 오염 진행 (specs/17 §3.3)."""
    ts = index.to_numpy()
    levels = np.zeros(len(index))

    # 각 시점이 속한 사이클의 시작 시각과 잔류 오염
    cycle_start = np.full(len(index), np.datetime64(index[0]))
    residual = np.zeros(len(index))
    for event in cleanings:
        after = ts >= np.datetime64(event.at + timedelta(days=event.outage_days))
        cycle_start[after] = np.datetime64(event.at + timedelta(days=event.outage_days))
        residual[after] = event.residual

    elapsed_days = (ts - cycle_start) / np.timedelta64(1, "D")

    if fouling_rate is not None:
        levels = np.minimum(residual + elapsed_days * fouling_rate, 1.0)
    else:
        levels = residual + (F_MAX - residual) * (1 - np.exp(-elapsed_days / TAU_DAYS))

    # 덕트버너 누적 가동은 오염을 가속한다.
    duct_ratio = np.cumsum(duct_on) / np.maximum(np.arange(1, len(index) + 1), 1)
    levels = levels * (1 + 0.3 * duct_ratio)
    return np.clip(levels, 0.0, 1.5)


def generate(args: argparse.Namespace) -> tuple[pd.DataFrame, list[Cleaning]]:
    rng = np.random.default_rng(args.seed)

    start = datetime.fromisoformat(args.start)
    end = start + pd.DateOffset(months=args.months)
    index = pd.date_range(start, end, freq=f"{args.interval_min}min", inclusive="left")

    cleanings = plan_cleanings(rng, start, end.to_pydatetime(), args.cleanings)

    ambient = ambient_series(index, rng, args.noise_level)
    power_target = load_profile(index, args.rated_mw, rng)
    power = apply_outages(power_target, index, cleanings, rng)
    duct_on = duct_burner_series(index, rng)
    levels = fouling_levels(index, cleanings, duct_on, args.fouling_rate)

    online = power > 0
    load_ratio = np.where(online, power / args.rated_mw, 0.0)

    # --- 청정 상태 기저 물리 모델 (specs/17 §3.2) ---
    exhaust_flow = (
        REF_FLOW * load_ratio * (288 / (ambient + 273)) * (1 + rng.normal(0, 0.01, len(index)))
    )
    gt_exhaust_temp = (
        560 + 60 * load_ratio - 0.4 * ambient + rng.normal(0, 3 * args.noise_level, len(index))
    )
    dp_clean = K_DP * (exhaust_flow / REF_FLOW) ** 2
    stack_clean = (
        95
        + 0.02 * (gt_exhaust_temp - 560)
        + 12 * load_ratio
        + 0.15 * ambient
        + rng.normal(0, 1.2 * args.noise_level, len(index))
    )

    # 덕트버너 가동 시 배기·스택온도 상승 (필터 검증용 노이즈)
    gt_exhaust_temp = gt_exhaust_temp + np.where(duct_on & online, 25.0, 0.0)
    stack_clean = stack_clean + np.where(duct_on & online, 18.0, 0.0)

    # --- 오염 영향 ---
    dp_meas = dp_clean * (1 + DP_FOULING_GAIN * levels)
    stack_meas = stack_clean + STACK_FOULING_GAIN * levels

    # 오염에 따른 출력 손실 (편익 검증용 정합성)
    gt_power = power * (1 - 0.0035 * (dp_meas - dp_clean))
    st_power = args.rated_st_mw * load_ratio * (1 - 0.0012 * (stack_meas - stack_clean))

    frame = pd.DataFrame(
        {
            "timestamp": index,
            "gt_power_mw": np.where(online, gt_power, 0.0),
            "ambient_temp_c": ambient,
            "gt_exhaust_temp_c": np.where(online, gt_exhaust_temp, ambient + 10),
            "exhaust_flow": np.where(online, exhaust_flow, 0.0),
            "fuel_flow": np.where(online, exhaust_flow * 45, 0.0),
            "igv_position_pct": np.where(online, 40 + 55 * load_ratio, 0.0),
            "hrsg_gas_dp_kpa": np.where(online, dp_meas, 0.0),
            "gt_backpressure_kpa": np.where(online, dp_meas * 1.05, 0.0),
            "stack_temp_c": np.where(online, stack_meas, ambient + 5),
            "duct_burner_on": (duct_on & online).astype(int),
            "st_power_mw": np.where(online, st_power, 0.0),
            "steam_flow_tph": np.where(online, 180 * load_ratio, 0.0),
            "feedwater_temp_c": 60 + 0.2 * ambient + rng.normal(0, 0.8, len(index)),
            "ambient_pressure_kpa": 101.3 + rng.normal(0, 0.4, len(index)),
            "humidity_pct": np.clip(
                60
                + 20 * np.sin(2 * np.pi * (index.dayofyear.to_numpy() - 150) / 365)
                + rng.normal(0, 5, len(index)),
                20,
                95,
            ),
            "_fouling_level": levels,
        }
    )

    for column in frame.columns:
        if column in {"timestamp", "duct_burner_on"}:
            continue
        frame[column] = frame[column].round(3)

    return frame, cleanings


def inject_mess(frame: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """--messy: 업로드 검증을 시험할 결함을 주입한다 (specs/17 §3.6)."""
    frame = frame.copy()
    n = len(frame)
    numeric_cols = [c for c in frame.columns if c not in {"timestamp", "_fouling_level"}]

    # 결측 0.5%
    for column in numeric_cols:
        mask = rng.random(n) < 0.005
        frame.loc[mask, column] = np.nan

    # 문자열 오류 0.1%
    frame[numeric_cols] = frame[numeric_cols].astype(object)
    for token in ("Bad", "I/O Timeout", "N/A"):
        column = str(rng.choice(numeric_cols))
        mask = rng.random(n) < 0.001
        frame.loc[mask, column] = token

    # 이상치 스파이크 0.05% (물리 범위 밖)
    mask = rng.random(n) < 0.0005
    frame.loc[mask, "stack_temp_c"] = 9999.0

    # 고정값: 차압을 6시간 고정
    for _ in range(int(rng.integers(2, 4))):
        begin = int(rng.integers(0, max(1, n - 40)))
        frame.iloc[begin : begin + 36, frame.columns.get_loc("hrsg_gas_dp_kpa")] = 3.33

    # 시각 중복 50행 + 역순 구간
    duplicate_rows = frame.sample(n=min(50, n), random_state=int(rng.integers(0, 10_000)))
    frame = pd.concat([frame, duplicate_rows], ignore_index=True)
    begin = int(rng.integers(0, max(1, len(frame) - 200)))
    block = frame.iloc[begin : begin + 200].iloc[::-1]
    frame = pd.concat([frame.iloc[:begin], block, frame.iloc[begin + 200 :]], ignore_index=True)
    return frame


def format_timestamps(frame: pd.DataFrame, messy: bool, rng: np.random.Generator) -> pd.Series:
    if not messy:
        return frame["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")
    # 형식 혼합 (specs/17 §3.6)
    alt = rng.random(len(frame)) < 0.3
    primary = frame["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")
    secondary = frame["timestamp"].dt.strftime("%Y/%m/%d %H:%M")
    return primary.where(~alt, secondary)


def write_operation_csv(
    frame: pd.DataFrame, args: argparse.Namespace, rng: np.random.Generator
) -> None:
    out = frame.drop(columns=["_fouling_level"]).copy()
    out["timestamp"] = format_timestamps(frame, args.messy, rng)
    out = out[ENGLISH_HEADERS]
    if args.korean_headers:
        out.columns = KOREAN_HEADERS
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.out, index=False, encoding="utf-8-sig" if args.korean_headers else "utf-8")


def write_maintenance_csv(
    path: str,
    unit_code: str,
    cleanings: list[Cleaning],
    period: tuple[datetime, datetime],
    rng: np.random.Generator,
) -> None:
    """세정 대응 행 + 오염과 무관한 잡음 행(70%) + EXCLUDE 검증용 행 (specs/17 §4.3)."""
    rows: list[list] = []
    for event in cleanings:
        rows.append(
            [
                event.at.strftime("%Y-%m-%d"),
                unit_code,
                "계획정비",
                f"HRSG 전열면 {event.method} 시행",
                f"가스측 차압 상승에 따른 {event.method} 실시",
                event.cost,
                event.outage_days,
                "정비2팀",
            ]
        )

    noise_titles = [
        ("점검", "GT 연소기 육안 점검", "정기 점검 결과 이상 없음"),
        ("정비", "윤활유 필터 교체", "차압 상승으로 필터 교체"),
        ("점검", "발전기 절연 저항 측정", "기준치 이내"),
        ("정비", "급수펌프 씰 교체", "누수 확인되어 교체"),
        ("점검", "소방설비 정기 점검", "이상 없음"),
    ]
    # 오염과 무관한 행이 전체의 약 70%가 되도록 채운다.
    noise_count = max(1, int(len(cleanings) / 0.3) - len(cleanings))
    for _ in range(noise_count):
        work_type, title, description = noise_titles[int(rng.integers(0, len(noise_titles)))]
        # 잡음 행은 실제 운전 데이터 기간 안에 고르게 흩뿌린다.
        span_days = max((period[1] - period[0]).days, 1)
        day = period[0] + timedelta(days=int(rng.integers(0, span_days)))
        rows.append(
            [day.strftime("%Y-%m-%d"), unit_code, work_type, title, description, 0, 1, "정비1팀"]
        )

    # EXCLUDE 키워드 검증용
    if cleanings:
        rows.append(
            [
                (cleanings[0].at - timedelta(days=20)).strftime("%Y-%m-%d"),
                unit_code,
                "계획",
                "HRSG 세정 계획 취소",
                "예산 사유로 금회 세정 미시행",
                0,
                0,
                "발전팀",
            ]
        )

    rows.sort(key=lambda r: r[0])
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("w", encoding="utf-8-sig", newline="") as fp:
        writer = csv.writer(fp)
        writer.writerow(
            ["작업일", "호기", "작업구분", "제목", "내용", "비용", "소요일수", "작업자"]
        )
        writer.writerows(rows)


def write_truth_csv(path: str, frame: pd.DataFrame) -> None:
    """정답 fouling_level 일별 중앙값 — FI 산출 정확도 검증용 (specs/17 §5)."""
    truth = (
        frame.set_index("timestamp")["_fouling_level"]
        .resample("1D")
        .median()
        .dropna()
        .rename("fouling_level")
        .reset_index()
    )
    truth.columns = ["date", "fouling_level"]
    truth["date"] = truth["date"].dt.strftime("%Y-%m-%d")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    truth.to_csv(path, index=False, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    rng = np.random.default_rng(args.seed + 1)  # 출력 단계 전용 스트림

    frame, cleanings = generate(args)
    written = inject_mess(frame, rng) if args.messy else frame
    write_operation_csv(written, args, rng)

    if args.maintenance_out:
        period = (
            frame["timestamp"].min().to_pydatetime(),
            frame["timestamp"].max().to_pydatetime(),
        )
        write_maintenance_csv(args.maintenance_out, args.unit_code, cleanings, period, rng)
    if args.truth_out:
        write_truth_csv(args.truth_out, frame)

    # 요약 출력 (specs/17 §5)
    print(f"호기         : {args.unit_code}")
    print(f"기간         : {frame['timestamp'].min()} ~ {frame['timestamp'].max()}")
    print(f"행수         : {len(written):,}")
    print(f"세정 횟수    : {len(cleanings)}")
    for i, event in enumerate(cleanings, 1):
        before = frame.loc[frame["timestamp"] < event.at, "_fouling_level"]
        level = before.iloc[-1] if len(before) else 0.0
        print(
            f"  {i}차 {event.at:%Y-%m-%d} {event.method} "
            f"비용 {event.cost:,}원 세정직전 fouling_level={level:.3f}"
        )
    print(f"출력 파일    : {args.out}")
    if args.maintenance_out:
        print(f"정비 이력    : {args.maintenance_out}")
    if args.truth_out:
        print(f"정답값       : {args.truth_out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
