# 13. 관리자 기능

관련 요구사항: FR-A-01 ~ FR-A-10, FR-D-05

---

## 1. 목적
시스템 운영에 필요한 모든 기준값·마스터 데이터·이력을 관리자가 화면에서 직접 관리할 수 있게 한다.
**어떤 기준값도 코드에 하드코딩하지 않는다.**

## 2. 접근 제어
- `role == 'ADMIN'` 인 사용자만 `/admin/*` 라우트와 관리자 API에 접근할 수 있다.
- 서버에서 `IsAdminRole` 권한 클래스로 재검증한다.
- 모든 관리자 변경 작업은 `AuditLog`에 기록한다(행위자, 일시, 대상, 변경 전/후 JSON).

## 3. 관리자 메뉴 구성

```
관리자 콘솔
├── 사용자 관리            → 01-auth-and-users.md
├── 호기 관리              → 02-unit-and-column-mapping.md
│   └── 컬럼 매핑
├── 분석 설정
│   ├── 오염도 임계치·등급 경계·가중치
│   ├── 정제/구간 필터 임계값
│   └── 군집화 설정
├── 편익 계산 기본값       → 09-benefit-model.md
├── 세정 이력 관리         → 10-maintenance-history.md
├── 오염 키워드 사전       → 10-maintenance-history.md
├── 모델 관리
│   ├── 청정 기준 기간 지정
│   ├── 재학습 실행 및 버전 비교
│   └── 활성 모델 전환
├── 분석 실행 이력
└── 호기 간 비교 (옵션)    → 19-optional-features.md
```

## 4. 설정값 관리 (FR-D-05)

### 4.1 설정 저장 구조
```
Setting
  - key         : 설정 키 (예 'fouling_threshold')
  - value       : 문자열로 저장, value_type으로 캐스팅
  - value_type  : 'INT'|'FLOAT'|'BOOL'|'STRING'|'JSON'
  - category    : 'FOULING'|'PREPROCESS'|'CLUSTER'|'MODEL'|'BENEFIT'|'SYSTEM'
  - label       : 화면 표시 이름 (한국어)
  - description : 설명/단위
  - default_value
  - min_value / max_value  (숫자형 검증)
  - unit_label  : 표시 단위
  - updated_by / updated_at

UnitSetting            # 호기별 오버라이드
  - unit (FK), key, value
  - unique(unit, key)
```

조회 우선순위: `UnitSetting` → `Setting` → 코드의 시드 기본값

### 4.2 필수 설정 항목 (시드)

**오염도 (`FOULING`)**
| 키 | 라벨 | 기본값 | 단위 |
|----|------|--------|------|
| `fouling_threshold` | 오염도 임계치 | 60 | – |
| `grade_caution_min` | 주의 등급 하한 | 30 | – |
| `grade_warning_min` | 경고 등급 하한 | 60 | – |
| `weight_dp` | 차압 가중치 | 0.6 | – |
| `weight_stack_temp` | 스택온도 가중치 | 0.4 | – |
| `normalization_method` | 정규화 방식 | SIGMA | – |
| `sigma_ref` | σ 기준 배수 | 6.0 | σ |
| `dp_ref_pct` | 차압 기준 상승률 | 30 | % |
| `st_ref_c` | 스택온도 기준 상승폭 | 15 | ℃ |
| `smoothing_window_h` | 평활 윈도 | 24 | h |
| `current_window_days` | 현재 지수 산정 기간 | 7 | 일 |

**전처리 (`PREPROCESS`)**
| 키 | 기본값 | 단위 |
|----|--------|------|
| `min_analysis_load_pct` | 40 | % |
| `ramp_threshold_mw_per_min` | 1.0 | MW/min |
| `ramp_settle_min` | 30 | 분 |
| `startup_settle_min` | 120 | 분 |
| `shutdown_lead_min` | 60 | 분 |
| `db_settle_min` | 60 | 분 |
| `stability_window_min` | 30 | 분 |
| `load_std_max_mw` | 2.0 | MW |
| `exh_temp_std_max_c` | 5.0 | ℃ |
| `min_segment_min` | 60 | 분 |
| `mad_k` | 5.0 | – |
| `rolling_window_h` | 24 | h |
| `stuck_points` | 30 | 점 |
| `gap_fill_max_points` | 3 | 점 |
| `min_valid_points` | 500 | 점 |

**군집화 (`CLUSTER`)**
| 키 | 기본값 |
|----|--------|
| `cluster_method` | RULE |
| `load_band_edges` | [40, 60, 80, 95] |
| `season_definition` | MONTH |
| `kmeans_k` | 6 |
| `min_cluster_points` | 200 |

**모델 (`MODEL`)**
| 키 | 기본값 |
|----|--------|
| `model_algorithm` | GBR |
| `baseline_length_days` | 30 |
| `baseline_offset_days` | 1 |
| `min_baseline_points` | 1000 |
| `r2_good` / `r2_warn` | 0.85 / 0.70 |
| `mae_stack_good_c` / `mae_stack_warn_c` | 3.0 / 6.0 |

**편익 (`BENEFIT`)** — `09-benefit-model.md` 3.1 항목 전체

**시스템 (`SYSTEM`)**
| 키 | 기본값 |
|----|--------|
| `max_upload_mb` | 200 |
| `max_rows_per_file` | 5000000 |
| `report_retention_days` | 90 |
| `session_timeout_hours` | 8 |
| `trend_window_days` | 180 |
| `min_trend_points` | 30 |
| `max_forecast_days` | 730 |
| `login_max_failures` | 5 |
| `login_lockout_minutes` | 5 |
| `priority_weights` | `{"fi":0.30,"slope":0.20,"daily_loss":0.35,"urgency":0.15}` |
| `backtest_lookahead_days` | `[30, 60, 90]` |
| `backtest_hit_window_days` | 30 |
| `auto_recalc_rolling_months` | 12 |

> **추가 근거(2026-09-21, Phase 7):** `19-optional-features.md` 의 우선순위 가중치(§3.3), 백테스트 컷오프 지점과
> ±30일 적중 판정 폭(§2.2), 자동 재계산 기본 창(§1.2)은 모두 튜닝 가능한 값이므로 설정으로 옮겼다(AGENTS.md §1.2).
> `priority_weights` 는 네 항목이 한 덩어리로만 의미가 있어 JSON 한 건으로 두고, 합이 1인지 검증한다
> (`units/settings_validation.py` 의 `check_json_weights`).

> **추가 근거(2026-09-20, Phase 1):** `01-auth-and-users.md` §3.2의 로그인 잠금 규칙("실패 5회 연속 시 5분 차단")은
> 튜닝 가능한 임계값이므로 코드에 고정하지 않고 설정값으로 옮겼다(AGENTS.md §1.2).
> `session_timeout_hours` 변경은 서버 재기동 후 적용된다(Django `SESSION_COOKIE_AGE` 는 기동 시 읽힌다).

### 4.3 설정 화면 동작
- 카테고리별 탭, 항목별 라벨·설명·단위·기본값·현재값 표시
- 값 변경 시 즉시 검증(`min_value`/`max_value`, 가중치 합 = 1, 등급 경계 순서)
- [기본값으로 복원] 버튼(항목별/카테고리별)
- 호기별 오버라이드 탭: 호기 선택 → 덮어쓸 항목만 지정, 나머지는 전역값 상속 표시
- 변경 시 **“다음 분석부터 적용됩니다. 기존 분석 결과는 변경되지 않습니다.”** 안내 표시
- 변경 이력(누가, 언제, 무엇을, 무엇에서 무엇으로) 조회

## 5. 모델 관리 (FR-A-08)

### 5.1 청정 기준 기간 지정
```
CleanBaselinePeriod
  - unit (FK)
  - start_at / end_at
  - source : 'MANUAL' | 'AUTO_FROM_CLEANING'
  - cleaning_event (FK, nullable)
  - is_active
  - note
  - created_by / created_at
```
- 관리자는 기간을 직접 지정하거나 세정 이력에서 자동 생성할 수 있다.
- 지정 시 해당 기간의 유효 포인트 수와 평균 차압·스택온도를 미리 보여준다.
- 여러 기간을 활성화해 합쳐서 학습할 수 있다.

### 5.2 재학습
- [재학습 실행] → 대상(차압/스택온도/둘 다), 알고리즘, 청정 기준 기간 선택 → 실행
- 비동기 실행, 진행률 표시
- 완료 시 **신·구 모델 지표 비교 표**(MAE, RMSE, R², 학습 표본 수) 제시 → [활성화] / [폐기] 선택
- 활성 모델 전환 이력 기록

## 6. 분석 실행 이력 (FR-A-09)

```
AnalysisRun
  - unit (FK)
  - executed_by (FK User)
  - executed_at
  - period_start / period_end
  - status : 'RUNNING'|'SUCCESS'|'FAILED'|'CANCELED'
  - failed_stage / error_message
  - settings_snapshot : JSON       # 적용된 모든 설정값
  - benefit_params_snapshot : JSON
  - model_version_dp (FK) / model_version_st (FK)
  - cluster_definition (FK)
  - column_mapping_version (FK)
  - data_stats : JSON              # 총/유효/제외 포인트
  - result_fi / result_grade / result_dday / result_net_benefit
  - duration_sec
  - is_auto : bool                 # 자동 재계산 여부
```

### 조회 화면
- 필터: 호기, 실행자, 기간, 상태, 자동/수동
- 목록 컬럼: 실행 일시, 호기, 실행자, 데이터 기간, 결과 FI/등급, D-day, 순편익, 소요시간, 상태
- 상세: 설정값 스냅샷 전체, 모델 버전, 데이터 통계, 오류 상세, [리포트 다시 생성] [결과 보기]
- 엑셀 내보내기 지원
- 실패한 실행은 실패 단계와 사유를 명확히 표시한다.

## 7. 감사 로그
```
AuditLog
  - actor (FK User), action, target_type, target_id
  - before : JSON / after : JSON
  - ip, created_at
```
대상: 사용자 CRUD, 호기 CRUD, 컬럼 매핑 변경, 설정 변경, 세정 이력 CRUD, 키워드 CRUD, 모델 활성화, 배치 롤백.

## 8. 예외 처리
| 상황 | 처리 |
|------|------|
| 가중치 합 ≠ 1 | 400 `INVALID_WEIGHTS`, 자동 정규화 제안 |
| `grade_caution_min ≥ grade_warning_min` | 400 `INVALID_GRADE_BOUNDARY` |
| 설정값이 min/max 범위 밖 | 400 `SETTING_OUT_OF_RANGE` |
| 데이터가 있는 호기 물리 삭제 시도 | 409 `UNIT_HAS_DATA` |
| 마지막 관리자 비활성화 | 409 `LAST_ADMIN_PROTECTED` |

## 9. 수용 기준 (AC)
- [ ] AC-13-1: 임계치를 60→50으로 변경하면 이후 분석의 D-day가 달라지고, 기존 분석 결과는 그대로다.
- [ ] AC-13-2: 호기별 오버라이드 설정이 전역 설정보다 우선 적용된다.
- [ ] AC-13-3: 분석 실행 이력에 실행자·일시·데이터 기간·설정값 스냅샷·모델 버전이 모두 기록된다.
- [ ] AC-13-4: 코드 내에 임계치·가중치·편익 계수의 하드코딩된 사용처가 없다(시드 정의 제외).
- [ ] AC-13-5: 설정 변경이 감사 로그에 변경 전후 값과 함께 남는다.
