# 05. 계산기

관련 요구사항: CALC-1 ~ CALC-10. 의존: `06-reference-data.md`(GT 모델·공법·SMP·파라미터)

---

## 1. 목적

가스터빈 모델과 현재 운전값을 넣으면 **현재 상태, 예상 손실, 세정 시 회수 효과**를 즉시 보여 준다.
질의응답의 수치도 전부 이 계산기에서 나온다(`02` CHAT-3).

> **계산식은 `[임시값]` 이다.** 실무진이 다년간의 세정 실적으로 만든 자체 산정 방식을 받기 전까지,
> 이전 앱의 편익 모델(`archive/v1-fouling-advisor/09-benefit-model.md`)을 입력 기반으로 바꿔 쓴다(§6).
> `[실무 논의]` 산정 방식 제공 시점과 형태. 받으면 §6 을 통째로 교체하고 `formula_version` 을 올린다.

## 2. 화면 구성 (CALC-5, CALC-6)

탭 3개: **손실·회수 효과** / **공법별 비용 비교** / **핀치·어프로치 점검**. 모든 탭이 같은 GT 모델 선택을 공유한다.

- **CALC-5 시각화**
  - 게이지: 운전 상태 변수별(배압, 배기온도) 현재값 · 경보 · 트립 위치
  - HRSG 도식(SVG): GT 배기 → 과열기 → 증발기 → 절탄기 → 굴뚝. 구간별 온도와 핀치·어프로치 위치, 상태 색
  - 그래프(Chart.js): 손실 구성(GT/ST), 공법별 순편익·회수 기간
  - 큰 숫자: 일 손실(원/일), 회수 기간(일), 상태
- **CALC-6 즉시 반응:** 값을 바꾸면 300ms 디바운스 후 서버에 계산을 요청하고 결과를 갱신한다.
  - 계산식이 비공개라 브라우저에서 계산하지 않는다(CALC-8). 그래서 서버 응답이 빨라야 한다(p95 300ms 이하, `13` §2).
  - 요청 중에는 이전 결과를 흐리게 유지한다(깜빡임 금지). 늦게 도착한 응답은 버린다 — 마지막 요청만 반영.
  - 입력 오류는 해당 칸 아래에 바로 표시하고, 오류가 있는 동안은 요청하지 않는다.
- 입력값은 URL 쿼리에 담아 공유·새로고침 시 복원한다. 챗봇 계산 카드의 "계산기에서 열기"도 이 방식이다.

## 3. 손실·회수 효과 (CALC-1, CALC-2)

### 3.1 입력

| 필드 | 단위 | 기본값 | 검증 |
|---|---|---|---|
| `gt_model_id` | – | 첫 모델 | 참조표에 있고 사용 중 |
| `gt_power_mw` | MW | 모델 정격 | 0 < x ≤ 정격 × 1.2 |
| `backpressure_kpa` | kPa | 모델 설계 배압 | 0 ≤ x ≤ 50 |
| `clean_backpressure_kpa` | kPa | 모델 설계 배압 | 0 ≤ x ≤ 50 |
| `exhaust_temp_c` | ℃ | 모델 설계 배기온도 | 200 ≤ x ≤ 700 |
| `stack_temp_c` | ℃ | 모델 설계 굴뚝 온도 | 40 ≤ x ≤ 250 |
| `clean_stack_temp_c` | ℃ | 모델 설계 굴뚝 온도 | 40 ≤ x ≤ 250 |
| `operating_hours_per_day` | h | 설정값 | 0 < x ≤ 24 |
| `smp_won_per_kwh` | 원/kWh | 등록된 최신 SMP | 0 < x ≤ 1000 |
| `cleaning_method_id` | – | 설정 `calc_default_method` | 사용 중인 공법 |

- 검증 범위는 물리적 타당성 검사이며 튜닝값이 아니다(코드의 이름 붙은 상수로 둔다).
- SMP 를 사용자가 바꾸면 결과에 "사용자 입력 SMP"로 표시한다(`06` REF-4).

### 3.2 운전 상태 판정 (CALC-2)

- **CALC-2** 판정 변수별로 GT 모델의 한계값과 비교한다.

  | 판정 | 조건 | 표시 |
  |---|---|---|
  | 정상 | 값 < 경보 한계 | 초록 "정상" |
  | 경보 | 경보 한계 ≤ 값 < 트립 한계 | 주황 "주의 — 경보 구간" |
  | 트립 | 값 ≥ 트립 한계 | 빨강 "위험 — 트립 구간" |

  - 판정 변수: `backpressure_kpa`(배압), `exhaust_temp_c`(배기온도). 종합 상태는 가장 나쁜 변수를 따른다.
  - 각 변수에 "경보 한계 대비 N %"(게이지에는 트립 위치도)를 함께 보여 준다. 한계값 원본 필드는 USER 응답에 넣지 않는다.
    **단, 현재값과 비율이 함께 보이므로 한계값은 역산된다**(4.6 kPa ÷ 102.2 % ≈ 4.5 kPa). 한계값을 정말 숨겨야 한다면
    비율도 빼고 상태만 보여 줘야 한다 — `[실무 논의]` P4 에서 정한다. 지금은 비율을 보여 준다.
  - `[실무 논의]` 판정 변수 추가 여부, 경보 전 "주의" 구간을 따로 둘지(예: 경보의 90%).
  - 색만으로 구분하지 않고 문구·아이콘을 함께 쓴다(`12` UI-5).

### 3.3 출력

| 필드 | 단위 |
|---|---|
| `status` · `status_by_variable[]` | 정상/경보/트립, 변수별 값·한계 대비 비율 |
| `delta_backpressure_kpa`, `delta_stack_temp_c` | kPa, ℃ |
| `power_loss_gt_mw`, `power_loss_st_mw`, `power_loss_total_mw` | MW |
| `daily_loss_won`, `monthly_loss_won` | 원/일, 원/30일 |
| `recovered_daily_won` | 원/일 |
| `cleaning_total_cost_won` | 원 |
| `net_benefit_won` | 원(평가 기간) |
| `payback_days` | 일(회수 불가면 `null` → "회수 불가") |
| `param_version`, `formula_version`, `smp_as_of`, `smp_source`, `uses_placeholder` | 재현·표시용 |

- 계산 불가 값은 `null` 이며 화면에 "계산 불가"로 표시한다. **0 으로 표시하지 않는다.**

## 4. 공법별 비용 비교 (CALC-3)

- **CALC-3** §3 의 입력으로, 사용 중인 모든 공법에 대해 세정 비용, 정지 손실, 총비용, 회수 효과, 순편익, 회수 기간을 계산해
  표와 막대그래프로 비교한다. 순편익이 가장 큰 공법을 강조하되 "권장" 대신 "순편익 최대"라고 표기한다.
- `[실무 논의]` 공법 목록과 공법별 비용·정지 일수·회복률(`06` §3 은 `[임시값]`).

## 5. 핀치·어프로치 점검 (CALC-4)

### 5.1 입력 (압력단별)

| 필드 | 단위 |
|---|---|
| `drum_pressure_barg` | bar(g) |
| `evaporator_outlet_gas_temp_c` | ℃ |
| `economizer_outlet_water_temp_c` | ℃ |
| `design_pinch_c`, `design_approach_c` | ℃ (선택 — 없으면 설정의 기준 범위 사용) |

- 압력단(HP/IP/LP)은 1~3개를 추가해 각각 입력한다. `[실무 논의]` 다중 압력 처리 방식과 압력 단위(게이지/절대).

### 5.2 계산

```
T_sat      = IAPWS-IF97 Region 4 포화온도(P_abs),  P_abs = drum_pressure_barg + 1.01325   [bar(a)]
pinch      = evaporator_outlet_gas_temp_c − T_sat
approach   = T_sat − economizer_outlet_water_temp_c
```

- 포화온도는 공개 공식(IAPWS-IF97 식 31)을 순수 함수로 구현한다(외부 라이브러리 불필요). 검증값:
  0.1 MPa → 99.606 ℃, 1 MPa → 179.886 ℃, 10 MPa → 310.999 ℃.
- 판정: 설계값이 있으면 `설계값 + calc_pinch_margin_c` 초과 시 주의, 없으면 설정 범위(`calc_pinch_range_c`, `calc_approach_range_c`)로 판정한다. `[임시값]`
- `approach < 0`(스티밍 우려)이면 위험으로 표시한다.
- 핀치·어프로치는 공개 열역학 계산이므로 식을 화면에 보여 줘도 된다(CALC-8 의 비공개 대상은 §6 손실 모델이다).

## 6. 임시 계산식 `[임시값]` (formula_version = `v0-placeholder`)

```
Δdp    = max(0, backpressure_kpa − clean_backpressure_kpa)
Δstack = max(0, stack_temp_c − clean_stack_temp_c)

load_ratio  = gt_power_mw / rated_gt_mw
P_loss_gt   = rated_gt_mw × dp_power_loss_coeff / 100 × Δdp × load_ratio
P_loss_st   = rated_st_mw × stack_temp_loss_coeff / 100 × Δstack × load_ratio
P_loss      = P_loss_gt + P_loss_st                                             [MW]

daily_loss  = P_loss × operating_hours_per_day × capacity_factor × 1000 × smp   [원/일]

공법 m:
  recovered_daily = daily_loss × recovery_ratio[m]
  outage_loss     = (rated_gt_mw + rated_st_mw) × 24 × capacity_factor × outage_days[m] × 1000
                    × smp × (1 − fuel_cost_ratio)
  total_cost      = cleaning_cost_won[m] + outage_loss
  gross_benefit   = recovered_daily × evaluation_horizon_days × 0.5     (선형 재오염 가정)
  net_benefit     = gross_benefit − total_cost
  payback_days    = total_cost / recovered_daily          (recovered_daily = 0 이면 null)
```

- 계수(`dp_power_loss_coeff` 0.35, `stack_temp_loss_coeff` 0.12, `capacity_factor` 0.85, `fuel_cost_ratio` 0.792,
  `evaluation_horizon_days` 365)는 계산 파라미터 세트(`06` §5)에 있고 관리자가 바꾼다.
- `load_ratio` 는 이전 앱에 없던 항이다. 부분 부하에서 손실을 과대 계상하지 않도록 넣었다(보수적 방향).
- `rated_st_mw` 가 비어 있으면 `rated_gt_mw × 0.5` 로 가정하고 결과에 안내를 붙인다.
- 정지 손실은 매출이 아니라 **마진 기준**이다(이전 앱의 결정 유지 — 정지 중에는 연료를 쓰지 않는다).

## 7. 보수적 추정 (CALC-9)

- **CALC-9** 불확실한 항은 손실·회수 효과를 **작게**, 비용을 **크게** 보는 쪽으로 처리한다.
  임시로 적용하는 규칙: `max(0, …)` 로 음의 차이 무시, 부분 부하 비례(`load_ratio`), 선형 재오염 0.5 계수, 회복률 1 미만.
- `[실무 논의]` "보수적"의 구체적 정의(예: 실적 분포의 하위 분위수 사용).

## 8. 비공개 (CALC-8)

- **CALC-8** §6 의 식과 계수는 서버에만 있다.
  - USER 용 계산 API 응답에는 입력과 §3.3 의 결과만 있다. 계수·식·중간 계수 곱은 없다.
  - 계산 파라미터 조회 API 는 관리자 전용이다.
  - 프론트엔드 번들에 계수·식이 없다(빌드 산출물 검사로 확인).
  - LLM 에도 결과만 준다(`04` LLM-6).

## 9. 결정론·재현 (CALC-7, CALC-10)

- **CALC-7** 계산은 `calculator/services/*.py` 의 **순수 함수**다(Django 모델 import 금지). 난수·현재 시각을 쓰지 않는다.
  같은 입력 + 같은 파라미터 버전 + 같은 참조값이면 결과가 항상 같다.
- **CALC-10** 결과에 `param_version`, `formula_version`, 사용한 GT 모델·공법의 버전, SMP 기준일을 붙인다.
  챗봇 계산 카드는 이 값을 그대로 저장한다.

## 10. 수용 기준 (AC)

- [ ] AC-05-1 같은 입력으로 100회 계산하면 결과가 모두 같다(검수 1).
- [ ] AC-05-2 가상 검증 사례(손계산 기대값) 10건이 소수점 반올림 범위에서 일치한다(검수 2).
- [ ] AC-05-3 배압을 경보 한계 직전 → 경보 한계 → 트립 한계로 바꾸면 상태가 정상 → 경보 → 트립으로 즉시 바뀌고 색·문구가 함께 바뀐다(검수 3).
- [ ] AC-05-4 포화온도 함수가 IF97 검증값 3개와 0.01 ℃ 이내로 일치한다.
- [ ] AC-05-5 USER 권한 계산 응답과 프론트 빌드 산출물에 계수 이름·값이 없다.
- [ ] AC-05-6 `Δ` 가 음수이면 손실이 0 이고, 회수 효과가 0 이면 회수 기간이 "회수 불가"로 표시된다(0 으로 표시하지 않음).
- [ ] AC-05-7 입력을 빠르게 연속 변경해도 마지막 입력의 결과만 남는다.
- [ ] AC-05-8 임시 참조값을 쓴 계산에는 "임시 참조값 사용" 안내가 보인다.
- [ ] AC-05-9 계산 API p95 응답 시간이 300ms 이하다.
