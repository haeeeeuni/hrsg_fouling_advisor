# 09. 세정 회수 편익 산출 모델

관련 요구사항: FR-U-12, FR-A-05

---

## 1. 목적
세정을 시행했을 때 회복되는 출력·효율 이득과 세정에 드는 비용을 비교해 **순편익, 회수기간, 최적 세정 시점**을 제시한다.

## 2. 손실 메커니즘 (물리적 근거)

| 경로 | 설명 | 지표 |
|------|------|------|
| ① 배압 상승 손실 | 가스측 차압 상승 → GT 배압 상승 → GT 출력 감소·열소비율 악화 | Δ차압 (kPa) |
| ② 배열회수 손실 | 전열면 오염 → 열전달 저하 → 스택온도 상승 → 증기 생산 감소 → ST 출력 감소 | Δ스택온도 (℃) |

두 손실을 각각 MW로 환산한 뒤 합산한다.

## 3. 입력 파라미터

### 3.1 관리자 기본값 (DB 저장, FR-A-05)
| 키 | 설명 | 기본값 | 단위 |
|----|------|--------|------|
| `electricity_price` | 전력 판매/기회 단가 | 120 | 원/kWh |
| `fuel_price` | 연료 단가 | 900 | 원/Nm³ |
| `cleaning_cost` | 세정 1회 비용 | 30,000,000 | 원 |
| `outage_days` | 세정 정지 일수 | 2.0 | 일 |
| `dp_power_loss_coeff` | 배압 손실 계수 — 차압 1 kPa 상승당 GT 출력 손실 | 0.35 | %MW / kPa |
| `stack_temp_loss_coeff` | 스택온도 손실 계수 — 1 ℃ 상승당 ST 출력 손실 | 0.12 | %MW(ST) / ℃ |
| `heat_rate_penalty_coeff` | 차압 1 kPa 상승당 열소비율 악화 | 0.30 | % / kPa |
| `operating_hours_per_day` | 일 평균 운전시간 | 20 | h/일 |
| `capacity_factor` | 이용률 | 0.85 | – |
| `cleaning_recovery_ratio` | 세정 후 회복률(완전 회복 = 1.0) | 0.9 | – |
| `evaluation_horizon_days` | 편익 평가 기간 | 365 | 일 |
| `discount_rate_annual` | 할인율(선택, NPV 계산용) | 0.0 | – |

- 모든 값은 **호기별 오버라이드**가 가능하다.
- 계수의 기본값은 참고치이며, 관리자가 실적 데이터에 맞춰 보정해야 함을 화면에 명시한다.

### 3.2 분석별 임시 변경 (FR-U-12)
- 사용자는 분석 실행 화면에서 위 값들을 **해당 분석에 한해** 임시로 변경할 수 있다.
- 임시값은 `AnalysisRun.benefit_params_snapshot`에 저장되고, **관리자 기본값은 변경되지 않는다.**
- 화면에는 기본값 대비 변경된 항목을 강조 표시하고 “이 분석에만 적용됨” 안내를 표시한다.

## 4. 계산식

### 4.1 현재 손실 출력
```
Δdp_current   = 현재 평균 실측 차압 − 현재 평균 기대 차압            [kPa]
Δstack_current = 현재 평균 실측 스택온도 − 현재 평균 기대 스택온도    [℃]

GT 출력 손실  P_loss_gt = rated_power_mw × (dp_power_loss_coeff / 100) × Δdp_current       [MW]
ST 출력 손실  P_loss_st = rated_st_power_mw × (stack_temp_loss_coeff / 100) × Δstack_current [MW]
              (ST 정격이 없으면 st_power_mw 평균값 사용, 없으면 GT 정격 × 0.5 가정 + 경고)

총 손실 출력  P_loss_total = P_loss_gt + P_loss_st                                          [MW]
```
- `Δ`가 음수이면 0으로 처리한다.
- 계산은 군집별로 수행한 뒤 **표본 수 가중 평균**한다(운전 조건에 따라 손실이 다르므로).

### 4.2 현재 일일 손실 비용
```
daily_energy_loss = P_loss_total × operating_hours_per_day × capacity_factor    [MWh/일]
daily_loss_cost   = daily_energy_loss × 1000 × electricity_price                [원/일]
```

### 4.3 연료 측 추가 손실 (열소비율 악화, 선택 계산)
```
heat_rate_penalty_pct = heat_rate_penalty_coeff × Δdp_current                   [%]
daily_fuel_cost_base  = 일평균 연료 사용량 × fuel_price                          [원/일]
daily_fuel_loss       = daily_fuel_cost_base × heat_rate_penalty_pct / 100       [원/일]
```
- 연료 사용량 데이터가 없으면 이 항을 0으로 두고 “연료 손실 미반영” 표시.

### 4.4 세정 비용
```
outage_loss = rated_total_power_mw × 24 × capacity_factor × outage_days × 1000 × electricity_price
total_cleaning_cost = cleaning_cost + outage_loss                                [원]
```
- `outage_days = 0`(운전 중 세정, on-line cleaning)이면 정지 손실은 0.

### 4.5 세정 회수 편익
```
recovered_daily_benefit = (daily_loss_cost + daily_fuel_loss) × cleaning_recovery_ratio   [원/일]

평가기간 총 회수액 gross_benefit = Σ(t=1..H) recovered_daily_benefit(t)
  - 기본: 오염이 세정 후 다시 진행되므로, 추세 기울기 b를 반영해
    회수액이 시간에 따라 감소하는 형태로 적분한다.
    간이식:  gross_benefit ≈ recovered_daily_benefit × H × 0.5   (선형 재오염 가정)
    정밀식:  일자별 FI 추세를 세정 시점부터 재투영하여 일별 손실 차이를 합산
  - 구현은 정밀식을 기본으로 하고, 간이식은 비교값으로 함께 표시한다.

순편익 net_benefit = gross_benefit − total_cleaning_cost                          [원]
회수기간 payback_days = total_cleaning_cost / recovered_daily_benefit             [일]
ROI = net_benefit / total_cleaning_cost × 100                                     [%]
```

### 4.6 최적 세정 시점
- 세정 시점을 오늘부터 `evaluation_horizon_days`까지 하루 단위로 이동시키며 **평가 기간 내 누적 순편익**을 계산하고, 최대가 되는 날짜를 “권고 세정 시점”으로 제시한다.
- 동시에 **“지금 세정 / 임계치 도달 시 세정 / 계획 정비 시 세정”** 3개 시나리오의 순편익을 표로 비교한다.
- 세정을 하루 미룰 때의 추가 손실(`daily_loss_cost`)을 “지연 비용(원/일)”로 강조 표시한다.

## 5. 민감도 분석
주요 파라미터(`electricity_price`, `cleaning_cost`, `dp_power_loss_coeff`, `outage_days`)를 ±30% 변동시켰을 때의 순편익 변화를 **토네이도 차트**로 제공한다. (P1)

## 6. 출력 (대시보드/리포트 표시 항목)
| 항목 | 예시 |
|------|------|
| 현재 손실 출력 | 2.8 MW (GT 1.9 / ST 0.9) |
| 일일 손실 비용 | 5,712,000 원/일 |
| 세정 비용(정지 손실 포함) | 30,000,000 + 244,800,000 원 |
| 세정 시 예상 회수 편익(1년) | 1,043,000,000 원 |
| 순편익 | 768,200,000 원 |
| 회수기간 | 48일 |
| 지연 비용 | 5,712,000 원/일 |
| 권고 세정 시점 | 2025-12-01 (D-72) |

## 7. 데이터 모델
```
BenefitResult
  - analysis_run (FK)
  - params_snapshot : JSON (적용된 모든 계수)
  - delta_dp_kpa / delta_stack_c
  - power_loss_gt_mw / power_loss_st_mw / power_loss_total_mw
  - daily_loss_cost / daily_fuel_loss
  - cleaning_cost / outage_loss / total_cleaning_cost
  - gross_benefit / net_benefit / payback_days / roi_pct
  - recommended_cleaning_date
  - scenarios : JSON (시나리오별 순편익)
  - sensitivity : JSON (선택)
```

## 8. 예외 처리
| 상황 | 처리 |
|------|------|
| `recovered_daily_benefit ≤ 0` | 회수기간 `null`, “현재 오염 수준에서 세정 경제성 없음” 표시 |
| ST 정격 출력 미등록 | GT 정격 × 0.5로 가정하고 경고 배지 표시 |
| 연료 데이터 없음 | 연료 손실 0 처리 + “미반영” 표시 |
| 파라미터 음수 입력 | 400 `INVALID_BENEFIT_PARAM` |

## 9. 표기 규칙
- 금액은 `#,##0 원`, 억 단위 병기(예: `768,200,000 원 (7.68억)`).
- 모든 편익 수치 옆에 **적용된 주요 가정**(전력단가, 손실계수)을 각주로 표기한다. 근거 없는 단정을 피한다.

## 10. 수용 기준 (AC)
- [ ] AC-09-1: 전력 단가를 2배로 하면 일일 손실 비용과 순편익이 그에 비례해 증가한다.
- [ ] AC-09-2: 분석별 임시 입력값을 변경해도 관리자 기본 설정값은 바뀌지 않는다.
- [ ] AC-09-3: 편익 결과에 적용 파라미터 스냅샷이 함께 저장되어 재현 가능하다.
- [ ] AC-09-4: 오염도 0 상태에서 순편익이 음수(세정 비경제)로 계산된다.
- [ ] AC-09-5: 3개 시나리오 비교표가 리포트에 포함된다.
