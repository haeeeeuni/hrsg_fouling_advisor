# AGENTS.md — 코딩 에이전트 작업 지침

이 저장소에서 코드를 작성·수정하는 모든 AI 에이전트와 개발자는 이 문서의 규칙을 따른다.
프로젝트 개요는 `PROJECT.md`, 상세 요구사항은 `specs/`(정본은 `specs/` 바로 아래, `specs/archive/` 는 이전 앱)에 있다.

---

## 1. 최우선 원칙

1. **명세 우선(Spec-first).** 코드를 쓰기 전에 해당 기능의 `specs/*.md` 를 읽는다. 명세와 코드가 충돌하면 명세가 우선이다.
   명세가 틀렸다고 판단되면 코드를 고치기 전에 명세를 먼저 고치고 근거를 남긴다.
2. **설정값은 코드에 하드코딩하지 않는다.** RAG·LLM 파라미터, 한도, 계산 계수, 판정 기준처럼 튜닝 가능한 값은 DB
   (`Setting`, `CalcParameterSet`, 참조 데이터 모델)에 두고 관리자 화면에서 바꾼다. 코드에는 **초기 시드값**만 둔다.
   물리적 타당성 검증 범위처럼 튜닝값이 아닌 상수는 이름 붙은 모듈 상수로 둔다(로직 한가운데 매직 넘버 금지).
3. **숫자는 계산기에서만, 비공개는 구조로.** 챗봇이 수치를 지어내지 못하게 하고(`specs/02` CHAT-4), 계산식·계수·API 키가
   USER 응답·프론트 번들·LLM 요청에 들어가지 않게 한다(`specs/05` CALC-8). 프롬프트 지시에만 기대지 않는다.
4. **재현성.** 계산 결과는 입력·파라미터 버전·식 버전·참조값 버전·SMP 기준일을 함께 남긴다.
5. **한국어 우선.** UI 문구·사용자 대상 에러 메시지는 한국어. 코드 식별자·주석은 영어, 도메인 용어 주석은 한국어 병기 허용.
6. **추측 금지.** 요구사항이 모호하면 임의로 확장하지 말고, 명세에 `TODO(질문):` 로 남기고 가장 단순한 해석으로 구현한다.
   `[실무 논의]` 항목은 명세의 임시 처리대로만 구현한다.

---

## 2. 기술 스택 고정

변경하려면 사전 합의가 필요하다.

| 레이어 | 고정 스택 |
|---|---|
| Frontend | Vue 3 (Composition API, `<script setup>`), Vite, Vue Router, Pinia, **Bootstrap 5.3**, 순수 CSS3, Chart.js + vue-chartjs |
| Backend | Python 3.11+, Django 5.x, Django REST Framework, Django ORM |
| DB | PostgreSQL 16 + **pgvector**(`vector`), `pg_trgm` |
| 임베딩 | 로컬 다국어 경량 모델, ONNX Runtime(PyTorch 금지) — `specs/03` §5 |
| LLM | 공식 SDK: `anthropic`, `openai`, `google-genai` — 어댑터 안에서만 import(`specs/04` §5) |
| 문서 추출 | `pypdf`(PDF), `python-docx`(Word) |
| 암호화 | `cryptography`(Fernet) — API 키 저장 |
| 엑셀 | `openpyxl`(참조표·체크리스트 가져오기/내보내기) |
| 비동기 | Celery + Redis(문서 색인·가져오기) |
| 운영 | Gunicorn + Nginx, Docker Compose / Render(데모) |

- **금지:** TypeScript 전환, Options API 혼용, jQuery, Bootstrap 이외 UI 프레임워크, Django Template 화면(`/admin/` 제외),
  **SQLite(운영·로컬·테스트 전부)**, LangChain 류 RAG 프레임워크(검색·프롬프트 조립은 직접 구현 — 보호 장치를 코드로 통제하기 위해).
- Bootstrap 은 기술 프롬프트의 5.0 이 아니라 5.3 이다 — 라이트/다크 컬러 모드(`data-bs-theme`) 때문(`specs/changes-2026-10.md` D11).
- 표에 없는 보조 라이브러리(axios, dayjs, psycopg 등)는 `requirements.txt` / `package.json` 이 정본이다. 아키텍처를 바꾸는 추가만 사전 합의 대상이다.
- 이전 앱 전용 의존성(pandas, numpy, scikit-learn, scipy, joblib, ReportLab, matplotlib)은 N1 전환에서 제거한다.

---

## 3. 디렉터리와 레이어

```
backend/
  config/       settings(base/dev/test/prod/demo), urls, celery
  accounts/     User(AbstractUser), 가입·승인·로그인
  chat/         대화 모델·뷰, services/(prompt 조립, guards)
  knowledge/    문서·청크 모델, services/(extract, chunking, embedding, retrieval)
  llm/          providers/(base, anthropic, openai, gemini, fake), registry, crypto
  calculator/   services/(loss, methods, pinch_approach, steam) — 모델 없음
  reference/    GtModel, CleaningMethod, SmpPrice, CalcParameterSet
  checklist/    템플릿·요청 건
  common/       Setting, AuditLog, Job, 예외·에러 포맷, 권한 클래스
  fixtures/     virtual_kb/, eval/ (가상 데이터, specs/14 §3)
frontend/src/
  api/  stores/  router/  views/  views/admin/  components/  composables/  utils/  assets/styles/
```

### 레이어 책임
- **View(DRF):** HTTP 입출력, 권한, 직렬화. 계산·검색·프롬프트 로직을 두지 않는다.
- **Serializer:** 입력 검증, 표현 변환. **USER 용 serializer 에 비밀 필드(계수, 한계값 원본, 키, 원본 파일)를 넣지 않는다.**
- **Service(`*/services/*.py`):** 순수 함수 중심. 계산(`calculator`), 가드(`chat/services/guards.py`), 청크·점수 결합(`knowledge`)은
  Django 모델을 import 하지 않고 dataclass/dict 로 입출력한다 → DB 없이 단위 테스트.
- **Provider 어댑터(`llm/providers`):** 공급자 SDK 는 여기서만 import 한다. 밖으로는 공통 타입만 내보낸다.
- **Model:** 데이터 정의와 단순 파생 속성만.

---

## 4. 코딩 컨벤션

### Python
- `black`(line-length 100), `isort`, `ruff`. 공개 함수 타입 힌트 필수. 함수는 한 가지 일, 60줄 넘으면 분리 검토.
- 예외는 `common/exceptions.py` 의 도메인 예외 → DRF 핸들러가 공통 JSON 으로 변환.
- 시간은 timezone-aware. DB 는 UTC, 표시·일 단위 집계(질문 한도 등)는 KST.
- 외부 호출(LLM, 임베딩 다운로드 등)에는 항상 시간 제한을 둔다.

### Vue / JS
- `PascalCase.vue`, 페이지는 `views/XxxView.vue`. `<script setup>` 만.
- API 호출은 `src/api/*.js` 경유. 컴포넌트에서 axios 직접 호출 금지.
- 전역 상태는 Pinia `auth`, `ui`, `chat` 으로 한정.
- 스타일은 Bootstrap 유틸리티 우선, 테마 색은 CSS 변수. 셸 클래스는 `ui-` 접두.
- 숫자는 `utils/format.js`. **`null` 은 "계산 불가"** 로 표시하고 `?? 0` 을 쓰지 않는다.
- 늦게 도착한 응답은 버린다(마지막 요청만 반영).

### 네이밍
| 대상 | 규칙 | 예 |
|---|---|---|
| Python 모듈/함수/변수 | snake_case | `compute_power_loss` |
| Django 모델 | PascalCase 단수 | `KnowledgeDocument` |
| 엔드포인트 | 소문자 kebab, 복수 | `/api/admin/gt-models/` |
| JSON 필드 | snake_case | `daily_loss_won` |
| 수치 필드 | 단위 접미사 | `_mw`, `_c`, `_kpa`, `_won`, `_barg`, `_pct` |
| 상수 | UPPER_SNAKE | `MAX_BACKPRESSURE_KPA` |

---

## 5. 도메인 규칙

1. **챗봇 수치 규칙**: 답변 수치는 도구 결과·검색 청크·질문 원문에만 근거한다. 출력 검사는 끌 수 없다(`specs/02` §5).
2. **보호 규칙은 두 층**: 코드 고정 규칙 + 관리자 시스템 프롬프트. 고정 규칙이 항상 앞에 붙는다(`specs/02` §4).
3. **도구 결과는 입력과 결과만**: 계수·한계값 원본을 넣지 않는다(`specs/04` §6).
4. **임시값 표시**: `is_placeholder` 참조값을 쓴 계산은 `uses_placeholder=true` 로 응답하고 화면에 안내한다(`specs/06` REF-6).
5. **SMP 는 기준일·출처와 함께**(`specs/06` REF-4).
6. **민감어는 색인 시 경고, 출력 시 가림**(`specs/03` KB-9).
7. **재색인은 원자적으로**: 새 청크를 다 만든 뒤 교체(`specs/03` §4).

---

## 6. API 규칙

- 베이스 `/api/`. 인증은 **세션 쿠키(HttpOnly, SameSite=Lax) + CSRF**. JWT 금지.
- 기본 권한 `IsApprovedUser`. 관리자 API 는 `IsAdminRole` 을 **명시**한다(기본값에 의존 금지). 공개 엔드포인트는 `specs/10` 에 나열된 것뿐.
- 목록은 DRF 페이지네이션. 에러는 `{ "error": { "code", "message", "details" } }`.
- 오래 걸리는 작업(색인, 가져오기)은 `202` + `job_id`. 질의응답은 동기(`specs/04` LLM-8).
- 남의 리소스는 404. 파괴적 작업은 `DELETE` 만, 서버에서 권한 재확인.

---

## 7. 보안 규칙

- 비밀번호는 Django 해셔. 평문 저장·로그 금지.
- 기본 관리자 `admin` / `admin1234!` 는 **활성 관리자가 없을 때만** 생성하고, 로그인 후 비밀번호 변경 배너를 띄운다(`specs/01` §6).
- LLM API 키는 Fernet 암호화 저장(`FIELD_ENCRYPTION_KEY`), 응답엔 끝 4자만, 로그·감사 로그 제외.
- 로그에 질문·답변 본문, 문서 본문, 키, 비밀번호를 남기지 않는다.
- 업로드는 확장자·MIME·크기 검증, 암호 파일 거부. xlsx 내보내기는 수식 인젝션 방지.
- `SECRET_KEY`, `FIELD_ENCRYPTION_KEY`, DB 비밀번호는 환경 변수. 커밋 금지.

---

## 8. 테스트 규칙

- 백엔드 `pytest` + `pytest-django`(PostgreSQL + pgvector). 순수 함수 서비스 커버리지 80 % 이상.
- **자동 테스트는 실제 LLM 을 부르지 않는다.** 가짜 공급자를 쓴다. 실제 LLM 평가는 `eval_chat` 으로 수동 실행(`specs/14` §3).
- 성질 기반 검증: 계산 단조성·결정론, 가드가 근거 없는 수치를 반드시 잡음, 청크가 원문을 빠짐없이 덮음.
- API 는 권한 전수(401/403/승인 대기 거부)와 **응답에 비밀 필드 없음**을 반드시 검사한다.
- 프론트 `vitest`(포맷터·스토어·디바운스·복사 문구). E2E 는 Playwright(`specs/14` §4.3).

---

## 9. 작업 절차

1. `PROJECT.md` 와 해당 `specs/*.md` 를 읽는다(`specs/00` §1 문서 지도).
2. 영향 범위 파악(모델 변경 → 마이그레이션).
3. 백엔드: 모델 → 마이그레이션 → 서비스 → 시리얼라이저 → 뷰 → URL → 테스트.
4. 프론트: api 모듈 → 스토어 → 뷰/컴포넌트 → 라우트 → 테스트.
5. 설정값이 생기면 시드 정의와 관리자 화면 항목을 같은 변경에 넣고 `specs/08` §4 표를 갱신한다.
6. 테스트 결과를 그대로 보고한다(실패를 숨기지 않는다).
7. 명세에 없는 동작을 추가했다면 해당 명세를 갱신한다. 실무 확인이 필요하면 `[실무 논의]` 로 표시하고 `specs/changes-2026-10.md` §4 에 추가한다.

### 금지 행동
- 이미 적용된 마이그레이션 파일을 지우고 다시 만들기(N1 의 일괄 재시작은 예외 — `specs/09` §9)
- 테스트를 통과시키려고 단언 약화
- 명세에 없는 라이브러리 임의 추가
- 요구되지 않은 리팩터링으로 범위 확장
- 실패한 단계를 "완료"로 보고

---

## 10. 명령어

```bash
docker compose up -d db redis          # PostgreSQL(pgvector) + Redis

cd backend && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                   # 최초 1회 — FIELD_ENCRYPTION_KEY 포함
python manage.py migrate
python manage.py seed_defaults         # 기본 관리자 + 설정 + 가상 참조 데이터 + 체크리스트 템플릿 (멱등)
python manage.py load_virtual_kb       # 가상 지식 베이스 (개발용)
python manage.py runserver
celery -A config worker -l info --pool=solo   # macOS 는 --pool=solo
pytest
pytest -m "not django_db"              # 순수 함수만
python manage.py eval_chat --questions fixtures/eval/questions.yaml --out eval-report.md   # 실제 LLM 평가(수동)

cd frontend && npm install && npm run dev
npm run build && npm run test

cd .. && npm run test:e2e              # E2E (가짜 LLM 모드 서버 대상)
```

> N1 전환 전까지 저장소의 코드는 이전 앱이며 위 명령 중 일부(`load_virtual_kb`, `eval_chat`)는 아직 없다.

---

## 11. 커밋 규칙

- Conventional Commits: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`. 제목은 한국어, 50자 이내. 본문에 이유와 영향 범위.
- 하나의 커밋은 하나의 논리적 변경. 모델 변경과 마이그레이션은 같은 커밋.
- 사용자가 요청하지 않은 커밋·푸시는 하지 않는다. "커밋"과 "푸시"는 따로 요청받는다.
