# HRSG 레퍼런스 앱

HRSG(배열회수보일러) 세정·성능에 관한 사내 웹앱.
**질문에 답하고, 손실과 세정 효과를 계산하고, 정확한 평가에 필요한 플랜트 데이터를 빠짐없이 받도록 돕는다.**

> **전환 중 (2026-10-10 ~).** 기반(N1)까지 구현됐다 — 회원가입·승인, 소개·홈, 관리자 모드, 라이트/다크.
> 질의응답·계산기·체크리스트는 다음 단계에서 채운다. 진행 단계는 아래 [진행 상황](#진행-상황), 경위는 `specs/changes-2026-10.md`.

---

## 기능

| 기능 | 내용 |
|---|---|
| **질의응답** | 기술 자료·사례를 근거로 답하는 챗봇(RAG). 수치가 필요하면 계산기를 호출해 **계산 카드**로 보여 준다. 한국어·영어 |
| **계산기** | GT 모델과 운전값 → 현재 상태(정상·경보·트립), 예상 손실(원/일), 세정 회수 효과, 공법별 비용 비교, 핀치·어프로치 점검. 게이지·HRSG 도식·그래프 |
| **데이터 요청 체크리스트** | 평가에 필요한 데이터 항목을 요청 건별로 체크하고, 미수신 항목을 이메일 본문으로 복사 |
| **관리자 모드** | 가입 승인, 지식 베이스(Text·Word·PDF), LLM(Claude·ChatGPT·Gemini) 키·모델, RAG 설정, 참조 데이터·계산 파라미터 |

- 회원가입 후 **관리자 승인**을 받아야 로그인할 수 있다.
- 챗봇은 숫자를 지어내지 않는다 — 답변의 수치는 계산기 결과나 근거 문서에 있는 값뿐이며 서버가 검사한다.
- 계산 방식은 비공개다. 화면·API 는 입력과 결과만 보여 준다.

## 아키텍처

```
Vue 3 SPA (Vite · Bootstrap 5.3 · Pinia · Chart.js)
    │  HTTP / JSON
    ▼
Django REST Framework ── Celery(문서 색인) ── Redis
    │  Django ORM
    ▼
PostgreSQL + pgvector          (질의응답 시) LLM API — Claude / ChatGPT / Gemini
```

| 레이어 | 기술 |
|---|---|
| Frontend | Vue 3, Vite, Vue Router, Pinia, Bootstrap 5.3, Chart.js |
| Backend | Python 3.11+, Django 5, Django REST Framework |
| DB | PostgreSQL 16 + pgvector, pg_trgm |
| RAG | 로컬 다국어 임베딩(ONNX) + 하이브리드 검색 |
| LLM | Anthropic · OpenAI · Google 공식 SDK (관리자가 택1, 기본 Claude Opus 5.5) |
| 비동기·운영 | Celery + Redis, Gunicorn + Nginx, Docker Compose / Render |

정본은 `AGENTS.md` §2.

## 시작하기

```bash
docker compose up -d db redis         # PostgreSQL 16 + pgvector, Redis

cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                  # FIELD_ENCRYPTION_KEY 등
python manage.py migrate
python manage.py seed_defaults        # 기본 관리자 · 설정 · 가상 참조 데이터 · 체크리스트 템플릿
python manage.py load_virtual_kb      # 가상 지식 베이스(개발용, N4 이후)
python manage.py runserver
celery -A config worker -l info --pool=solo    # 별도 터미널

cd ../frontend && npm install && npm run dev   # http://localhost:5173
```

Docker 대신 로컬에 설치한 PostgreSQL 을 쓴다면 pgvector 확장이 있어야 한다(`CREATE EXTENSION vector` 가 마이그레이션에 있다).
Homebrew 는 `pgvector` 를 PostgreSQL 17·18 용으로만 주므로 16 이면 소스로 빌드한다:
`make PG_CONFIG=$(brew --prefix postgresql@16)/bin/pg_config PG_SYSROOT=$(xcrun --show-sdk-path) && make install ...`(같은 인자).

**기본 관리자:** ID `admin` / 비밀번호 `admin1234!` — 활성 관리자가 없을 때만 생성되며, 첫 로그인 후 비밀번호를 바꾸라는 배너가 뜬다.
LLM API 키는 관리자 모드 > LLM 설정에서 입력한다. 키가 없으면 질의응답만 비활성이고 나머지 기능은 동작한다.

## 테스트

```bash
cd backend && pytest                  # 실제 LLM 을 부르지 않는다(가짜 공급자)
cd frontend && npm run test
npm run test:e2e                      # 루트, Playwright + Chrome — Django 를 THROTTLE_SIGNUP=1000/hour 로 띄운 뒤
python manage.py eval_chat --questions fixtures/eval/questions.yaml --out eval-report.md   # 실제 LLM 품질 평가(수동)
```

## 문서

| 문서 | 내용 |
|---|---|
| `PROJECT.md` | 개요·범위·용어·아키텍처·마일스톤 |
| `AGENTS.md` | 코딩 규칙, 스택 고정, 레이어 책임, 커밋 규칙 |
| `CLAUDE.md` | 여러 명세를 읽어야 보이는 전체 그림과 비자명한 결합 |
| `specs/00~14` | 기능별 상세 명세. `00` 이 색인. 각 문서 끝의 **수용 기준(AC)** 이 테스트 명세 |
| `specs/changes-2026-10.md` | 요구사항 변경 경위, 결정 기록, **실무 논의 안건** |
| `specs/archive/` | 이전 앱 명세(정본 아님) |
| `DEPLOY.md` | 운영 배포 절차(현재는 이전 앱 기준 — N7 에서 갱신) |

## 진행 상황

| 단계 | 내용 | 상태 |
|---|---|---|
| N0 | 요구사항·명세 확정 | **완료** (2026-10-10) |
| N1 | 기반 전환 — 이전 앱 제거, 가입·승인, pgvector, 소개·홈, 라이트/다크 | **완료** |
| N2 | 계산기 + 참조 데이터 | 예정 |
| N3 | 데이터 요청 체크리스트 | 예정 |
| N4 | 지식 베이스(문서·임베딩·검색) | 예정 |
| N5 | LLM 연동 + 질의응답 | 예정 |
| N6 | 관리자 마무리 · 가상 데이터 · 평가 스크립트 | 예정 |
| N7 | 검수 시나리오 8종 · 배포 | 예정 |

계산식·GT 한계표·공법 비용·체크리스트 항목은 현재 **임시값**이다. 실무진 자료를 받으면 관리자 모드에서 교체한다.
