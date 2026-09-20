# 17. 가상 샘플 데이터 생성 스크립트

관련 요구사항: FR-D-07

---

## 1. 목적
개발·검증용으로 **오염이 서서히 진행되다 세정 시점에 회복되는 패턴이 2~3회 반복되는** 가상 운전 데이터를 생성한다.
이 데이터는 전 파이프라인(업로드 → 정제 → 모델 → FI → 추세 → 편익 → 리포트)의 동작을 검증하는 기준이 된다.

## 2. 위치 및 실행

```
backend/scripts/generate_sample_data.py
```

```bash
python scripts/generate_sample_data.py \
    --unit-code U1 \
    --start 2023-01-01 --months 24 \
    --interval-min 10 \
    --rated-mw 160 --rated-st-mw 80 \
    --cleanings 3 \
    --seed 42 \
    --out sample_unit1.csv \
    --maintenance-out sample_unit1_maintenance.csv \
    --korean-headers
```

| 인자 | 기본값 | 설명 |
|------|--------|------|
| `--unit-code` | `U1` | 호기 코드(파일명·이력에 사용) |
| `--start` | `2023-01-01` | 시작일 |
| `--months` | 24 | 생성 기간(개월) |
| `--interval-min` | 10 | 샘플링 주기 |
| `--rated-mw` | 160 | GT 정격 출력 |
| `--rated-st-mw` | 80 | ST 정격 출력 |
| `--cleanings` | 3 | 세정 이벤트 횟수 (2~3 권장) |
| `--fouling-rate` | 자동 | 오염 진행 속도(일당 차압 상승률) |
| `--noise-level` | 1.0 | 노이즈 배율 |
| `--seed` | 42 | 난수 시드(재현성) |
| `--out` | – | 운전 데이터 CSV 경로 |
| `--maintenance-out` | – | 정비 이력 CSV 경로 |
| `--korean-headers` | off | 한글 컬럼명으로 출력(컬럼 매핑 테스트용) |
| `--messy` | off | 결측·이상치·형식 오류를 의도적으로 주입 |

## 3. 생성 모델

### 3.1 운전 프로파일
```
부하 패턴 (일간)
  - 06~22시: 고부하 (정격의 85~100%)
  - 22~06시: 중부하 (정격의 55~75%)
  - 주말: 전체적으로 10% 낮게
  - 매주 랜덤 1~2회: 기동/정지 이벤트(야간 정지 → 아침 기동)
  - 연 2회: 계획 정비 정지 (7~10일)

외기온도
  ambient_temp_c = 14 + 12·sin(2π(doy - 100)/365) + 5·sin(2π(hour-9)/24) + N(0, 1.5)

습도 / 대기압
  humidity_pct = 60 + 20·sin(...) + N(0,5),  clip(20, 95)
  ambient_pressure_kpa = 101.3 + N(0, 0.4)
```

### 3.2 기저 물리 모델 (청정 상태)
```
load_ratio      = gt_power_mw / rated_mw
exhaust_flow    = 450 · load_ratio · (288 / (ambient_temp_c + 273)) · (1 + N(0, 0.01))   [kg/s]
gt_exhaust_temp = 560 + 60·load_ratio - 0.4·ambient_temp_c + N(0, 3)                     [℃]

# 차압: 유량 제곱에 비례
dp_clean        = k_dp · (exhaust_flow / 450)²                      k_dp ≈ 2.5 [kPa]

# 스택온도: 배기온도·부하·급수온도의 함수
stack_clean     = 95 + 0.02·(gt_exhaust_temp - 560) + 12·load_ratio + 0.15·ambient_temp_c + N(0, 1.2)  [℃]
```

### 3.3 오염 진행 모델
세정 사이클마다 오염이 누적된다.
```
t_c = 마지막 세정 이후 경과일

# 포화형 진행 (초기 빠름 → 점차 둔화). 선형 옵션도 제공
fouling_level(t_c) = F_max · (1 - exp(-t_c / τ))        # τ ≈ 180일, F_max ≈ 1.0
  또는 선형:  fouling_level(t_c) = min(t_c / T_full, 1.0)

# 덕트버너 가동 누적은 오염을 가속
fouling_level *= (1 + 0.3 · duct_burner_hours_ratio)

# 오염이 관측량에 주는 영향
dp_meas     = dp_clean    · (1 + dp_fouling_gain    · fouling_level)     # dp_fouling_gain ≈ 0.35
stack_meas  = stack_clean + stack_fouling_gain · fouling_level           # stack_fouling_gain ≈ 14 [℃]

# 오염에 따른 출력 손실(편익 검증용 정합성 확보)
gt_power_actual = gt_power_target · (1 - 0.0035 · (dp_meas - dp_clean))
st_power        = rated_st_mw · load_ratio · (1 - 0.0012 · (stack_meas - stack_clean))
```

### 3.4 세정 이벤트
- 세정 시점은 전체 기간을 `cleanings + 1` 구간으로 나눈 경계 부근(±15일 랜덤)에 배치한다.
- 세정 시점에 `fouling_level`을 `residual_fouling`(기본 0.05~0.15 랜덤)으로 리셋한다 → **완전 회복이 아닌 현실적 회복**.
- 세정 기간(기본 2일) 동안은 정지 상태(출력 0)로 만든다.
- 세정 방법은 `화학세정`, `수세`, `드라이아이스` 중 랜덤 배정.

### 3.5 덕트버너
- 고부하 시간대 중 랜덤 15%의 날에 2~6시간 가동(`duct_burner_on = 1`).
- 가동 시 `gt_exhaust_temp`와 `stack_temp`를 각각 +25 ℃, +18 ℃ 상승시킨다.
  → 분석 파이프라인이 이 구간을 제외하지 않으면 FI가 왜곡되므로, **필터 검증용 노이즈**로 기능한다.

### 3.6 `--messy` 옵션 주입 항목
| 항목 | 주입 내용 |
|------|-----------|
| 결측 | 랜덤 0.5% 셀을 빈 값으로 |
| 문자열 오류 | 0.1% 셀에 `Bad`, `I/O Timeout`, `N/A` 삽입 |
| 이상치 스파이크 | 0.05% 행에 물리 범위 밖 값 |
| 고정값 | 랜덤 2~3구간에서 차압 값을 6시간 고정 |
| 시각 중복 | 랜덤 50행 중복 |
| 시각 역순 | 랜덤 구간 순서 섞기 |
| 형식 혼합 | 타임스탬프 형식을 `YYYY-MM-DD HH:MM:SS`와 `YYYY/MM/DD HH:MM` 혼용 |

## 4. 출력 파일

### 4.1 운전 데이터 CSV (영문 헤더 기본)
```
timestamp,gt_power_mw,ambient_temp_c,gt_exhaust_temp_c,exhaust_flow,fuel_flow,
igv_position_pct,hrsg_gas_dp_kpa,gt_backpressure_kpa,stack_temp_c,duct_burner_on,
st_power_mw,steam_flow_tph,feedwater_temp_c,ambient_pressure_kpa,humidity_pct
```

### 4.2 `--korean-headers` 사용 시 (컬럼 매핑 검증용)
```
시각,GT출력(MW),대기온도(℃),GT배기온도(℃),배기유량(kg/s),연료유량(Nm3/h),
IGV개도(%),HRSG가스차압(kPa),GT배압(kPa),스택온도(℃),덕트버너상태,
ST출력(MW),증기유량(t/h),급수온도(℃),대기압(kPa),습도(%)
```

### 4.3 정비 이력 CSV
```
작업일,호기,작업구분,제목,내용,비용,소요일수,작업자
2023-06-14,U1,계획정비,HRSG 전열면 화학세정 시행,가스측 차압 상승에 따른 화학세정 실시,28000000,2,정비2팀
2023-03-02,U1,점검,GT 연소기 육안 점검,정기 점검 결과 이상 없음,0,1,정비1팀
```
- 세정 이벤트에 대응하는 행과, 오염과 무관한 잡음 행(전체의 70%)을 섞어 **키워드 추출 정확도**를 검증할 수 있게 한다.
- `EXCLUDE` 키워드 검증용 행도 포함한다(예: `HRSG 세정 계획 취소`).

## 5. 부가 기능
- `--to-db` 옵션: CSV 생성 대신 Django ORM으로 직접 `Unit`, `Measurement`, `CleaningEvent`를 적재(개발 환경 전용).
- 생성 후 요약 출력: 기간, 행수, 세정 일자 목록, 세정 직전 `fouling_level`, 기대 FI 대략값.
- 생성된 “정답값”(`fouling_level` 시계열)을 `--truth-out` 으로 별도 CSV 저장 → **FI 산출 정확도 검증**에 사용.

## 6. 검증 시나리오 (통합 테스트)
1. `generate_sample_data.py`로 24개월·세정 3회 데이터 생성
2. 호기 등록 + 컬럼 매핑(한글 헤더) 설정
3. 업로드 → 검증 통과 → 적재
4. 정비 이력 업로드 → 세정 후보 3건 추출 확인
5. 세정 이벤트 승인 → 청정 기준 기간 자동 생성
6. 분석 실행 → 모델 R² ≥ 0.85 확인
7. FI 시계열에서 세정 시점마다 급락 확인, 사이클 내 단조 증가 확인
8. 생성 정답값(`fouling_level`)과 FI의 상관계수 ≥ 0.9 확인
9. D-day, 편익, PDF/엑셀 리포트 생성 확인

## 7. 수용 기준 (AC)
- [ ] AC-17-1: 동일 `--seed`로 실행하면 완전히 동일한 파일이 생성된다.
- [ ] AC-17-2: 생성 데이터의 FI 시계열이 세정 시점마다 뚜렷이 하락한다.
- [ ] AC-17-3: 정답값과 산출 FI의 상관계수가 0.9 이상이다.
- [ ] AC-17-4: `--messy` 옵션 데이터가 업로드 검증에서 오류·경고로 정확히 잡힌다.
- [ ] AC-17-5: `--korean-headers` 파일이 컬럼 매핑을 통해 정상 적재된다.
