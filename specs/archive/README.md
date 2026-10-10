# 보관 명세

**새 기능을 구현할 때 이 폴더를 정본으로 읽지 않는다.** 정본은 `specs/` 바로 아래 문서다.

## v1-fouling-advisor/ (2026-09-20 ~ 2026-10-10)

이전 앱 "HRSG Fouling Advisor"의 명세다. 운전 시계열 CSV로 오염도 지수, D-day, 세정 편익을 산출하는 앱이었다.
2026-10-10 요구사항이 바뀌어 "HRSG 레퍼런스 앱"(질의응답 · 계산기 · 데이터 요청 체크리스트)으로 전환했다.
변경 경위는 `specs/changes-2026-10.md` 에 있다.

보관하는 이유:
- 전환이 끝날 때까지 **저장소의 코드는 이 명세를 따른다**(`backend/analysis`, `units`, `ingestion`, `maintenance`, `reports`).
- 계산기의 임시 계산식은 `09-benefit-model.md` 의 편익 모델에서 가져왔다(`specs/05-calculator.md` §6).
- 인증·감사 로그·job 패턴·E2E 인프라처럼 새 앱이 재사용하는 부분의 설계 근거가 남아 있다.

`CLAUDE.md`, `AGENTS.md`, `README.md` 는 전환 직전 시점의 사본이고, `PROJECT.md` 는 원본을 옮긴 것이다.
