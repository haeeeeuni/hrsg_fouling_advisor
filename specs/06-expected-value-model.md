# 06. 기대 차압·기대 스택온도 예측 모델

관련 요구사항: FR-U-07, FR-U-08, FR-A-08

---

## 1. 목적
“같은 운전 조건에서 **청정 상태**라면 나왔어야 할 차압과 스택온도”를 예측한다.
실측값과의 차이(잔차)가 오염의 직접 신호가 된다.

## 2. 핵심 개념: 청정 기준 기간 (Clean Baseline)

- 모델은 **오염이 없다고 간주되는 구간**으로만 학습한다.
- 청정 기준 기간 결정 우선순위
  1. 관리자가 명시 지정한 기간 (`CleanBaselinePeriod`)
  2. 세정 이력이 있으면 **세정 완료일 + `baseline_offset_days`(기본 1일) 부터 `baseline_length_days`(기본 30일)**
  3. 세정 이력이 없으면 **해당 호기 데이터의 최초 `baseline_length_days`** 를 사용하고 “청정 기준 미확인” 경고 표시
- 청정 기준 기간의 유효 포인트가 `min_baseline_points`(기본 1,000) 미만이면 경고하고, 기간 확장을 제안한다.
- 여러 세정 이력이 있으면 관리자는 **가장 최근 세정 후 구간**을 기본으로 하되, 복수 구간을 합쳐 학습하도록 선택할 수 있다.

## 3. 타깃과 피처

### 3.1 타깃 (2개 모델)
| 모델 | 타깃 | 대체 |
|------|------|------|
| `MODEL_DP` | `hrsg_gas_dp_kpa` | 없으면 `gt_backpressure_kpa` |
| `MODEL_ST` | `stack_temp_c` | – |

### 3.2 피처 (사용 가능한 것만 자동 선택)
| 피처 | 필수 | 비고 |
|------|------|------|
| `gt_power_mw` | ✔ | 부하 |
| `ambient_temp_c` | ✔ | 외기온 |
| `gt_exhaust_temp_c` | ✔ | 배기온도 |
| `exhaust_flow` / `fuel_flow` / `igv_position_pct` | ✔(택1) | 유량 대체 지표 |
| `ambient_pressure_kpa` | – | 있으면 사용 |
| `humidity_pct` | – | 있으면 사용 |
| `steam_flow_tph` | – | `MODEL_ST`에 유효 |
| `feedwater_temp_c` | – | `MODEL_ST`에 유효 (스택온도에 직접 영향) |
| `load_band`, `season` | – | 원-핫 인코딩(규칙 기반 군집 사용 시) |

### 3.3 파생 피처
- `flow_squared` = 유량² (차압은 유량 제곱에 비례 — 물리적 근거)
- `load_ratio` = `gt_power_mw / rated_power_mw`
- `delta_t` = `gt_exhaust_temp_c - stack_temp_c` (MODEL_DP 전용 참고 피처, MODEL_ST에는 타깃 누설이므로 **사용 금지**)

> **타깃 누설 금지 규칙:** `MODEL_ST`의 피처에 `stack_temp_c`에서 파생된 값을 넣지 않는다. `MODEL_DP`의 피처에 `hrsg_gas_dp_kpa`/`gt_backpressure_kpa` 파생값을 넣지 않는다.

## 4. 알고리즘

두 가지를 제공하고 관리자가 선택한다(기본: `GBR`).

| 코드 | 알고리즘 | 용도 |
|------|----------|------|
| `RIDGE` | `Ridge` (다항 2차 확장 + StandardScaler, Pipeline) | 해석 용이, 표본 적을 때 안정 |
| `GBR` | `GradientBoostingRegressor` 또는 `HistGradientBoostingRegressor` | 비선형 관계 포착, 기본값 |

### 하이퍼파라미터 기본값 (설정 가능)
```
RIDGE : alpha=1.0, poly_degree=2
GBR   : n_estimators=300, learning_rate=0.05, max_depth=3,
        min_samples_leaf=20, subsample=0.9, random_state=RANDOM_SEED
```

- 모든 모델은 `sklearn.pipeline.Pipeline`으로 구성해 전처리(결측 대치, 스케일링, 인코딩)를 포함한다.
- 재현성을 위해 `random_state`는 공통 상수로 고정한다.

## 5. 학습·검증 절차

```
청정 기준 기간 데이터 (정제 완료, STEADY 구간만)
  → 시간 순 분할: 학습 70% / 검증 30%  (TimeSeriesSplit 또는 앞/뒤 분할)
  → 학습
  → 검증셋 지표 산출: MAE, RMSE, R², MAPE
  → 교차검증(TimeSeriesSplit, n_splits=5) 평균 지표 병기
  → ModelVersion 저장
```

- 시계열이므로 **무작위 셔플 분할을 쓰지 않는다.**
- 검증 지표가 기준 미달이면 경고를 표시하되 분석은 진행한다.

### 정확도 기준 (설정값, 기본)
| 지표 | 대상 | 양호 | 주의 | 불량 |
|------|------|------|------|------|
| R² | 차압 | ≥ 0.85 | 0.70 ~ 0.85 | < 0.70 |
| MAE | 차압 | ≤ 5% of 평균 | 5~10% | > 10% |
| R² | 스택온도 | ≥ 0.85 | 0.70 ~ 0.85 | < 0.70 |
| MAE | 스택온도 | ≤ 3 ℃ | 3~6 ℃ | > 6 ℃ |

## 6. 잔차 산포 (오염도 정규화에 사용)
청정 기준 기간 검증셋의 잔차 표준편차 `σ_dp`, `σ_st` 와 평균 `μ_dp`, `μ_st`(≈0)를 **모델과 함께 저장**한다.
이 값이 `07-fouling-index.md`의 정규화 기준이 된다.

## 7. 모델 버전 관리

```
ModelVersion
  - unit (FK)
  - target : 'DP' | 'STACK_TEMP'
  - algorithm : 'RIDGE' | 'GBR'
  - version : 정수 증가 (호기·타깃별)
  - baseline_start / baseline_end       # 청정 기준 기간
  - feature_list : JSON
  - hyperparams : JSON
  - metrics : JSON {mae, rmse, r2, mape, cv_mae, cv_r2}
  - residual_std / residual_mean
  - training_rows
  - artifact_path : 직렬화 파일 경로 (joblib)
  - trained_by (FK User) / trained_at
  - is_active : 호기·타깃별 1개만 True
  - notes
```

- 모델 아티팩트는 `joblib.dump`로 저장하고 경로를 DB에 기록한다. 원본 데이터는 아티팩트에 포함하지 않는다.
- 활성 모델 교체는 관리자만 가능하며, 과거 분석 결과는 당시 버전을 그대로 참조한다.

## 8. 재학습 (FR-A-08)
- 트리거: 관리자 수동 실행 / 새 세정 이력 등록 시 알림 / 데이터가 일정량 누적 시 알림.
- 재학습은 비동기 작업으로 실행하며 진행 상태를 폴링한다.
- 재학습 완료 시 **신·구 모델 지표 비교 표**를 보여주고, 관리자가 승인해야 활성화된다(자동 활성 옵션 제공).

## 9. UI 표시 (FR-U-08)
분석 결과 화면과 리포트에 다음을 표시한다.
- 모델 알고리즘, 버전, 학습 기간, 학습 표본 수
- 차압 모델: MAE, RMSE, R² (양호/주의/불량 배지)
- 스택온도 모델: MAE, RMSE, R²
- 실측 vs 예측 산점도(대각선 기준선 포함), 잔차 시계열 플롯
- 피처 중요도(GBR) 또는 계수(RIDGE) 상위 항목

## 10. 예외 처리
| 상황 | 처리 |
|------|------|
| 청정 기준 기간 데이터 부족 | `INSUFFICIENT_BASELINE` 경고, 기간 확장 또는 대체 기간 제안 |
| 학습 실패(수치 불안정 등) | `RIDGE`로 폴백하고 사유 기록 |
| 활성 모델 없음 | 분석 실행 시 자동 학습 시도, 실패 시 `NO_ACTIVE_MODEL` 오류 |
| 신규 데이터가 학습 도메인 밖 | 해당 포인트에 `OUT_OF_DOMAIN` 표시, 기대값 신뢰도 하향 |

## 11. 수용 기준 (AC)
- [ ] AC-06-1: 샘플 데이터의 청정 기준 기간으로 학습한 차압 모델의 검증 R²가 0.85 이상이다.
- [ ] AC-06-2: 학습 기간·지표·피처·하이퍼파라미터가 `ModelVersion`에 저장되고 화면에 표시된다.
- [ ] AC-06-3: 같은 데이터·설정으로 재학습하면 동일한 지표가 재현된다.
- [ ] AC-06-4: 스택온도 모델 피처에 `stack_temp_c` 파생값이 포함되지 않는다.
- [ ] AC-06-5: 모델 재학습 후 승인 전까지 기존 활성 모델이 유지된다.
