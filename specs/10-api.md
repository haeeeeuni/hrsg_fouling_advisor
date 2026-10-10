# 10. REST API

---

## 1. 공통 규칙

- 베이스 `/api/`, 버전 없음. JSON 필드는 snake_case.
- 인증: 세션 쿠키 + CSRF. `GET /api/auth/csrf/` 로 CSRF 쿠키를 받는다. JWT 를 쓰지 않는다.
- 권한 표기: **공개**(인증 불필요) / **사용자**(`IsApprovedUser`) / **관리자**(`IsAdminRole`, 명시 지정).
- 목록: DRF 페이지네이션(`count`, `next`, `previous`, `results`).
- 오래 걸리는 작업(문서 색인·재색인, xlsx 가져오기)은 `202` + `job_id` → `GET /api/jobs/{id}/` 폴링.
- 에러 포맷:
  ```json
  { "error": { "code": "VALIDATION_ERROR", "message": "…", "details": { } } }
  ```
- 주요 에러 코드: `VALIDATION_ERROR`(400), `NOT_AUTHENTICATED`(401), `PERMISSION_DENIED`(403), `NOT_FOUND`(404),
  `CONFLICT`(409), `LOGIN_FAILED`(400), `ACCOUNT_PENDING`·`ACCOUNT_REJECTED`·`ACCOUNT_INACTIVE`(403), `LOGIN_LOCKED`(429),
  `LAST_ADMIN_PROTECTED`(409), `SETTING_OUT_OF_RANGE`·`SETTING_TYPE_ERROR`·`UNKNOWN_SETTING`(400),
  `CHAT_UNAVAILABLE`(409), `CHAT_LIMIT_REACHED`(429), `LLM_*`(`04` §7), `THROTTLED`(429).
- 남의 리소스(대화·요청 건)는 403 이 아니라 **404** 로 응답한다(존재 여부 노출 방지).
- Django 자체 관리 화면은 `/django-admin/` 이다(비상용). SPA 의 관리자 모드 `/admin/*` 와 경로가 겹치지 않게 옮겼다.

## 2. 인증·계정 (`01`)

| 메서드 | 경로 | 권한 | 설명 |
|---|---|---|---|
| GET | `/api/auth/csrf/` | 공개 | CSRF 쿠키 |
| POST | `/api/auth/signup/` | 공개 | 가입 신청 → 201, 상태 `PENDING` |
| GET | `/api/auth/username-available/?username=` | 공개 | ID 중복 확인 |
| POST | `/api/auth/login/` | 공개 | `{username, password}` → `{authenticated:true, user}` |
| POST | `/api/auth/logout/` | 사용자 | |
| GET | `/api/auth/me/` | 공개 | `{authenticated, user}` — 비로그인·승인 취소·비활성이면 `{authenticated:false, user:null}`(그 세션은 끊는다) |
| POST | `/api/auth/password/` | 사용자 | 본인 비밀번호 변경 |
| PATCH | `/api/auth/me/` | 사용자 | 성명·소속·이메일 수정 |

## 3. 질의응답 (`02`)

| 메서드 | 경로 | 권한 | 설명 |
|---|---|---|---|
| GET | `/api/chat/status/` | 사용자 | `{status: AVAILABLE\|NO_API_KEY\|DISABLED\|LIMIT_REACHED, remaining_today}` |
| GET | `/api/chat/conversations/` | 사용자 | 내 대화 목록 |
| POST | `/api/chat/conversations/` | 사용자 | 새 대화 |
| GET | `/api/chat/conversations/{id}/` | 사용자 | 대화 + 메시지 |
| PATCH · DELETE | `/api/chat/conversations/{id}/` | 사용자 | 제목 변경 · 삭제 |
| POST | `/api/chat/conversations/{id}/messages/` | 사용자 | `{content}` → 동기 응답: 사용자 메시지 + 어시스턴트 메시지 |
| POST | `/api/chat/messages/{id}/retry/` | 사용자 | 실패한 질문 다시 보내기 |

- 메시지 응답: `content`, `status`, `sources[]`, `calc_cards[]`, `error_code`. 토큰 수·가드 상세는 관리자 API 에서만.

## 4. 계산기 (`05`)

| 메서드 | 경로 | 권한 | 설명 |
|---|---|---|---|
| GET | `/api/calculator/options/` | 사용자 | GT 모델 목록(이름·정격·설계값 — **경보·트립 한계 제외**), 공법 이름 목록, 최신 SMP(값·기준일·출처·추정 여부), 기본값 |
| POST | `/api/calculator/loss/` | 사용자 | 손실·회수 효과(`05` §3) |
| POST | `/api/calculator/methods/` | 사용자 | 공법별 비교(`05` §4) |
| POST | `/api/calculator/pinch-approach/` | 사용자 | 핀치·어프로치(`05` §5) |

- 응답에 계수·식·한계값 원본이 없다(CALC-8). 계산 API 는 저장하지 않는다(부작용 없음 → 디바운스 호출에 안전).

## 5. 체크리스트 (`07`)

| 메서드 | 경로 | 권한 | 설명 |
|---|---|---|---|
| GET · POST | `/api/checklist/requests/` | 사용자 | 내 요청 건 목록 · 생성(템플릿 복사) |
| GET · PATCH · DELETE | `/api/checklist/requests/{id}/` | 사용자 | 상세(항목 포함) · 이름·메모·상태 · 삭제 |
| PATCH | `/api/checklist/requests/{id}/items/{item_id}/` | 사용자 | `{state, memo}` |
| POST | `/api/checklist/requests/{id}/sync-template/` | 사용자 | 템플릿의 새 항목 추가 |
| GET | `/api/checklist/requests/{id}/email-text/?lang=ko\|en&scope=pending\|all` | 사용자 | 복사용 본문 |

## 6. 관리자 (`08`)

| 경로 접두 | 메서드 | 설명 |
|---|---|---|
| `/api/admin/overview/` | GET | 개요 지표 |
| `/api/admin/users/` | GET · PATCH · DELETE | 목록·수정·비활성화(`?approval_status=PENDING`) |
| `/api/admin/users/{id}/approve/` · `/reject/` · `/reset-password/` | POST | 승인(대기·반려 → 승인) · 반려(`{reason}`, 대기만) · 비밀번호 초기화 |
| `/api/admin/login-histories/` | GET | 로그인 이력(`?username=`, `?success=`) |
| `/api/admin/documents/` | GET · POST(multipart) | 문서 목록 · 생성 → 202 + job |
| `/api/admin/documents/{id}/` | GET · PATCH · DELETE | 상세(추출 텍스트 포함) · 수정(→ 재색인 job) · 삭제 |
| `/api/admin/documents/{id}/original/` | GET | 원본 파일 내려받기 |
| `/api/admin/documents/{id}/reindex/` · `/acknowledge-sensitive/` | POST | 재색인 · 민감어 확인 후 색인 |
| `/api/admin/documents/reindex-all/` | POST | 전체 재색인 → 202 + job |
| `/api/admin/sensitive-terms/` | CRUD | |
| `/api/admin/llm/providers/` | GET | 공급자 3종(키는 `has_api_key`·`api_key_hint` 만) |
| `/api/admin/llm/providers/{provider}/` | PATCH | `{model_name, api_key?}` — `api_key` 생략 시 유지 |
| `/api/admin/llm/providers/{provider}/api-key/` | DELETE | 키 삭제 |
| `/api/admin/llm/providers/{provider}/test/` | POST | 연결 테스트 |
| `/api/admin/settings/` | GET · PATCH | 분류별 설정(정의·현재값·기본값) |
| `/api/admin/settings/{key}/reset/` | POST | 기본값으로 |
| `/api/admin/gt-models/` | CRUD | DELETE 는 사용 중지. + `/template/`(xlsx 양식), `/import/`(xlsx, 동기 — 전부 아니면 전무) |
| `/api/admin/cleaning-methods/` | CRUD | DELETE 는 사용 중지 |
| `/api/admin/smp-prices/` | GET · POST · DELETE | |
| `/api/admin/calc-parameter-sets/` | GET · POST | 목록 · 새 버전 생성(활성화) |
| `/api/admin/calc-parameter-sets/{id}/activate/` | POST | 되돌리기 |
| `/api/admin/calc-parameter-sets/preview/` | POST | 후보 파라미터로 예시 입력 결과 미리보기 |
| `/api/admin/checklist-items/` | CRUD | + `/import/`(xlsx → 202), `/export/`, `/reorder/` |
| `/api/admin/usage/` | GET | 일·사용자별 사용량 |
| `/api/admin/audit-logs/` | GET | 필터: 기간·관리자·대상 |

## 7. 기타

| 메서드 | 경로 | 권한 | 설명 |
|---|---|---|---|
| GET | `/api/jobs/{id}/` | 사용자(본인 job) | `status`, `progress`, `stage`, `result`, `error` |
| GET | `/api/health/live/` · `/api/health/ready/` | 공개 | 프로세스 / DB·pgvector 포함 |
| GET | `/api/app-info/` | 공개 | 소개 화면용 — 앱 이름, 기능 설명 문구. 내부 정보 없음 |

## 8. 수용 기준 (AC)

- [ ] AC-10-1 비로그인으로 공개 외 엔드포인트를 부르면 401, USER 로 관리자 엔드포인트를 부르면 403 이다(전수 테스트).
- [ ] AC-10-2 승인 대기 사용자의 세션은 모든 사용자 엔드포인트에서 거부된다.
- [ ] AC-10-3 어떤 응답에도 API 키 평문, 계산 계수, 경보·트립 한계값(USER 응답), 문서 원본이 없다.
- [ ] AC-10-4 남의 대화·요청 건 접근은 404 다.
- [ ] AC-10-5 에러는 항상 공통 포맷이다.
