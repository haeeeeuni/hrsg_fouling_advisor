# 15. REST API 명세

관련 요구사항: TR-02

---

## 1. 공통 규약

| 항목 | 규약 |
|------|------|
| 베이스 경로 | `/api/` |
| 형식 | JSON (요청·응답 모두 `application/json`, 파일 업로드는 `multipart/form-data`) |
| 인증 | 세션 쿠키(HttpOnly) + CSRF 토큰 |
| 권한 | 기본 `IsAuthenticated`, 관리자 전용은 `IsAdminRole` 명시 |
| 필드 표기 | `snake_case` |
| 시각 표기 | ISO 8601 (`2025-09-20T14:30:00+09:00`) |
| 페이지네이션 | `?page=&page_size=` → `{count, next, previous, results}` |
| 정렬 | `?ordering=-executed_at` |
| 검색 | `?search=` |

### 오류 응답 포맷 (고정)
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "필수 컬럼이 누락되었습니다.",
    "details": { "missing_fields": ["stack_temp_c"] }
  }
}
```

| HTTP | 의미 |
|------|------|
| 400 | 검증 실패 |
| 401 | 미인증 |
| 403 | 권한 부족 |
| 404 | 리소스 없음 |
| 409 | 상태 충돌(중복, 참조 존재) |
| 413 | 파일 크기 초과 |
| 422 | 분석 전제 불충족(데이터 부족 등) |
| 429 | 요청 제한 |
| 500 | 서버 오류 |

### 비동기 작업 규약
오래 걸리는 작업(검증, 적재, 분석, 재학습, 리포트)은 다음 패턴을 따른다.
```
POST  /api/<resource>/            → 202 { "job_id": "...", "status": "RUNNING" }
GET   /api/jobs/{job_id}/         → { "status": "RUNNING|SUCCESS|FAILED",
                                      "progress": 45, "stage": "기대값 예측",
                                      "result": {...}, "error": {...} }
POST  /api/jobs/{job_id}/cancel/  → 202
```

---

## 2. 인증 (`/api/auth/`)

| 메서드 | 경로 | 권한 | 설명 |
|--------|------|------|------|
| POST | `/auth/login/` | 공개 | 로그인. body: `full_name`, `employee_no`, `password` |
| POST | `/auth/logout/` | 인증 | 로그아웃 |
| GET | `/auth/me/` | 인증 | 현재 사용자 정보(`employee_no`, `full_name`, `role`, `must_change_password`) |
| POST | `/auth/change-password/` | 인증 | body: `current_password`, `new_password` |
| GET | `/auth/csrf/` | 공개 | CSRF 토큰 발급 |

---

## 3. 사용자 관리 (`/api/users/`) — 관리자

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/users/` | 목록 (검색: 성명/사번, 필터: `role`, `is_active`) |
| POST | `/users/` | 생성 |
| GET | `/users/{id}/` | 상세 |
| PATCH | `/users/{id}/` | 수정 |
| DELETE | `/users/{id}/` | 비활성화(기본) / `?hard=true` 물리 삭제 |
| POST | `/users/{id}/reset-password/` | 비밀번호 초기화 |
| GET | `/login-histories/` | 로그인 이력 |

---

## 4. 호기 및 매핑 (`/api/units/`)

| 메서드 | 경로 | 권한 | 설명 |
|--------|------|------|------|
| GET | `/units/` | 인증 | 호기 목록 (`?is_active=true`). 매핑 완료 여부 `is_mapping_complete` 포함 |
| POST | `/units/` | 관리자 | 호기 생성 |
| GET/PATCH/DELETE | `/units/{id}/` | 관리자(수정/삭제) | |
| GET | `/units/{id}/column-mappings/` | 관리자 | 매핑 목록 |
| PUT | `/units/{id}/column-mappings/` | 관리자 | 매핑 일괄 저장 |
| POST | `/units/{id}/column-mappings/preview/` | 관리자 | 샘플 파일 + 매핑 → 상위 20행 변환 미리보기 |
| GET | `/units/{id}/column-mappings/versions/` | 관리자 | 매핑 변경 이력 |
| GET | `/standard-fields/` | 인증 | 표준 항목 정의 목록(필수/선택/대체 규칙 포함) |
| GET | `/units/{id}/data-summary/` | 인증 | 누적 데이터 기간, 행수, 최근 분석 요약 |

---

## 5. 데이터 업로드 (`/api/uploads/`)

| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | `/uploads/operation/validate/` | 운전 데이터 검증. `multipart`: `unit_id`, `file`. → 202 job |
| POST | `/uploads/{batch_id}/commit/` | 검증 통과 배치 적재. body: `duplicate_policy` (`SKIP`\|`OVERWRITE`) → 202 job |
| POST | `/uploads/{batch_id}/cancel/` | 검증 결과 폐기 |
| GET | `/uploads/` | 업로드 이력 (`?unit_id=&kind=&status=`) |
| GET | `/uploads/{batch_id}/` | 상세(검증 리포트 포함) |
| DELETE | `/uploads/{batch_id}/` | 관리자. 배치 롤백(적재 데이터 삭제) |
| POST | `/uploads/maintenance/` | 정비 이력 파일 업로드(CSV/XLSX). → 202 job |

### 검증 결과 예시
```json
{
  "batch_id": 12,
  "status": "VALIDATED",
  "row_total": 52560,
  "row_valid": 51902,
  "period": {"start": "2024-01-01T00:00:00+09:00", "end": "2024-12-31T23:50:00+09:00"},
  "estimated_interval_min": 10,
  "errors": [],
  "warnings": [
    {"code": "NUMERIC_PARSE_ERROR", "count": 412, "message": "숫자 변환 실패", "sample_rows": [130, 2288]}
  ],
  "missing_rate": {"hrsg_gas_dp_kpa": 0.8, "stack_temp_c": 0.2}
}
```

---

## 6. 분석 (`/api/analysis-runs/`)

| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | `/analysis-runs/` | 분석 실행. body 아래 참조 → 202 job |
| GET | `/analysis-runs/` | 실행 이력 (`?unit_id=&status=&executed_by=&from=&to=`) |
| GET | `/analysis-runs/{id}/` | 실행 메타 + 요약 결과 |
| GET | `/analysis-runs/{id}/fouling-index/` | FI 시계열 (`?cluster_key=&from=&to=`) |
| GET | `/analysis-runs/{id}/clusters/` | 군집별 요약 |
| GET | `/analysis-runs/{id}/residuals/` | 차압·스택온도 실측/기대/잔차 시계열 |
| GET | `/analysis-runs/{id}/model-metrics/` | 모델 정확도(MAE, RMSE, R², 산점도용 데이터) |
| GET | `/analysis-runs/{id}/trend/` | 추세·D-day |
| GET | `/analysis-runs/{id}/benefit/` | 편익 결과 |
| GET | `/analysis-runs/{id}/data-quality/` | 정제 요약 |
| POST | `/analysis-runs/{id}/recalculate-benefit/` | 편익 파라미터만 변경해 재계산(분석 재실행 없이) |
| DELETE | `/analysis-runs/{id}/` | 관리자 |

### 분석 실행 요청 body
```json
{
  "unit_id": 1,
  "period_start": "2024-01-01",
  "period_end": "2024-12-31",
  "benefit_params_override": {
    "electricity_price": 135,
    "cleaning_cost": 28000000,
    "outage_days": 1.5
  },
  "settings_override": { "fouling_threshold": 55 },
  "force_retrain": false
}
```

### 분석 요약 응답 예시
```json
{
  "id": 87,
  "unit": {"id": 1, "code": "U1", "name": "1호기 HRSG"},
  "executed_by": {"employee_no": "A1234", "full_name": "홍길동"},
  "executed_at": "2025-09-20T14:02:11+09:00",
  "period": {"start": "2024-01-01", "end": "2024-12-31"},
  "status": "SUCCESS",
  "current_fi": 62.4,
  "grade": "WARNING",
  "confidence": "HIGH",
  "fi_change_7d": 3.2,
  "trend": {"status": "ALREADY_EXCEEDED", "eta_days": 0, "slope_per_day": 0.18},
  "benefit": {"net_benefit": 768200000, "payback_days": 48, "daily_loss_cost": 5712000},
  "model": {"dp": {"version": 3, "r2": 0.91, "mae": 0.12},
            "stack_temp": {"version": 3, "r2": 0.88, "mae": 2.4}},
  "data_stats": {"total": 52560, "valid": 31204, "valid_ratio": 0.594}
}
```

---

## 7. 정비·세정 이력 (`/api/maintenance/`, `/api/cleaning-events/`)

| 메서드 | 경로 | 권한 | 설명 |
|--------|------|------|------|
| GET | `/maintenance-records/` | 인증 | 정비 이력 (`?unit_id=&is_fouling_related=&review_status=`) |
| POST | `/maintenance-records/{id}/accept/` | 인증 | 세정 이벤트로 등록 |
| POST | `/maintenance-records/{id}/ignore/` | 인증 | 무시 처리 |
| POST | `/maintenance-records/re-extract/` | 관리자 | 키워드 사전 변경 후 재추출 |
| GET/POST | `/cleaning-events/` | 조회 인증 / 생성 관리자 | 세정 이력 |
| GET/PATCH/DELETE | `/cleaning-events/{id}/` | 관리자 | |
| GET/POST | `/fouling-keywords/` | 관리자 | 키워드 사전 |
| PATCH/DELETE | `/fouling-keywords/{id}/` | 관리자 | |
| POST | `/fouling-keywords/restore-defaults/` | 관리자 | 기본 시드 복원 |

---

## 8. 비교 리포트 (`/api/comparisons/`)

| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | `/comparisons/` | 세정 전후 비교 생성. body: `cleaning_event_id`, `window_days`, `before_offset_days`, `after_offset_days` |
| GET | `/comparisons/` | 목록 (`?unit_id=`) |
| GET | `/comparisons/{id}/` | 상세(군집별 비교, p-value 포함) |

---

## 9. 리포트 출력 (`/api/reports/`)

| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | `/analysis-runs/{id}/export/` | body: `format` (`pdf`\|`xlsx`), `charts` (base64 PNG 배열, 선택) → 202 job |
| POST | `/comparisons/{id}/export/` | 비교 리포트 출력 |
| GET | `/reports/` | 생성 이력 |
| GET | `/reports/{id}/download/` | 파일 다운로드 (`Content-Disposition` RFC 5987 한글 파일명) |

---

## 10. 설정 (`/api/settings/`) — 관리자

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/settings/` | 전역 설정 목록 (`?category=`) |
| PATCH | `/settings/` | 일괄 수정. body: `{"fouling_threshold": 55, "weight_dp": 0.7}` |
| POST | `/settings/restore-defaults/` | body: `category` 또는 `keys` |
| GET | `/units/{id}/settings/` | 호기별 오버라이드 조회(상속값 표시 포함) |
| PUT | `/units/{id}/settings/` | 호기별 오버라이드 저장 |
| DELETE | `/units/{id}/settings/{key}/` | 오버라이드 해제(전역값 상속) |
| GET | `/settings/effective/?unit_id=1` | 인증. 해당 호기에 실제 적용되는 최종 설정값 |

---

## 11. 모델 관리 (`/api/models/`) — 관리자

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/model-versions/` | `?unit_id=&target=` |
| GET | `/model-versions/{id}/` | 상세(지표, 피처, 하이퍼파라미터) |
| POST | `/model-versions/train/` | 재학습. body: `unit_id`, `targets`, `algorithm`, `baseline_period_ids` → 202 job |
| POST | `/model-versions/{id}/activate/` | 활성화 |
| GET/POST | `/clean-baseline-periods/` | 청정 기준 기간 |
| PATCH/DELETE | `/clean-baseline-periods/{id}/` | |
| GET/POST | `/cluster-definitions/` | 군집 정의 |

---

## 12. 옵션 기능 (`/api/`)

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/units/{id}/auto-recalc/` | 자동 재계산 설정 조회 (일반 사용자 읽기 가능) |
| PUT | `/units/{id}/auto-recalc/` | 자동 재계산 설정 변경 (관리자) |
| POST | `/backtests/` | 백테스트 실행 → 202 job (관리자) |
| GET | `/backtests/` | 결과 목록 (`?unit_id=`) |
| GET | `/backtests/{id}/` | 결과 상세 |
| GET | `/backtests/availability/` | 호기별 실행 가능 여부 — 세정 2회 미만이면 `available=false` (AC-19-6) |
| GET | `/units/comparison/` | 호기 간 오염도 비교 및 세정 우선순위 (`?unit_ids=1,2,3`) |
| GET | `/notifications/` | 알림 목록 (`?unread=true`, `?unit_id=`). 응답에 `unread_count` 포함 |
| POST | `/notifications/{id}/read/` | 개별 읽음 처리 |
| POST | `/notifications/read-all/` | 전체 읽음 처리 |

**정정(구현 시점):** 원안은 자동 재계산 설정을 `POST` 하나로 뒀으나, 설정은 호기당 1건인 멱등 리소스이므로
조회 `GET` + 갱신 `PUT` 으로 나눈다. 백테스트 메뉴 비활성화 판단(AC-19-6)과 알림 읽음 처리(specs/19 §1.4)에
필요한 엔드포인트가 원안에 빠져 있어 함께 추가했다.

**라우팅 주의:** `/units/comparison/` 은 `units` 라우터의 상세 경로 `/units/{pk}/` 와 형태가 겹친다.
`config/urls.py` 에서 `analysis.urls` 를 `units.urls` 보다 먼저 include 해 고정 경로가 먼저 잡히게 한다.

---

## 13. Rate limit / 보안
- 로그인: IP 기준 분당 10회, 사번 기준 5회 실패 시 5분 잠금.
- 업로드: 사용자당 동시 1건.
- 분석 실행: 호기당 동시 1건(중복 요청 시 409 `ANALYSIS_ALREADY_RUNNING`).
- 모든 상태 변경 요청은 CSRF 토큰 필요.

## 14. 수용 기준 (AC)
- [ ] AC-15-1: 비인증 요청이 모든 `/api/` 엔드포인트(로그인·CSRF 제외)에서 401을 받는다.
- [ ] AC-15-2: 일반 사용자가 `/api/settings/`에 PATCH 하면 403을 받는다.
- [ ] AC-15-3: 오류 응답이 모두 공통 포맷을 따른다.
- [ ] AC-15-4: 분석 실행이 202 + job_id를 반환하고 폴링으로 진행률을 확인할 수 있다.
- [ ] AC-15-5: 같은 호기에 동시 분석 요청 시 두 번째가 409를 받는다.
