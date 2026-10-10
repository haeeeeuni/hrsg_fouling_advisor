# 14. 데이터 모델 (ERD)

관련 요구사항: FR-D-04, FR-D-05, FR-D-06, TR-03, TR-06

---

## 1. 설계 원칙
1. `User`는 Django `AbstractUser`를 상속해 확장한다(TR-06).
2. 원본 데이터(`Measurement`)는 불변(immutable)으로 취급한다. 정제·플래그는 파생 테이블에 둔다.
3. 모든 분석 결과는 **실행 컨텍스트 스냅샷**(설정값, 모델 버전, 매핑 버전)을 함께 보관해 재현 가능해야 한다.
4. 기준값은 `Setting` / `UnitSetting`에 두고 코드에 고정하지 않는다.
5. 시각은 DB에 UTC(timezone-aware)로 저장하고, 표시·집계는 KST로 변환한다.

## 2. 앱별 모델 배치

| 앱 | 모델 |
|----|------|
| `accounts` | `User`, `LoginHistory` |
| `units` | `Unit`, `ColumnMapping`, `ColumnMappingVersion`, `Setting`, `UnitSetting` |
| `ingestion` | `UploadBatch`, `Measurement` |
| `analysis` | `ClusterDefinition`, `ModelVersion`, `CleanBaselinePeriod`, `AnalysisRun`, `CleanedPoint`, `FoulingIndexPoint`, `TrendForecast`, `BenefitResult`, `ComparisonReport`, `BacktestResult` |
| `maintenance` | `MaintenanceRecord`, `CleaningEvent`, `FoulingKeyword` |
| `reports` | `ReportExport` |
| `common` | `AuditLog` |

## 3. ERD (관계 요약)

```
User ──< AnalysisRun >── Unit
 │                          │
 │                          ├──< ColumnMapping
 │                          ├──< UnitSetting
 │                          ├──< UploadBatch ──< Measurement
 │                          ├──< CleaningEvent
 │                          ├──< MaintenanceRecord
 │                          ├──< CleanBaselinePeriod
 │                          ├──< ModelVersion
 │                          └──< ClusterDefinition
 │
 └──< LoginHistory
      AuditLog

AnalysisRun ──< CleanedPoint
            ──< FoulingIndexPoint
            ──1 TrendForecast
            ──1 BenefitResult
            ──< ReportExport
            ──< ComparisonReport
```

## 4. 모델 정의

### 4.1 accounts

```python
class User(AbstractUser):
    # username 제거, employee_no 를 USERNAME_FIELD 로 사용
    employee_no = CharField(max_length=20, unique=True)      # 사번
    full_name   = CharField(max_length=50)                    # 성명
    role        = CharField(max_length=10, choices=ROLE, default='USER')  # USER|ADMIN
    department  = CharField(max_length=50, blank=True)
    phone       = CharField(max_length=20, blank=True)
    must_change_password = BooleanField(default=False)
    last_login_at = DateTimeField(null=True, blank=True)
    created_at / updated_at

    USERNAME_FIELD = 'employee_no'
    REQUIRED_FIELDS = ['full_name']

class LoginHistory:
    user (FK, null 허용), attempted_employee_no, full_name_input
    success (bool), fail_reason, ip, user_agent, created_at
```

### 4.2 units

```python
class Unit:
    code (unique), name, plant_name, gt_model
    rated_power_mw, rated_st_power_mw (null), min_load_mw
    sampling_interval_min (default 10)
    dp_source ('DP'|'BACKPRESSURE'), flow_source ('EXHAUST_FLOW'|'FUEL_FLOW'|'IGV')
    is_active, created_at, updated_at

class ColumnMapping:
    unit (FK), standard_field, source_column, unit_label
    scale_factor (default 1.0), offset (default 0.0)
    bool_rule (null)             # duct_burner_on 해석 규칙
    unique_together = (unit, standard_field)

class ColumnMappingVersion:
    unit (FK), version (int), snapshot (JSON), created_by, created_at

class Setting:
    key (unique), value, value_type, category, label, description
    default_value, min_value, max_value, unit_label, updated_by, updated_at

class UnitSetting:
    unit (FK), key, value
    unique_together = (unit, key)
```

### 4.3 ingestion

```python
class UploadBatch:
    unit (FK), kind ('OPERATION'|'MAINTENANCE')
    uploaded_by (FK User), uploaded_at
    original_filename, file_size_bytes, checksum (sha256)
    status ('PENDING'|'VALIDATED'|'LOADED'|'FAILED'|'CANCELED')
    row_total, row_loaded, row_skipped, row_duplicated
    period_start, period_end
    validation_report (JSON)
    column_mapping_version (FK, null)

class Measurement:
    unit (FK, db_index), timestamp (db_index)
    gt_power_mw, ambient_temp_c, gt_exhaust_temp_c
    exhaust_flow, fuel_flow, igv_position_pct
    hrsg_gas_dp_kpa, gt_backpressure_kpa, stack_temp_c
    duct_burner_on (bool)
    st_power_mw, steam_flow_tph, feedwater_temp_c
    ambient_pressure_kpa, humidity_pct
    upload_batch (FK)
    unique_together = (unit, timestamp)
    indexes = [(unit, timestamp)]
```

> **성능 주의:** `Measurement`는 가장 큰 테이블이다. `(unit, timestamp)` 복합 인덱스를 필수로 두고,
> 데이터가 수천만 행 규모로 커질 경우 PostgreSQL 선언적 파티셔닝(월 단위, `timestamp` 기준) 도입을 검토한다.

### 4.4 analysis

```python
class ClusterDefinition:
    unit (FK), method ('RULE'|'KMEANS'), version, params (JSON)
    is_active, created_by, created_at

class CleanBaselinePeriod:
    unit (FK), start_at, end_at, source, cleaning_event (FK null)
    is_active, note, created_by, created_at

class ModelVersion:
    unit (FK), target ('DP'|'STACK_TEMP'), algorithm, version
    baseline_start, baseline_end, feature_list (JSON), hyperparams (JSON)
    metrics (JSON), residual_mean, residual_std, training_rows
    artifact_path, trained_by (FK), trained_at, is_active, notes
    unique_together = (unit, target, version)

class AnalysisRun:
    unit (FK), executed_by (FK), executed_at
    period_start, period_end
    status, failed_stage, error_message, duration_sec, is_auto
    settings_snapshot (JSON), benefit_params_snapshot (JSON)
    model_version_dp (FK null), model_version_st (FK null)
    cluster_definition (FK null), column_mapping_version (FK null)
    data_stats (JSON)
    result_fi, result_grade, result_dday, result_net_benefit   # 목록 조회용 비정규화

class CleanedPoint:            # 대용량 — 보존 정책 적용
    analysis_run (FK, db_index), timestamp
    (표준 항목 정제값들)
    segment_state, segment_id, cluster_key, is_valid, exclusion_reason
    expected_dp, expected_stack_temp, residual_dp, residual_stack_temp

class FoulingIndexPoint:
    analysis_run (FK, db_index), date, cluster_key (null=전체)
    fi_value, score_dp, score_st
    residual_dp, residual_st, expected_dp, expected_st, measured_dp, measured_st
    sample_count, confidence, grade

class TrendForecast:
    analysis_run (OneToOne), model_type, fit_start, fit_end
    coefficients (JSON), slope_per_day, r2, mae, p_value
    threshold_used, current_fi
    eta_date, eta_days, eta_lower_date, eta_upper_date
    caution_eta_date, warning_eta_date, status

class BenefitResult:
    analysis_run (OneToOne), params_snapshot (JSON)
    delta_dp_kpa, delta_stack_c
    power_loss_gt_mw, power_loss_st_mw, power_loss_total_mw
    daily_loss_cost, daily_fuel_loss
    cleaning_cost, outage_loss, total_cleaning_cost
    gross_benefit, net_benefit, payback_days, roi_pct
    recommended_cleaning_date, scenarios (JSON), sensitivity (JSON null)

class ComparisonReport:
    unit (FK), cleaning_event (FK), created_by, created_at
    window_days, before_start, before_end, after_start, after_end
    model_version_dp (FK), model_version_st (FK)
    metrics (JSON), cluster_metrics (JSON), p_values (JSON)

class BacktestResult:          # 옵션
    unit (FK), created_by, created_at
    cleaning_event (FK), cutoff_date
    predicted_eta_date, actual_event_date, error_days
    predicted_benefit, actual_benefit (null)
    detail (JSON)
```

### 4.5 maintenance

```python
class MaintenanceRecord:
    unit (FK), upload_batch (FK null)
    work_date, work_type, title, description, cost, duration_days, worker
    is_fouling_related (bool), matched_keywords (JSON), match_score
    review_status ('PENDING'|'ACCEPTED'|'IGNORED')

class CleaningEvent:
    unit (FK), cleaned_at, cleaned_end_at (null)
    method, method_detail, cost, outage_days
    source ('MANUAL'|'EXTRACTED'), maintenance_record (FK null)
    note, created_by, created_at, updated_at

class FoulingKeyword:
    keyword, category ('CLEANING'|'FOULING'|'INSPECTION'|'EXCLUDE')
    weight (default 1.0), is_active, created_by, created_at
    unique_together = (keyword, category)
```

### 4.6 reports / common

```python
class ReportExport:
    analysis_run (FK null), comparison_report (FK null)
    format ('PDF'|'XLSX'), file_path, file_size_bytes
    created_by, created_at, expires_at

class AuditLog:
    actor (FK User null), action, target_type, target_id
    before (JSON null), after (JSON null), ip, created_at
```

## 5. 데이터 보존 정책
| 테이블 | 정책 |
|--------|------|
| `Measurement` | 무기한 누적(운영 데이터 자산) |
| `CleanedPoint` | 최근 N회(기본 10회) 분석분만 보관, 이후 삭제. `FoulingIndexPoint`는 유지 |
| `FoulingIndexPoint` | 무기한 (요약 수준이라 용량 작음) |
| `ReportExport` | `report_retention_days`(기본 90일) 후 파일 삭제, 레코드는 유지 |
| `LoginHistory` / `AuditLog` | 3년 |

## 6. 인덱스 요약
| 테이블 | 인덱스 |
|--------|--------|
| `Measurement` | `(unit, timestamp)` unique, `timestamp` |
| `CleanedPoint` | `(analysis_run, timestamp)` |
| `FoulingIndexPoint` | `(analysis_run, date)`, `(analysis_run, cluster_key)` |
| `AnalysisRun` | `(unit, executed_at DESC)`, `status` |
| `CleaningEvent` | `(unit, cleaned_at)` |
| `MaintenanceRecord` | `(unit, work_date)`, `is_fouling_related` |

## 7. 마이그레이션 주의
- 커스텀 User 모델은 **첫 마이그레이션 이전에** 정의해야 한다(`AUTH_USER_MODEL = 'accounts.User'`).
- 이미 마이그레이션이 적용된 후 User 모델을 교체하는 것은 매우 번거로우므로, 프로젝트 초기에 확정한다.

## 8. 수용 기준 (AC)
- [ ] AC-14-1: `AUTH_USER_MODEL`이 커스텀 User를 가리키고 사번으로 로그인된다.
- [ ] AC-14-2: 동일 호기·시각의 Measurement가 중복 저장되지 않는다.
- [ ] AC-14-3: `AnalysisRun`만 보고도 그 결과를 동일하게 재현할 수 있는 정보가 모두 저장된다.
- [ ] AC-14-4: 설정값이 DB에서 조회되며, 호기별 오버라이드가 동작한다.
