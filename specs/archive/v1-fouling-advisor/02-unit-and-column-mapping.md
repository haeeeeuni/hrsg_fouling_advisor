# 02. 호기(설비) 관리 및 컬럼 매핑

관련 요구사항: FR-A-03, FR-D-03

---

## 1. 목적
분석 단위인 호기를 등록·관리하고, 호기마다 다른 원본 CSV 컬럼명을 시스템 표준 항목으로 연결한다.

## 2. 호기(Unit) 모델

```
Unit
  - code          : 호기 코드 (unique, 예 'U1', 'CC1-HRSG1')
  - name          : 호기명 (예 '1호기 HRSG')
  - plant_name    : 발전소명 (선택)
  - gt_model      : GT 기종 (선택)
  - rated_power_mw: 정격 출력(MW) — 부하율 계산 기준
  - min_load_mw   : 최소 안정 부하(MW) — 기동/정지 판정 기준
  - sampling_interval_min : 데이터 주기(분, 기본 10)
  - dp_source     : 'DP'(가스측 차압 계측) | 'BACKPRESSURE'(GT 배압 대체)
  - flow_source   : 'EXHAUST_FLOW' | 'FUEL_FLOW' | 'IGV'
  - is_active     : 사용 여부
  - created_at / updated_at
```

- 호기 삭제는 **비활성화 우선**. 운전 데이터·분석 이력이 있으면 물리 삭제 불가(`409 UNIT_HAS_DATA`).
- 사용자는 활성 호기만 선택할 수 있다.

## 3. 표준 항목 정의

분석 코드는 아래 표준 항목명만 사용한다.

### 3.1 필수 표준 항목
| 표준 항목 | 타입 | 단위 | 설명 |
|-----------|------|------|------|
| `timestamp` | datetime | – | 측정 시각 (KST) |
| `gt_power_mw` | float | MW | GT 출력 |
| `ambient_temp_c` | float | ℃ | 대기온도 |
| `gt_exhaust_temp_c` | float | ℃ | GT 배기온도 |
| `exhaust_flow` | float | kg/s 등 | 배기유량. 없으면 `fuel_flow` 또는 `igv_position_pct`로 대체 |
| `hrsg_gas_dp_kpa` | float | kPa | HRSG 가스측 차압. 없으면 `gt_backpressure_kpa`로 대체 |
| `stack_temp_c` | float | ℃ | 스택 온도 |
| `duct_burner_on` | bool/int | – | 덕트버너 상태(1=가동) |

### 3.2 대체 항목 (필수 항목의 대체재)
| 표준 항목 | 단위 | 대체 대상 |
|-----------|------|-----------|
| `fuel_flow` | Nm³/h, t/h | `exhaust_flow` |
| `igv_position_pct` | % | `exhaust_flow` |
| `gt_backpressure_kpa` | kPa | `hrsg_gas_dp_kpa` |

### 3.3 선택 표준 항목
| 표준 항목 | 단위 | 설명 |
|-----------|------|------|
| `st_power_mw` | MW | ST 출력 |
| `steam_flow_tph` | t/h | 증기 유량 |
| `feedwater_temp_c` | ℃ | 급수 온도 |
| `ambient_pressure_kpa` | kPa | 대기압 |
| `humidity_pct` | % | 습도 |

### 3.4 필수 충족 규칙
업로드가 유효하려면 다음을 모두 만족해야 한다.
1. `timestamp`, `gt_power_mw`, `ambient_temp_c`, `gt_exhaust_temp_c`, `stack_temp_c`, `duct_burner_on` 이 모두 매핑되어 있을 것
2. `exhaust_flow` **또는** `fuel_flow` **또는** `igv_position_pct` 중 최소 1개
3. `hrsg_gas_dp_kpa` **또는** `gt_backpressure_kpa` 중 최소 1개

## 4. 컬럼 매핑 모델

```
ColumnMapping
  - unit            : FK(Unit)
  - standard_field  : 표준 항목 키 (예 'gt_power_mw')
  - source_column   : 원본 CSV 컬럼명 (예 'GT_1_LOAD')
  - unit_label      : 원본 단위 표기 (예 'MW', 'mmH2O')
  - scale_factor    : float, 기본 1.0 (단위 환산 계수)
  - offset          : float, 기본 0.0 (환산 오프셋)
  - is_required_ok  : 계산 필드 — 필수 충족 여부 판정에 사용
  - unique(unit, standard_field)
```

변환식: `표준값 = 원본값 × scale_factor + offset`

예) 차압이 `mmH2O`로 기록된 경우 `scale_factor = 0.00980665` (→ kPa)
예) 온도가 `°F`인 경우 `scale_factor = 5/9`, `offset = -32×5/9`

### 덕트버너 상태 매핑
`duct_burner_on`은 다음 중 하나의 해석 규칙을 지정한다.
| 규칙 | 설명 |
|------|------|
| `BOOL` | `1/0`, `True/False`, `ON/OFF`, `Y/N` 문자열을 bool로 해석 |
| `THRESHOLD` | 덕트버너 연료유량 값이 임계값(설정) 초과 시 ON |

## 5. 관리자 UI 동작

1. 관리자는 호기 상세 화면에서 **샘플 CSV 헤더 업로드**를 통해 원본 컬럼 목록을 불러올 수 있다.
2. 표준 항목별로 드롭다운에서 원본 컬럼을 선택하고, 단위/계수를 입력한다.
3. 화면 상단에 **필수 충족 규칙(4항) 통과 여부**를 실시간 배지로 표시한다.
4. 저장 전 “미리보기” 기능: 샘플 파일의 상위 20행에 매핑을 적용한 결과 테이블을 보여준다.
5. 매핑을 변경하면 `ColumnMappingVersion`으로 이력을 남긴다(변경자, 일시, 변경 전후). 과거 분석 결과의 재현성을 위해 분석 실행 시 사용한 매핑 버전을 기록한다.

## 6. 예외 처리
| 상황 | 처리 |
|------|------|
| 필수 항목 미매핑 상태로 저장 | 저장은 허용하되 `is_mapping_complete=False`로 표시하고, 해당 호기로의 업로드는 차단 |
| 원본 컬럼이 실제 파일에 없음 | 업로드 시 `MISSING_SOURCE_COLUMN` 오류로 어떤 표준 항목이 어떤 컬럼을 기대했는지 명시 |
| 동일 원본 컬럼을 두 표준 항목에 매핑 | 경고만 표시(허용) |

## 7. 수용 기준 (AC)
- [ ] AC-02-1: 컬럼 매핑이 완료되지 않은 호기는 사용자 업로드 화면의 호기 목록에 “매핑 미완료”로 표시되고 업로드가 차단된다.
- [ ] AC-02-2: 차압 컬럼이 없고 GT 배압만 매핑된 호기도 필수 규칙을 통과한다.
- [ ] AC-02-3: `scale_factor`를 적용한 값이 미리보기와 실제 적재값에서 동일하다.
- [ ] AC-02-4: 매핑 변경 이력이 조회되고, 과거 분석 결과는 당시 매핑 버전을 참조한다.
