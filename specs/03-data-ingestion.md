# 03. 운전 데이터 업로드 및 적재

관련 요구사항: FR-U-02, FR-U-03, FR-D-01, FR-D-02, FR-D-04

---

## 1. 목적
사용자가 호기를 선택해 운전 데이터 CSV를 업로드하고, 시스템이 형식을 검증한 뒤 호기별로 누적 저장한다.

## 2. 업로드 절차

```
[1] 호기 선택
 └─ 활성 + 매핑 완료 호기만 선택 가능
[2] 파일 선택 (CSV, 다중 파일 허용)
[3] 사전 검증 (서버)
 ├─ 파일 형식 / 인코딩 / 크기
 ├─ 헤더 검사 (매핑된 원본 컬럼 존재 여부)
 ├─ 타입/형식 검사 (타임스탬프 파싱, 숫자 변환)
 └─ 요약 리포트 반환 (행수, 기간, 오류 목록)
[4] 사용자 확인 → 적재 실행
[5] 적재 결과 표시 (신규 N행, 중복 M행, 오류 K행)
```

- [3]과 [5]는 분리한다. **검증 통과 전에는 DB에 저장하지 않는다.**
- 검증 결과는 임시 저장(`UploadBatch` status=`VALIDATED`)되고, 사용자가 취소하면 폐기한다.

## 3. 파일 요건

| 항목 | 규칙 |
|------|------|
| 형식 | `.csv` (구분자 `,` 기본, `;`·탭 자동 감지) |
| 인코딩 | UTF-8, UTF-8-BOM, CP949(EUC-KR) 자동 감지 |
| 최대 크기 | 기본 200 MB (설정값 `MAX_UPLOAD_MB`) |
| 최대 행수 | 기본 5,000,000행 (설정값) |
| 헤더 | 첫 행이 헤더. 앞뒤 공백 자동 제거 |

## 4. 검증 규칙

### 4.1 구조 검증
| 코드 | 조건 | 심각도 |
|------|------|--------|
| `EMPTY_FILE` | 데이터 행 0개 | 오류 |
| `MISSING_SOURCE_COLUMN` | 매핑된 원본 컬럼이 헤더에 없음 | 오류 |
| `REQUIRED_FIELD_UNMAPPED` | 필수 표준 항목 매핑 누락(대체 규칙 포함) | 오류 |
| `DUPLICATE_HEADER` | 동일 컬럼명 중복 | 오류 |

### 4.2 값 검증 (행 단위)
| 코드 | 조건 | 심각도 | 처리 |
|------|------|--------|------|
| `TIMESTAMP_PARSE_ERROR` | 타임스탬프 파싱 실패 | 오류 | 해당 행 제외 |
| `TIMESTAMP_DUPLICATE` | 동일 호기 + 동일 시각 중복 | 경고 | 마지막 값 우선(설정으로 첫 값 우선 변경 가능) |
| `TIMESTAMP_OUT_OF_ORDER` | 시간 역순 | 경고 | 정렬 후 적재 |
| `NUMERIC_PARSE_ERROR` | 숫자 컬럼 변환 실패(문자, `Bad`, `I/O Timeout` 등) | 경고 | 해당 셀 NaN 처리 |
| `OUT_OF_RANGE` | 물리적 범위 초과(아래 표) | 경고 | 해당 셀 NaN 처리 + 이상치 카운트 |
| `FUTURE_TIMESTAMP` | 현재 시각 + 1일 초과 | 오류 | 해당 행 제외 |

### 4.3 물리적 허용 범위 (설정값, 기본)
| 항목 | 최소 | 최대 |
|------|------|------|
| `gt_power_mw` | -5 | 정격 × 1.2 |
| `ambient_temp_c` | -40 | 60 |
| `gt_exhaust_temp_c` | 0 | 800 |
| `stack_temp_c` | 0 | 400 |
| `hrsg_gas_dp_kpa` | 0 | 20 |
| `gt_backpressure_kpa` | 0 | 20 |
| `humidity_pct` | 0 | 100 |

### 4.4 검증 결과 리포트 (사용자 화면)
- 총 행수 / 유효 행수 / 제외 행수
- 데이터 기간(시작~종료), 실제 샘플링 주기 추정값
- 오류·경고 목록: 코드, 설명, 발생 건수, 예시 행번호 최대 10개
- 컬럼별 결측률 표
- **오류가 1건이라도 있으면 적재 버튼 비활성화.** 경고만 있으면 적재 가능.

## 5. 적재 규칙

```
UploadBatch
  - unit, uploaded_by, uploaded_at
  - original_filename, file_size_bytes, checksum(sha256)
  - status : PENDING | VALIDATED | FAILED | LOADED | CANCELED
  - row_total / row_loaded / row_skipped / row_duplicated
  - period_start / period_end
  - validation_report : JSON
  - column_mapping_version : FK
```

```
Measurement   (호기별 누적 시계열)
  - unit (FK, index)
  - timestamp (index)
  - gt_power_mw, ambient_temp_c, gt_exhaust_temp_c
  - exhaust_flow, fuel_flow, igv_position_pct
  - hrsg_gas_dp_kpa, gt_backpressure_kpa, stack_temp_c
  - duct_burner_on
  - st_power_mw, steam_flow_tph, feedwater_temp_c, ambient_pressure_kpa, humidity_pct
  - upload_batch (FK)
  - unique(unit, timestamp)
```

- 중복 타임스탬프는 `unique(unit, timestamp)` 제약으로 막고, 정책에 따라 **업데이트 또는 건너뛰기**를 선택한다(기본: 건너뛰기, 배치 옵션으로 덮어쓰기 가능).
- 대량 적재는 `bulk_create(batch_size=5000, ignore_conflicts=True)` 사용.
- 동일 파일(checksum 동일)을 같은 호기에 재업로드하면 경고를 띄우고 사용자가 확인해야 진행된다.
- 적재는 트랜잭션으로 처리하고, 실패 시 `UploadBatch.status='FAILED'`와 사유를 남긴다.

## 6. 업로드 이력
- 사용자/관리자 모두 호기별 업로드 이력을 조회할 수 있다: 파일명, 업로더, 일시, 기간, 행수, 상태.
- 관리자는 배치 단위 **롤백(적재된 Measurement 삭제)** 이 가능하다. 해당 배치를 사용한 분석 결과가 있으면 경고 후 진행.

## 7. 성능 요구
- 100만 행(약 100 MB) 파일 검증 + 적재가 **5분 이내** 완료되어야 한다.
- 검증/적재는 비동기 작업으로 실행하고 진행률(%)을 폴링으로 제공한다.
- pandas `read_csv(chunksize=...)` 로 청크 처리하여 메모리 사용량을 2 GB 이하로 유지한다.

## 8. 예외 처리
| 상황 | 응답 |
|------|------|
| 매핑 미완료 호기 | 400 `UNIT_MAPPING_INCOMPLETE` |
| 크기 초과 | 413 `FILE_TOO_LARGE` |
| 인코딩 판별 실패 | 400 `ENCODING_NOT_SUPPORTED` |
| 검증 오류 존재 상태로 적재 요청 | 409 `VALIDATION_NOT_PASSED` |

## 9. 수용 기준 (AC)
- [ ] AC-03-1: 필수 컬럼이 빠진 CSV 업로드 시 어떤 표준 항목이 어떤 원본 컬럼을 찾지 못했는지 구체적으로 표시된다.
- [ ] AC-03-2: 타임스탬프 형식이 섞인 파일에서 파싱 실패 행이 제외되고 건수가 리포트에 표시된다.
- [ ] AC-03-3: 같은 파일을 두 번 적재해도 Measurement 행이 중복 증가하지 않는다.
- [ ] AC-03-4: CP949 인코딩 한글 헤더 파일이 정상 처리된다.
- [ ] AC-03-5: 적재 후 호기별 누적 데이터 기간이 갱신되어 대시보드에 반영된다.
