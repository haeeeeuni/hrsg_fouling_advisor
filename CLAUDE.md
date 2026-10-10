# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 현재 상태 — N2(계산기 + 참조 데이터) 완료

- 2026-10-10 요구사항이 바뀌어 "HRSG Fouling Advisor"(운전 시계열 → 오염도 지수·D-day)에서
  **"HRSG 레퍼런스 앱"**(질의응답 · 계산기 · 플랜트 데이터 요청 체크리스트)으로 전환 중이다.
- 명세 `specs/00~14` 확정(N0). **N1 완료**(브랜치 `feat/reference-app`): 이전 앱 코드 제거, 회원가입·승인·ID 로그인,
  `Setting` 의 `common` 이전, pgvector 확장, 소개·홈·헤더 로그인·라이트/다크·모바일, 관리자 모드(개요·가입 승인·사용자·설정·감사 로그).
  **N2 완료**: `reference`(GT 한계표·공법·SMP·버전 있는 파라미터 세트, 전부 `[임시값]` 시드)와 `calculator`(순수 함수 +
  `runner.py`), 계산기 3탭(게이지·HRSG 도식·차트·URL 복원), 관리자 참조 데이터 4화면. 질의응답·체크리스트는 "준비 중"이다.
  다음은 **N3(체크리스트)**.
- 백엔드 앱: `accounts`·`common`·`reference`·`calculator`. 새 앱은 마일스톤마다 추가하고 `pytest.ini` testpaths·`pyproject` 도 함께 갱신한다.
- **계산 응답은 `calculator/runner.py` 한 곳에서 조립한다.** 뷰와 챗봇 도구(N5)가 같은 함수를 부르게 하려는 것이다.
  응답에 계수·한계값 원본을 넣지 않는다 — `calculator/tests/test_api.py` 가 응답 JSON 에 비밀 키가 없는지 검사한다.
  관리자 파라미터 화면은 항목 정의를 API(`definitions`)로 받아 그려서 프론트 번들에도 계수 이름이 없다(빌드 산출물에서 확인).
- 이전 앱 코드는 로컬 태그 `v1-fouling-advisor`(`3a925ca`), 이전 로컬 DB 는 `~/backups/hrsg/` 덤프에 있다.
  이전 앱 명세는 `specs/archive/v1-fouling-advisor/` — **새 기능을 구현할 때 정본으로 읽지 않는다.**

**`AGENTS.md` 가 코딩 규칙의 단일 진실 공급원이다.** 스택 고정, 레이어 책임, 네이밍, 커밋 규칙은 거기에 있다.
이 문서는 "여러 명세를 읽어야 파악되는 전체 그림"만 담는다.

## 확정된 결정 (다시 제안하지 않는다)

전체 목록(D1~D25)과 근거는 `specs/changes-2026-10.md` §3. 자주 부딪힐 것만 추린다.

| 주제 | 결정 |
|---|---|
| 사용자 접근 | 기술 프롬프트의 "로그인 없이 채팅" 대신 **회원가입 + 관리자 승인**. 승인 전 로그인 불가 |
| 로그인 | **ID + 비밀번호**(상단 우측). 기본 관리자 `admin` / `admin1234!` — 활성 관리자가 없을 때만 생성 |
| LLM | Claude·ChatGPT·Gemini 중 택1, 기본 `claude-opus-5-5`. 키는 관리자 화면 → DB **암호화** 저장 |
| 임베딩 | 로컬 다국어 경량 모델(ONNX) + pg_trgm 하이브리드. 모델은 환경 변수(차원이 스키마에 묶임) |
| 보호 장치 | 고정 보호 규칙·숫자 근거 검사·민감어 가림은 **코드**. 관리자 시스템 프롬프트로 끌 수 없다 |
| 계산식 | 이전 앱 편익 모델 기반 **임시 식**. 관리자는 계수·표만 바꾸고 식 구조는 코드(`formula_version`) |
| Bootstrap | 5.3 (다크 모드). Celery 유지, 응답 비스트리밍 |
| 이메일 | 보내지 않는다. 체크리스트는 클립보드 복사, 알림은 앱 내 배지 |

**실무진 확인이 필요한 것은 `[실무 논의]`, 가상 데이터는 `[임시값]` 으로 표시한다.** 안건 목록은 `specs/changes-2026-10.md` §4.
임시값으로 구현하되 **관리자 화면에서 교체 가능해야** 하고, 사용자 화면에는 "임시 참조값" 안내가 붙는다.

## 명세 읽는 순서

`specs/00-requirements-index.md` §1 문서 지도 → 해당 기능 명세 → `09-data-model.md` → `10-api.md`.
`00` §3.1 에 원 요구사항 문장 → 요구사항 ID 대응표가 있다. 각 명세 끝의 **수용 기준(AC)** 이 테스트 명세다.

## 도메인 한 줄 요약

HRSG(배열회수보일러) 세정·성능에 관한 사내 레퍼런스 앱. 오염되면 배압↑(GT 출력↓)과 굴뚝 온도↑(ST 출력↓)가 생기고,
계산기가 그 손실(원/일)과 세정 시 회수 효과를 계산한다. 용어집은 `PROJECT.md` §3.

## 전체 그림 — 기능 간 결합

```
질문 ─▶ knowledge 검색(벡터 + 키워드, RRF) ─▶ top-k 청크
          │
          ▼
       llm 어댑터 ◀─ [고정 보호 규칙(코드)] + [시스템 프롬프트(관리자)]
          │   └─ 도구 호출 ─▶ calculator(순수 함수) ◀─ reference(GT 한계표·공법·SMP·파라미터 세트)
          ▼                    └─ 입력·결과만 반환(계수·한계값 원본 없음)
       chat 출력 검사(숫자 근거 · 민감어) ─▶ 답변 + 출처 + 계산 카드
```

비자명한 결합:

- **챗봇의 숫자는 계산기에서 나온다.** 그래서 계산기(N2)를 질의응답(N5)보다 먼저 만든다.
  계산 카드의 수치는 같은 입력의 계산기 화면 결과와 같아야 한다(AC-02-3).
- **숫자 근거 검사는 서버 코드다**(`chat/services/guards.py`). 답변 수치가 도구 결과·검색 청크·질문 원문 어디에도 없으면
  1회 재생성, 그래도 위반이면 본문을 막는다. 설정으로 끌 수 없다 — 검수 4의 "근거 없는 수치 0건"이 여기에 걸려 있다.
- **계산식 비공개는 구조로 지킨다.** 계산은 서버에서만 하므로 계산기의 "즉시 반응"은 **디바운스 + 빠른 서버 응답(p95 300ms)** 으로 만든다.
  브라우저로 식을 옮기면 비공개가 깨진다. LLM 도 결과만 받으므로 "계산식 알려줘"에 답할 재료가 없다.
- **USER 응답에 경보·트립 한계값 원본을 주지 않는다.** 상태와 "경보 한계 대비 N%"만 준다(`[실무 논의]` P4 확정 전까지).
- **임베딩은 채팅 LLM 과 분리돼 있다.** 관리자가 채팅 공급자를 바꿔도 재색인이 필요 없다. 반대로 청크 설정이나 임베딩 모델을 바꾸면 **전체 재색인**이 필요하다.
- **API 키는 공급자별로 따로 저장된다.** 활성 공급자의 키가 없으면 채팅 입력창이 비활성이고(`/api/chat/status/`), 계산기·체크리스트는 그대로 동작한다.
- **재색인은 원자적이다.** 색인 중에도 옛 버전 청크로 답한다(`indexed_version`).
- **체크리스트 요청 건은 생성 시 템플릿을 복사한다.** 관리자가 템플릿을 바꿔도 진행 중인 건은 바뀌지 않는다.
- **계산 파라미터는 버전 세트다.** 저장하면 새 버전이 활성화되고, 결과에 `param_version` 이 붙는다. 식 구조 변경은 `formula_version`(코드).
- **원본 파일은 DB(BinaryField)에 있다.** Render 디스크는 재배포 때 사라진다.

## 지켜야 할 시스템 불변식

1. **숫자는 계산기에서만** — 위 결합 참고.
2. **비공개 대상**(원문·고객사·발전소·개인 정보·계산식·API 키)은 USER API·프론트 번들·LLM 요청·로그에 없다(`specs/13` §1 표).
3. **설정값은 DB.** 코드에는 시드만. 예외는 임베딩 모델(환경 변수). 새 튜닝값은 시드 + 관리자 화면 + `specs/08` §4 표를 같은 변경에 넣는다.
4. **승인된 사람만.** 기본 권한은 `IsApprovedUser`, 관리자 API 는 `IsAdminRole` 을 명시. 남의 리소스는 404.
5. **재현성.** 계산 결과 = 입력 + 파라미터·식·참조값 버전 + SMP 기준일.

## 이전 앱에서 배운 것 (새 앱에도 해당)

- **UTC/KST:** 서버는 UTC 를 준다. 날짜 문자열 앞 10자를 자르지 말고 dayjs·`timezone.localtime` 으로 바꾼다. 같은 버그가 세 번 났다.
- **"계산 불가"를 0 으로 표시하지 않는다**(`?? 0` 패턴 주의). 회복률 0.0 % 오표시가 실제로 있었다.
- **늦게 도착한 응답:** 전환·연속 입력 화면은 마지막 요청만 반영한다(계산기 디바운스, 대화 전환).
- **PDF 한글:** 이전 앱은 PDF 생성에서 폰트 경로 문제를 겪었다. 새 앱은 PDF 를 **읽기만** 하므로 해당 없음.
- **Render 무료 플랜 메모리(512MB):** 이전 앱이 분석 중 OOM 으로 죽었다. 임베딩 모델 메모리를 N4 초기에 실측한다.

## 명령어

정본은 `AGENTS.md` §10. 새 앱 명령(`load_virtual_kb`, `eval_chat`)은 해당 마일스톤 이후 유효하다.

```bash
docker compose up -d db redis          # SQLite 금지 — 로컬·테스트도 PostgreSQL
cd backend && source .venv/bin/activate
python manage.py migrate && python manage.py seed_defaults
python manage.py runserver
celery -A config worker -l info --pool=solo
pytest                                  # 전체
pytest path/to/test_file.py::test_name  # 단일 테스트
pytest -m "not django_db"               # DB 없이 순수 함수만
cd frontend && npm run dev | npm run build | npm run test
cd .. && npm run test:e2e
```

## 테스트 환경에서 한 번씩 걸리는 것

- **자동 테스트는 실제 LLM 을 부르지 않는다.** 가짜 공급자(`llm/providers/fake.py`)를 쓴다. E2E 서버는 `LLM_FAKE_MODE=1`(prod 에서는 무시).
- **Celery eager 모드는 `override_settings` 로만 켜진다.** `current_app.conf` 대입·`conf.update()` 는 먹히지 않는다
  (`config_from_object("django.conf:settings")` 라 Django settings 가 우선). `EAGER_PROPAGATES` 는 꺼 둔다 —
  켜면 태스크 예외가 뷰까지 올라와 500 이 되어, 운영의 "202 후 워커 실패 기록" 경로를 검증할 수 없다.
- **로그인 스로틀 카운터는 테스트마다 비운다**(IP 분당 10회). E2E 는 저장된 관리자 세션을 재사용하고, 다른 사용자 로그인은 **빈 쿠키로 시작**한다
  (관리자 세션을 물려받은 채 로그인하면 Django 가 세션을 폐기한다).
- **macOS 에서 Celery 는 `--pool=solo`.** 기본 prefork 는 태스크를 받자마자 죽고 화면은 끝없이 기다린다.
- **Vite 는 `localhost`(IPv6)에만 바인딩된다.** `127.0.0.1:5173` 으로는 접속되지 않는다.
- **E2E 는 Django 를 `THROTTLE_SIGNUP=1000/hour` 로 띄워야 한다.** 가입 스로틀(IP 시간당 10회)에 걸려 두세 번째 실행부터 실패한다.
- **로컬 PostgreSQL(Homebrew `postgresql@16`)에는 pgvector 를 소스로 빌드해 넣었다.** Homebrew `pgvector` 는 17·18 용만 있다.
  빌드 시 `pg_config` 가 없는 SDK 경로(MacOSX26.sdk)를 가리키므로 `make PG_SYSROOT=$(xcrun --show-sdk-path)` 가 필요하다.
- **Bootstrap `data-bs-dismiss` 를 `<RouterLink>` 에 달지 않는다.** Bootstrap 이 링크 기본 동작을 막아 이동이 취소된다
  (관리자 사이드바가 먹통이 된 적 있다). 오프캔버스·접힘 메뉴는 경로 변경을 watch 해 코드로 닫는다.
- **개발 서버를 `--noreload` 로 띄운 채 오래 두지 않는다.** 10월 4·7일에 띄운 옛 Django·Vite·Celery 가 남아 옛 코드를 서빙하고 있었다.
  작업 시작 시 `ps -ax | grep -E "runserver|vite|celery"` 로 확인한다.
- **Django 자체 관리 화면은 `/django-admin/`** 이다. `/admin/*` 는 SPA 관리자 모드다.
- **Node 26 의 `localStorage` 전역**은 `--localstorage-file` 없이 `undefined` 이고 jsdom 구현을 가린다. `frontend/tests/setup.js` 가 비어 있을 때만 채운다.
- **zsh 글로브 실패 시 grep 이 0건을 돌려준다**(`--include=*.vue` 등은 인용부호로 감싼다). 검색 결과가 0건이면 명령부터 의심한다.
