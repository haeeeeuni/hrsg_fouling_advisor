# 04. LLM 연동

관련 요구사항: LLM-1 ~ LLM-9

---

## 1. 공급자 (LLM-1)

- **LLM-1** 관리자는 다음 셋 중 **하나를 활성 공급자로** 고른다. 한 번에 하나만 쓴다.

  | 코드 | 공급자 | 기본 모델 |
  |---|---|---|
  | `ANTHROPIC` | Claude | **`claude-opus-5-5`** (Opus 5.5) |
  | `OPENAI` | ChatGPT | TODO(질문): 구현 시점에 공급자 문서에서 확인해 시드 |
  | `GEMINI` | Gemini | TODO(질문): 구현 시점에 공급자 문서에서 확인해 시드 |

- 초기 활성 공급자는 `ANTHROPIC` 이다.
- 공급자별로 API 키·모델 이름을 **따로** 저장한다. 공급자를 바꿔도 다른 공급자의 키는 지워지지 않는다.

## 2. API 키 (LLM-2, LLM-3)

- **LLM-2** API 키는 관리자 화면에서 입력하고 **PostgreSQL 에 암호화해 저장**한다.
  - 암호화: `cryptography` 의 Fernet. 암호화 키는 환경 변수 `FIELD_ENCRYPTION_KEY` 다(`SECRET_KEY` 와 분리 — `SECRET_KEY` 를 바꿔도 저장된 키가 깨지지 않게).
  - `prod` 설정은 `FIELD_ENCRYPTION_KEY` 가 없으면 기동을 거부한다.
  - **키는 어떤 API 응답에도 평문으로 나가지 않는다.** 조회 응답은 `has_api_key: true`, `api_key_hint: "…a1b2"`(끝 4자)뿐이다.
  - 입력란은 쓰기 전용이다. 비워 두고 저장하면 기존 키를 유지하고, "키 삭제" 버튼으로만 지운다.
  - 감사 로그에는 "API 키 변경(ANTHROPIC)"만 남기고 값은 남기지 않는다. 애플리케이션 로그에도 남기지 않는다.
- **LLM-3** 활성 공급자의 키가 없으면 채팅은 비활성이다(`02` CHAT-8).
- **연결 테스트:** 저장 전·후에 "연결 테스트" 버튼으로 짧은 요청을 보내 키·모델이 유효한지 확인한다. 결과(성공/오류 코드·시각)를 저장해 관리자 화면에 보여 준다.

## 3. 모델 선택 (LLM-4)

- **LLM-4** 관리자는 공급자별 모델 이름을 바꿀 수 있다(예: `claude-opus-5-5` → `claude-sonnet-5-5`).
  - 입력은 자유 텍스트 + 추천 목록(코드 시드). 저장 전에 연결 테스트로 유효성을 확인하길 권한다.
  - 모델을 바꿔도 대화 기록은 유지된다. 각 메시지에 당시 공급자·모델이 저장된다.

## 4. 생성 파라미터 (LLM-5)

| 설정 키 | 기본값 | 범위 | 설명 |
|---|---|---|---|
| `llm_temperature` | 0.2 | 0~1 | 낮을수록 일관된 답 |
| `llm_max_output_tokens` | 1500 | 200~8000 | 답변 최대 길이 |
| `llm_timeout_seconds` | 60 | 10~180 | 공급자 응답 대기 상한 |
| `llm_max_retries` | 1 | 0~3 | 과부하·일시 오류 재시도 |
| `llm_max_tool_rounds` | 3 | 1~5 | 한 질문에서 도구 호출을 주고받는 최대 횟수 |
| `llm_total_deadline_seconds` | 120 | 30~240 | 한 질문 전체(검색·도구 루프·재생성 포함) 처리 상한 |

- 공급자마다 지원 범위가 다르면 어댑터가 범위 안으로 맞춘다.

## 5. 어댑터 구조

```
llm/
  providers/base.py        ChatProvider 인터페이스 — chat(messages, tools, params) -> ChatResult
  providers/anthropic.py   Claude
  providers/openai.py      ChatGPT
  providers/gemini.py      Gemini
  providers/fake.py        테스트용 — 시나리오대로 응답·도구 호출을 재생
  registry.py              활성 공급자 + 복호화한 키 + 설정으로 provider 인스턴스 생성
```

- 공급자 SDK 는 공식 SDK 를 쓴다(`anthropic`, `openai`, `google-genai`). 공급자별 차이(메시지 형식, 시스템 프롬프트 위치,
  도구 호출 형식, 오류 타입)는 **어댑터 안에서만** 다룬다. 나머지 코드는 공통 타입(`ChatMessage`, `ToolSpec`, `ToolCall`, `ChatResult`)만 안다.
- `ChatResult` 는 본문, 도구 호출 목록, 입력·출력 토큰 수, 종료 사유, 공급자·모델을 담는다.

## 6. 도구 호출 (LLM-6)

- **LLM-6** 계산기를 LLM 도구로 노출한다. 도구 정의는 JSON Schema 로 한 번 쓰고 어댑터가 공급자 형식으로 바꾼다.

  | 도구 | 계산 | 정의 |
  |---|---|---|
  | `list_gt_models` | 선택 가능한 GT 모델 이름 목록 | `06` §2 |
  | `calculate_fouling_loss` | 현재 상태·예상 손실·회수 효과 | `05` §3 |
  | `compare_cleaning_methods` | 공법별 비용·순편익 비교 | `05` §4 |
  | `check_pinch_approach` | 핀치·어프로치 점검 | `05` §5 |

- **도구 결과에는 입력과 결과만 담는다.** 계수·식·참조표의 한계값 원본은 넣지 않는다(`05` CALC-8).
  운전 상태 판정은 "경보 한계 대비 92%"처럼 결과로만 준다.
- 도구 루프: LLM 응답에 도구 호출이 있으면 실행 → 결과를 붙여 다시 호출. `llm_max_tool_rounds` 를 넘으면 중단하고 그때까지의 결과로 답한다.
- 도구 실행 오류(입력 검증 실패 등)는 오류 내용을 도구 결과로 돌려줘 LLM 이 사용자에게 되묻게 한다.

## 7. 오류 분류 (LLM-7)

- **LLM-7** 어댑터는 공급자 오류를 공통 코드로 바꾼다.

  | 코드 | 원인 | 재시도 | HTTP |
  |---|---|---|---|
  | `LLM_NOT_CONFIGURED` | 키 없음 | – | 409 |
  | `LLM_AUTH_FAILED` | 키 무효·권한 없음 | ✗ | 502 |
  | `LLM_RATE_LIMITED` | 한도·과부하 | ✔ | 503 |
  | `LLM_TIMEOUT` | 시간 초과 | ✔ | 504 |
  | `LLM_UNAVAILABLE` | 네트워크·공급자 장애 | ✔ | 503 |
  | `LLM_BAD_RESPONSE` | 응답 해석 실패·모델 없음 | ✗ | 502 |

- 사용자 안내 문구는 `02` §8. 오류 시각·코드는 관리자 LLM 설정 화면의 "마지막 오류"에 표시한다.

## 8. 호출 방식 (LLM-8)

- **LLM-8** 질의응답은 **동기 HTTP 요청**으로 처리한다(202 + job 을 쓰지 않는다). 대화형 응답에 폴링은 맞지 않는다.
  - 한 질문 전체를 `llm_total_deadline_seconds`(기본 120초) 안에 끝낸다. 넘으면 `LLM_TIMEOUT` 으로 실패 처리한다.
  - Gunicorn `timeout` 은 이 값의 최댓값(240초)보다 크게 둔다(`13-nonfunctional.md` §6).
  - 스트리밍은 1차 범위 밖이다(`changes-2026-10.md` §3).

## 9. 사용량 (LLM-9)

- **LLM-9** 질문마다 공급자, 모델, 입력·출력 토큰, 소요 시간, 결과(성공/오류 코드)를 기록하고, 관리자 화면에 일·사용자별 합계를 보여 준다.
- 요금 계산은 하지 않는다(공급자·모델별 단가가 바뀌므로). 토큰 수만 보여 준다.

## 10. 수용 기준 (AC)

- [ ] AC-04-1 공급자 3종 각각에 대해 가짜 서버(또는 SDK 모킹)로 질의 → 도구 호출 → 최종 답변 흐름이 같은 공통 결과 타입으로 나온다.
- [ ] AC-04-2 API 키는 DB 에 암호문으로 저장되고(평문 검색 불가), 어떤 GET 응답에도 평문이 없다.
- [ ] AC-04-3 `FIELD_ENCRYPTION_KEY` 가 없으면 `prod` 설정으로 기동되지 않는다.
- [ ] AC-04-4 공급자를 OPENAI 로 바꿨다 ANTHROPIC 으로 돌아오면 ANTHROPIC 키가 그대로 있다.
- [ ] AC-04-5 기본 설정으로 시작하면 활성 공급자는 ANTHROPIC, 모델은 `claude-opus-5-5` 다. 모델을 `claude-sonnet-5-5` 로 바꾸면 다음 질문부터 그 모델로 호출된다.
- [ ] AC-04-6 잘못된 키로 연결 테스트를 하면 `LLM_AUTH_FAILED` 와 안내가 보이고 앱은 계속 동작한다.
- [ ] AC-04-7 도구 결과 JSON 에 계수·한계값 원본 필드가 없다(스키마 테스트).
- [ ] AC-04-8 도구 호출이 `llm_max_tool_rounds` 를 넘으면 중단되고 무한 루프가 없다.
