# 09. 데이터 모델

Django 앱별 모델 정의다. 필드 의미와 규칙은 각 기능 명세에 있고, 여기서는 구조만 정한다.
공통: 모든 모델에 `created_at`, `updated_at`(timezone-aware, DB 는 UTC). PK 는 기본 `BigAutoField`.

---

## 1. 앱 구성

| 앱 | 모델 | 명세 |
|---|---|---|
| `accounts` | `User`, `LoginHistory` | 01 |
| `knowledge` | `KnowledgeDocument`, `DocumentChunk`, `SensitiveTerm` | 03 |
| `llm` | `LlmProviderConfig`, `LlmUsageDaily` | 04 |
| `chat` | `Conversation`, `Message` | 02 |
| `calculator` | (모델 없음 — 순수 함수) | 05 |
| `reference` | `GtModel`, `CleaningMethod`, `SmpPrice`, `CalcParameterSet` | 06 |
| `checklist` | `ChecklistTemplateItem`, `DataRequest`, `DataRequestItem` | 07 |
| `common` | `Setting`, `AuditLog` | 08, 13 |

## 2. accounts

```
User(AbstractUser)
  username            CharField(30, unique)        USERNAME_FIELD, 소문자 저장
  full_name           CharField(50)
  organization        CharField(100)
  email               EmailField(blank)
  signup_reason       TextField(500, blank)
  role                CharField choices USER|ADMIN, default USER
  approval_status     CharField choices PENDING|APPROVED|REJECTED, default PENDING, index
  approved_by         FK(User, null, SET_NULL)
  approved_at         DateTimeField(null)
  rejection_reason    TextField(blank)
  must_change_password BooleanField(default False)
  last_login_at       DateTimeField(null)
  # first_name, last_name 미사용
  # 로그인 잠금은 별도 필드 없이 LoginHistory 의 최근 연속 실패로 판정한다(01 AUTH-8)
  REQUIRED_FIELDS = ['full_name', 'organization']

LoginHistory
  user FK(null) · attempted_username · success · fail_reason · ip · user_agent · created_at
  # fail_reason: NOT_FOUND | BAD_PASSWORD | PENDING | REJECTED | INACTIVE | LOCKED
```

## 3. knowledge

```
KnowledgeDocument
  title               CharField(200)
  category            CharField choices COMPANY|PRODUCT|TECHNICAL|CASE
  description         TextField(blank)
  input_type          CharField choices TEXT|DOCX|PDF
  body_text           TextField(blank)             TEXT 입력 본문
  original_file       BinaryField(null)            DOCX/PDF 원본 (DB 저장, 03 §3)
  original_filename   CharField(255, blank)
  original_size_bytes PositiveIntegerField(null)
  extracted_text      TextField(blank)             추출 결과 (관리자 미리보기·재색인용)
  is_enabled          BooleanField(default True)
  index_status        CharField choices PENDING|INDEXING|READY|FAILED
  index_error         TextField(blank)
  indexed_version     PositiveIntegerField(null)   검색에 쓰이는 청크의 문서 버전
  version             PositiveIntegerField(default 1)
  sensitive_hits      JSONField(default list)      [{term, position, snippet}]
  sensitive_ack       BooleanField(default False)  "그대로 색인" 확인
  created_by / updated_by FK(User)

DocumentChunk
  document            FK(KnowledgeDocument, CASCADE)
  document_version    PositiveIntegerField
  seq                 PositiveIntegerField
  section_title       CharField(300, blank)
  page                PositiveIntegerField(null)
  content             TextField
  embedding           VectorField(dimensions=384)          pgvector
  # 인덱스: HNSW(embedding vector_cosine_ops), GIN(content gin_trgm_ops)
  unique (document, document_version, seq)

SensitiveTerm
  term CharField(100, unique, 대소문자 무시) · note · is_active
```

- `VectorField` 는 `pgvector` 파이썬 패키지의 Django 통합을 쓴다. 차원(384)은 임베딩 모델에 묶인다(`03` §5).

## 4. llm

```
LlmProviderConfig                      공급자당 1행 (ANTHROPIC, OPENAI, GEMINI)
  provider            CharField(unique) choices
  model_name          CharField(100)
  api_key_encrypted   TextField(blank)             Fernet 암호문. 평문 필드 없음
  api_key_hint        CharField(8, blank)          끝 4자
  last_test_at        DateTimeField(null)
  last_test_ok        BooleanField(null)
  last_error_code     CharField(40, blank)
  last_error_at       DateTimeField(null)
  # 활성 공급자는 Setting llm_active_provider

LlmUsageDaily
  date · user FK · provider · model_name · question_count · input_tokens · output_tokens · error_count
  unique (date, user, provider, model_name)
```

## 5. chat

```
Conversation
  user FK(User, CASCADE) · title CharField(100)

Message
  conversation        FK(Conversation, CASCADE)
  role                CharField choices USER|ASSISTANT
  content             TextField
  status              CharField choices OK|FAILED|BLOCKED
  sources             JSONField(default list)      [{document_id, title, category, section_title, page, snippet}]
  calc_cards          JSONField(default list)      [{tool, inputs, outputs, param_version, formula_version, smp_as_of}]
  provider · model_name
  input_tokens · output_tokens · latency_ms
  guard_result        JSONField(default dict)      {numeric_violations, masked_count, regenerated}
  error_code          CharField(40, blank)
```

## 6. reference

```
GtModel
  name (unique) · manufacturer · rated_gt_mw · rated_st_mw(null)
  design_backpressure_kpa · backpressure_alarm_kpa · backpressure_trip_kpa
  design_exhaust_temp_c · exhaust_temp_alarm_c · exhaust_temp_trip_c
  design_stack_temp_c · is_placeholder · is_active · note · version
  CheckConstraint: alarm < trip (배압·배기온도 각각), rated_gt_mw > 0

CleaningMethod
  name (unique) · cleaning_cost_won · outage_days · recovery_ratio · is_placeholder · is_active · version
  CheckConstraint: 0 < recovery_ratio ≤ 1, cost ≥ 0, outage_days ≥ 0

SmpPrice
  value_won_per_kwh · as_of_date · period_label(blank) · source · is_estimate · created_by

CalcParameterSet
  version_label (unique, 예 p1) · params JSONField · is_active · is_seed · note · created_by
  부분 unique: is_active=True 는 1행
```

## 7. checklist

```
ChecklistTemplateItem
  category · name_ko · name_en · unit · is_required · why_needed_ko · why_needed_en
  source FORM|ADDED · is_calculator_input · order · is_active · is_placeholder

DataRequest
  owner FK(User, CASCADE) · title · memo · due_date(null)
  status IN_PROGRESS|DONE|ARCHIVED · template_snapshot_at

DataRequestItem                         요청 건 생성 시 템플릿을 복사 (07 §3)
  request FK(DataRequest, CASCADE) · template_item FK(null, SET_NULL)
  category · name_ko · name_en · unit · is_required · why_needed_ko · why_needed_en · order   (복사본)
  state PENDING|RECEIVED|NOT_APPLICABLE · received_at(null) · memo
```

## 8. common

```
Setting
  key (unique) · value(문자열) · value_type · category · label · description · default_value
  min_value · max_value · unit_label · updated_by
  # 정본은 코드 정의(common/setting_defaults.py 의 SETTING_DEFS). seed_defaults 가 메타데이터를 동기화하고
  # 관리자가 바꾼 value 는 덮어쓰지 않는다

AuditLog
  actor FK · action · target_type · target_id · before JSONField · after JSONField · ip · created_at

# Job 테이블은 두지 않는다. 202 + job 상태는 Celery 결과 백엔드(Redis)에 있고(common/jobs.py),
# 영속 기록은 KnowledgeDocument.index_status 같은 도메인 필드가 맡는다.
```

## 9. 이전 앱 모델

`units`, `ingestion`, `analysis`, `maintenance`, `reports` 앱의 모델은 새 앱에서 쓰지 않는다.
전환 시 앱째 제거하고 마이그레이션을 새로 시작한다(`changes-2026-10.md` §3, `01` §2 의 마이그레이션 주의).
