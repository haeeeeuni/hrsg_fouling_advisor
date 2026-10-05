# 21. E2E 테스트 (Playwright + Chrome)

관련 요구사항: NFR(18 §6 브라우저 지원, §8 테스트 기준), FR-U 전반의 화면 수용 기준

---

## 1. 목적

단위 테스트(`pytest`, `vitest`)는 계층별로 따로 검증한다. 그래서 **화면 → API → Celery 워커 → DB** 로
이어지는 경로가 실제 브라우저에서 한 번에 동작하는지는 확인하지 못한다.
E2E 테스트는 이 빈틈을 메운다. 사용자가 하는 동작을 Chrome으로 그대로 재현하고,
각 명세의 화면 수용 기준(AC)을 자동으로 검증한다.

E2E가 **하지 않는 일**:
- 분석 수치의 정확도 검증 — `analysis/tests/`(성질 기반, AC-17-3 상관계수)가 맡는다.
- API 권한·검증 오류의 경우의 수 전수 검사 — DRF API 테스트가 맡는다.
- 포맷터·스토어 로직 — `frontend/tests/`(vitest)가 맡는다.

E2E는 "연결이 끊기지 않았는가"를 본다. 같은 검증을 아래 계층에서 할 수 있다면 아래 계층에서 한다.

## 2. 구성

```
playwright.config.ts          # 대상 URL, 브라우저, 프로젝트(setup → chrome), webServer
package.json                  # 루트 — @playwright/test 와 test:e2e 스크립트
tests/
  auth.setup.ts               # 관리자 로그인 1회 → playwright/.auth/admin.json 저장
  auth.spec.ts                # 로그인·리디렉션·로그아웃
  navigation.spec.ts          # 전 화면 순회 스모크, 사이드바, 호기 선택 유지
  dashboard.spec.ts           # KPI 4종, 도움말(?), FI 차트, 신호 진단, 등급 배지, 빈 화면
  resilience.spec.ts          # 세션 만료, 404, 서버 오류·연결 실패, 입력 실수
  analysis-run.spec.ts        # 중복 클릭, 진행 상태 복원, 동시 실행 409, 기간 KST   @mutates
  permissions.spec.ts         # 일반 사용자 권한     @mutates
  reports.spec.ts             # PDF·엑셀 내려받기, 세정 전후 비교   @mutates
  scenario.spec.ts            # 업로드 → 적재 → 분석 → 대시보드   @mutates
  upload-validation.spec.ts   # 컬럼 누락, 행 오류, 폐기, 비 CSV, 재업로드 확인   @mutates
  support/
    env.ts                    # 환경 변수와 기본값
    api.ts                    # 준비·정리용 API 헬퍼(세션 + CSRF, multipart, job 대기)
    ui.ts                     # 로그인 폼, 호기 선택, 업로드, KST 날짜 등 공용 조작
    sample-data.ts            # 시나리오용 CSV 생성(specs/17 스크립트) + 오류 사례 변형
    e2e-unit.ts               # E2E 호기 활성화·비활성화, 데이터 적재 보장
.github/workflows/playwright.yml   # CI — 전체 스택을 띄우고 E2E 실행
```

- `frontend/tests/` 는 vitest 단위 테스트다. **루트 `tests/` 가 E2E** 이며 두 곳을 섞지 않는다.
- 브라우저는 **설치된 Google Chrome**(`channel: 'chrome'`)이 기본이다. 사내 표준 브라우저와 같다(18 §6).
  Chrome이 없는 환경에서는 `E2E_BROWSER=chromium` 으로 Playwright 내장 Chromium을 쓴다.
- 뷰포트는 **최소 지원 해상도 1280×800** 으로 고정한다(18 §6). 가장 좁은 조건에서 깨지지 않으면 넓은 화면에서도 깨지지 않는다.
- 타임존 `Asia/Seoul`, 로케일 `ko-KR` 로 고정한다. 날짜 표기가 실행 환경에 따라 달라지지 않게 하기 위해서다.

## 3. 로컬 실행

### 3.1 최초 1회

```bash
npm install                                  # 루트 — @playwright/test
npx playwright install chrome                # Chrome 이 없을 때만. 있으면 생략
npm --prefix frontend install
```

### 3.2 서버 기동

E2E는 **실제 백엔드**를 상대로 돈다. Vite는 `webServer` 설정이 자동으로 띄운다.
이미 떠 있으면 그 서버를 재사용한다. Django와 Celery는 직접 띄운다.

```bash
# PostgreSQL · Redis (docker compose up -d db redis, 또는 Homebrew 서비스)
cd backend && source .venv/bin/activate
python manage.py migrate && python manage.py seed_defaults
python manage.py runserver 127.0.0.1:8000
celery -A config worker -l info --pool=solo      # 별도 터미널
```

> **macOS에서는 Celery에 `--pool=solo` 가 필요하다.** 기본 prefork 풀은 macOS에서
> `ValueError: not enough values to unpack (expected 3, got 0)` 로 태스크를 받자마자 죽는다.
> 이때 화면은 "검증 결과"를 끝내 표시하지 못하고 테스트는 타임아웃으로 실패한다. 실패 원인이 화면에 드러나지 않으니 워커 로그를 먼저 본다.

### 3.3 실행

```bash
npm run test:e2e                              # 전체 (헤드리스). npm run test:chrome 도 같다
npx playwright test tests/dashboard.spec.ts   # 파일 하나
npx playwright test -g "AC-16-2"              # 이름으로 고르기
npx playwright test --headed                  # 브라우저 창을 띄워서
npm run test:e2e:ui                           # UI 모드 — 단계별 재생, 셀렉터 탐색
npm run test:e2e:report                       # 마지막 HTML 리포트 열기
```

### 3.4 환경 변수

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `E2E_BASE_URL` | `http://localhost:5173` | 대상 서버. localhost 가 아니면 **원격 모드**(§6) |
| `E2E_BROWSER` | `chrome` | `chromium` 이면 Playwright 내장 브라우저 |
| `E2E_ADMIN_NAME` / `E2E_ADMIN_NO` / `E2E_ADMIN_PASSWORD` | `관리자` / `ADM01` / `qwer` | 관리자 계정. 기본값은 `seed_defaults` 초기값(01 §4) |
| `E2E_PYTHON` | `backend/.venv/bin/python` | 시나리오 CSV를 생성할 Python |

> Vite는 `localhost`(IPv6 `::1`)에만 바인딩한다. 기준 URL을 `127.0.0.1:5173` 으로 바꾸면 연결이 거부된다.

## 4. 테스트 작성 규칙

### 4.1 셀렉터

우선순위: **역할·레이블 → 텍스트 → CSS 클래스**. `data-testid` 는 쓰지 않는다.

```ts
page.getByLabel('사번')                                   // <label for> 가 있는 입력
page.getByRole('button', { name: '분석 실행' })           // 버튼·링크
page.getByRole('button', { name: '현재 오염도 지수 설명 열기' })  // aria-label
page.locator('.ui-stat-label', { hasText: '예상 회수 편익' })     // 의미 있는 역할이 없을 때만
```

역할·레이블로 찾을 수 없는 요소는 **접근성 결함일 가능성이 크다.** 이때는 테스트 쪽에서 우회하지 말고
화면 쪽에 `<label for>`·`aria-label` 을 붙인다. 테스트 ID를 쓰지 않는 이유다.

자주 걸리는 함정:
- `'분석 실행'` 은 사이드바 링크와 실행 버튼에 같이 있다. 역할(`button`/`link`)로 구분한다.
- `'검증'` 은 `'검증 결과'` 와 부분 일치한다. 버튼은 `exact: true` 로 찾는다.
- 업로드 이력 표에는 과거에 올린 같은 파일명이 남아 있다. 파일명으로 찾을 때는 범위를 좁힌다.
- `getByText(/^…/)` 정규식은 템플릿 들여쓰기 공백 때문에 맞지 않을 수 있다. 앵커(`^`)를 쓰지 않는다.

### 4.2 인증과 로그인 스로틀

로그인 API는 **IP 기준 분당 10회**로 제한된다(01 §3). E2E가 매번 로그인하면 금방 429를 받는다.

- `auth.setup.ts` 가 관리자 세션을 `playwright/.auth/admin.json` 에 저장한다. 모든 스펙은 이 세션으로 시작한다.
  저장된 세션이 아직 유효하면 setup은 다시 로그인하지 않는다.
- API로 준비 작업을 할 때는 `Api.asAdmin()` 을 쓴다. 저장된 세션을 재사용하므로 로그인 횟수를 쓰지 않는다.
  `Api.login(creds)` 는 관리자가 아닌 계정이 필요할 때만 쓴다.
- 로그인 흐름 자체를 검증하는 테스트(`auth.spec.ts`)만 세션 없이 시작한다.
  `test.use({ storageState: { cookies: [], origins: [] } })` 를 지정한다.

현재 전체 실행 1회의 로그인은 약 5회다. **새 테스트에서 폼 로그인을 늘리면 연속 실행이 429로 깨진다.**

### 4.3 준비는 API로, 검증은 화면으로

호기 등록·컬럼 매핑·테스트 사용자 생성처럼 **검증 대상이 아닌 준비 작업은 API로** 처리한다(`support/api.ts`).
화면은 사용자가 실제로 하는 동작에만 쓴다. 준비 작업까지 화면으로 하면 느려지고,
관리자 화면이 바뀔 때마다 무관한 테스트가 같이 깨진다.

API 헬퍼는 세션 쿠키와 CSRF를 다룬다. 변경 요청에는 `csrftoken` 쿠키 값을 `X-CSRFToken` 헤더로 싣고,
HTTPS 대상에 대비해 `Referer` 도 함께 보낸다(15 §1).

### 4.4 비동기 작업(202 + job_id) 기다리기

검증·적재·분석은 202를 받은 뒤 화면이 job을 폴링한다(15 §1). 테스트는 **폴링을 직접 하지 않고 화면의 결과를 기다린다.**

```ts
await page.getByRole('button', { name: '검증', exact: true }).click();
await expect(page.getByRole('heading', { name: '검증 결과' })).toBeVisible({ timeout: 60_000 });
```

`waitForTimeout` (고정 대기)은 금지한다. 분석처럼 오래 걸리는 테스트는 `test.slow()` 로 제한 시간을 늘린다.
성능 기준은 분석 60초다(18 §1).

### 4.5 브라우저 대화상자

이미 **적재한** 파일을 다시 업로드하면 화면이 `window.confirm` 으로 확인을 받는다(03 §4).
검증 후 폐기한 파일에는 뜨지 않는다.
**Playwright는 대화상자를 기본으로 닫는다.** 그래서 처리하지 않으면 "취소"를 누른 것과 같아진다.
이 흐름이 있는 테스트는 `page.on('dialog', (d) => d.accept())` 를 먼저 건다.

### 4.6 데이터를 바꾸는 테스트 — `@mutates`

DB에 쓰는 테스트는 describe 이름에 `@mutates` 태그를 붙이고, 아래 규칙을 지킨다.

1. **재실행해도 통과해야 한다.** 같은 코드(`E2E` 호기, `E2EUSER01`)를 재사용하고,
   시작할 때 직전 실행이 남긴 상태를 정리하거나 그대로 받아들인다.
   예: 두 번째 실행부터 업로드는 중복이라 **0행 적재가 정상**이다(AC-03-3).
2. **끝나면 다른 화면을 어지럽히지 않는다.** 테스트 사용자는 물리 삭제한다.
   데이터가 있는 호기는 삭제할 수 없으므로(02 §2) **비활성화**한다.
3. **원본 불변을 어기는 정리를 하지 않는다.** `Measurement` 를 지우는 정리 코드를 쓰지 않는다(시스템 불변식 1).

읽기 전용 테스트는 이미 있는 데이터에 기대되, 없으면 `test.skip` 으로 이유를 남긴다.
예: `dashboard.spec.ts` 는 **활성 호기 중** 성공한 분석이 있는 호기를 고르고, 없으면 건너뛴다.
비활성 호기는 내비바에서 고를 수 없으므로 후보에서 뺀다.

### 4.7 장애 주입 — `page.route`

서버를 실제로 망가뜨리지 않고 오류 경로를 확인할 때는 `page.route` 로 응답을 바꾼다.

```ts
await page.route('**/api/analysis-runs/**', (route) =>
  route.fulfill({ status: 500, contentType: 'application/json',
                  body: JSON.stringify({ error: { code: 'INTERNAL_ERROR', message: '…' } }) }));
await page.route('**/api/auth/login/', (route) => route.abort('connectionrefused'));
```

확인할 것은 세 가지다. ① 사용자가 **이유를 알 수 있는가**(오류를 "데이터 없음" 으로 보여주지 않는가),
② **회복할 수 있는가**(다시 시도, 다른 화면 이동), ③ 처리되지 않은 스크립트 오류(`pageerror`)가 없는가.
지연을 주입하면(`setTimeout` 후 `route.continue()`) "처리 중" 상태의 버튼 잠금도 관찰할 수 있다.

### 4.8 재현이 까다로운 상황

- **세션 만료**는 `context.clearCookies()` 로 흉내 낸다. 단, **진행 중인 요청이 끝난 뒤**(`waitForLoadState('networkidle')`)에 지워야 한다.
  응답의 `Set-Cookie` 가 세션 쿠키를 다시 심어, 만료가 재현되지 않은 채 테스트가 실패한다.
  저장된 관리자 세션 파일은 건드리지 않으므로 다른 테스트에 영향이 없다.
- **같은 세션의 다른 탭**은 `page.context().newPage()` 로 연다. 탭마다 `sessionStorage` 가 따로라서,
  진행 중 작업을 탭끼리 공유하지 않는 상황(동시 실행 409)을 만들 수 있다.
- **분석 진행 표시**는 `.progress-bar-animated` 로 찾는다. 대시보드에도 `.progress-bar` 가 여럿 있다.
  그래서 분석이 끝나 대시보드로 이동한 뒤에는 진행 표시가 "남아 있는" 것처럼 오인한다.
- **날짜 비교**는 `kstDate()` 를 쓴다. API 의 UTC 시각 문자열 앞 10자를 자르면 KST 00~09시가 전날이 된다.

### 4.9 명세 추적

테스트 이름 앞에 검증하는 AC ID를 붙인다(`'AC-16-2: …'`). `npx playwright test -g "AC-16"` 로
명세 단위 실행이 되고, 실패 리포트에서 바로 명세로 거슬러 올라갈 수 있다.

## 5. 현재 커버리지

전체 59개(setup 제외). 이 중 읽기 전용은 38개다.

| 파일 | 검증 내용 | AC |
|------|-----------|----|
| `auth.spec.ts` | 비로그인 접근 → 로그인 → 원래 경로 복귀 | AC-01-4, AC-16-1 |
| | 성명 불일치 시 로그인 실패 | AC-01-3 |
| | 로그아웃 후 보호 경로 차단 | — |
| `navigation.spec.ts` | 사용자 7개 · 관리자 12개 화면이 JS 오류·API 5xx 없이 열림 | 16 §3, 13 §3 |
| | 관리자 하위 화면에서 사이드바 활성 유지 | — (`014326c` 회귀) |
| | 호기 선택이 이동·새로고침 후 유지 | AC-16-3 |
| `dashboard.spec.ts` | KPI 4종 표시 | AC-11-1 |
| | 도움말(?) 클릭으로 열림, Esc·바깥 클릭으로 닫힘 | AC-16-6 |
| | FI 시계열 차트, 신호 진단 패널 | 11 §4, 07 §8 |
| | 경고 등급이면 빨간 "경고" 배지 | AC-11-3 |
| | 분석 없는 호기는 안내 + 분석 실행 버튼 | AC-11-4 |
| `resilience.spec.ts` | 세션 만료 시 다음 동작에서 로그인으로 | 16 §6 |
| | 없는 경로(일반·관리자 하위) → 404 → 대시보드 복귀 | — |
| | 비밀번호 확인 불일치는 서버에 보내지 않고 안내 | 01 §5 |
| | 결과 조회 500 → "결과 없음" 이 아니라 오류 + 다시 시도로 회복 | — (§9 회귀) |
| | 호기 전환 중 조회 실패 → 이전 호기 결과를 남기지 않음 | — (§9 회귀) |
| | 로그인 시 서버 연결 실패를 안내하고 재시도 가능 | — |
| `analysis-run.spec.ts` | 적재 기간·기본 분석 기간이 KST 날짜 | — (§9 회귀) |
| | 실행 버튼 연타에도 요청 1회 | 16 §6 |
| | 분석 중 다른 화면 이동·새로고침 후 진행 상태 복원 | AC-16-4 |
| | 진행 중인 호기 재실행 → "진행 중인 분석이 있습니다" (409) | 15 §1 |
| `permissions.spec.ts` | 일반 사용자에게 관리자 메뉴 없음, URL 직접 접근 차단 | AC-16-2 |
| | 일반 사용자도 업로드 화면 컬럼명 안내를 봄(링크 대신 요청 안내) | 03 §2.2 |
| | 일반 사용자의 관리자 API 호출 403, 매핑 수정 403 | AC-01-5 |
| `reports.spec.ts` | 대시보드 PDF·엑셀이 열 수 있는 파일(시그니처 `%PDF-`, `PK`) | 12 §2 |
| | 리포트 생성 중 다운로드 버튼 잠금 | 16 §6 |
| | 세정 전후 비교 생성 → 결과 표 또는 비교 불가 사유 → PDF | 10 §5 |
| `scenario.spec.ts` | CSV 업로드 → 검증 → 적재 → 이력 반영 | AC-03-5, AC-03-3(재실행) |
| | 분석 실행 → 대시보드 이동 → KPI·FI 범위(0~100) | AC-07-4(화면) |
| | 분석 기본 기간이 선택한 호기 기준으로 잡힘 | — (§9 회귀) |
| `upload-validation.spec.ts` | 업로드 전 호기가 찾는 컬럼명 표(필수·선택, 관리자 링크) | 03 §2.2 |
| | 필수 컬럼 누락 → 항목·원본 컬럼 표시, 적재 차단, 컬럼명 안내 유지 | AC-03-1 |
| | 타임스탬프 오류 행 제외 + 건수 표시, 적재 가능 | AC-03-2 |
| | 숫자 칸 문자열 → 경고 건수, 적재 가능 | 03 §4.2 |
| | 검증 결과 폐기 | 03 §2 |
| | CSV 가 아닌 파일 → 오류 안내, 화면 유지 | — |
| | 적재한 파일 재업로드 → 확인, 취소 시 이유 표시 | 03 §4 |

**다음 후보**: CP949 한글 헤더 파일(AC-03-4) · 관리자 설정 변경이 다음 분석부터 적용(AC-13-1, 설정 원복 필요) ·
마지막 관리자 비활성화 거부(AC-01-6) · 정비 이력 업로드와 세정 후보 승인 · 등급 상승 알림 배너.

## 6. 원격 모드 (배포본 스모크)

```bash
E2E_BASE_URL=https://hrsg-web.onrender.com E2E_ADMIN_PASSWORD='…' npm run test:e2e
```

`E2E_BASE_URL` 이 localhost가 아니면 config가 **`@mutates` 테스트를 자동으로 제외**하고 읽기 전용 38개만 돈다.
Vite도 띄우지 않는다. 배포 직후 화면이 모두 열리는지 확인하는 용도다.

- 공개 URL이므로 관리자 비밀번호는 명령줄 환경 변수로만 넘긴다. 파일에 적지 않는다.
- Render 무료 플랜은 유휴 후 첫 요청에 수십 초가 걸린다(콜드 스타트). 첫 실행이 타임아웃으로 실패하면 한 번 더 돌린다.

## 7. CI

`.github/workflows/playwright.yml` 이 `main` 푸시·PR마다 돈다.

1. 서비스 컨테이너로 PostgreSQL 16, Redis 7을 띄운다.
2. 백엔드를 설치하고 `migrate` → `seed_defaults` 를 실행한다. 관리자 초기 계정이 여기서 생긴다.
3. `runserver` 와 `celery --pool=solo` 를 백그라운드로 띄우고 `/api/health/ready/` 가 응답할 때까지 기다린다.
4. `npx playwright install --with-deps chrome` 후 `npx playwright test` 를 실행한다. Vite는 webServer가 띄운다.
5. 실패하면 Django·Celery 로그 끝 200줄을 출력하고, HTML 리포트를 아티팩트로 올린다(14일 보관).

CI의 DB는 매번 비어 있다. 그래서 **기존 데이터에 기대는 읽기 전용 테스트 15건은 CI에서 건너뛴다**(첫 실행 2026-10-05: 44 통과 · 15 건너뜀).
대시보드 KPI·도움말·등급 배지, 리포트 내려받기, 세정 전후 비교, 호기 선택 유지, 장애 주입 일부가 여기에 해당한다.
시나리오가 끝나면 E2E 호기를 비활성화하므로 같은 실행 안에서도 대상이 되지 않는다. 이 테스트들은 현재 로컬 실행으로만 검증된다.
CI에서도 돌리려면 시드 단계에서 분석까지 마친 데모 호기를 만들어야 한다(후속 과제).

**빈 DB를 전제로 테스트를 쓴다.** 호기가 없으면 API 를 부르지 않는 화면이 있다. 예를 들어 세션 만료 테스트가
정비 이력 화면으로 이동했더니 401 을 받을 기회가 없어 CI에서만 실패했다. 항상 API 를 부르는 화면(사용자 관리)을 쓴다.

## 8. 실패 진단

| 증상 | 먼저 볼 것 |
|------|-----------|
| "검증 결과"·분석 완료를 기다리다 타임아웃 | Celery 워커가 떠 있는가, macOS면 `--pool=solo` 인가(§3.2) |
| 로그인 직후 실패, 화면에 "요청이 너무 많습니다" | 로그인 스로틀. 1분 기다리거나 폼 로그인 횟수를 줄인다(§4.2) |
| 화면이 "서버에 연결할 수 없습니다" | Django가 `127.0.0.1:8000` 에 떠 있는가(Vite 프록시 대상) |
| `selectOption` 타임아웃 | 그 호기가 비활성이라 목록에 없다(§4.6) |
| 재실행에서만 업로드 실패, "같은 파일이 이미 적재되어 있습니다" | `dialog` 처리 누락(§4.5) |
| 세션 만료 테스트가 로그인으로 안 가고 빈 목록을 보여줌 | 쿠키를 진행 중 요청이 끝나기 전에 지웠다(§4.8) |
| 진행 표시가 끝나지 않는다며 타임아웃, 화면은 대시보드 | `.progress-bar` 가 대시보드 요소까지 잡았다(§4.8) |

실패한 테스트는 `test-results/` 에 스크린샷·영상·트레이스가 남는다.
`npx playwright show-trace <trace.zip>` 으로 단계마다 DOM·네트워크·콘솔을 다시 볼 수 있다.

## 9. E2E가 찾은 결함

| 일자 | 결함 | 조치 |
|------|------|------|
| 2026-10-05 | 분석 실행 화면이 서버의 UTC 시각 앞 10자를 날짜로 썼다. KST 00시에 시작하는 데이터의 적재 기간이 **하루 앞당겨 표시**됐고(2023-01-01 → 2022-12-31), KST 오전 9시 전에 끝나는 데이터는 기본 종료일이 전날로 잡혀 **마지막 날이 분석에서 빠졌다.** 요청은 KST 날짜로 보내므로 기준이 어긋나 있었다. | `applyDefaultRange` · `applyQuickRange` 가 dayjs 로 로컬(KST) 날짜를 만든다. `analysis-run.spec.ts` 가 적재 기간·기본 기간을 KST 로 확인한다. |
| 2026-10-05 | 대시보드가 결과 조회 실패(서버 오류)를 **"아직 분석 결과가 없습니다"** 로 표시했다. 장애를 데이터 부재로 오인해 불필요한 재분석으로 이어질 수 있다. 처리되지 않은 Promise 오류도 남았다. | 분석 스토어에 `error` 상태를 두고, 대시보드가 오류 안내와 "다시 시도" 를 보여준다. `resilience.spec.ts`, `analysis-store.spec.js` |
| 2026-10-05 | 호기를 바꿀 때 새 호기 조회가 실패하거나 이전 호기 응답이 늦게 도착하면, **이전 호기의 KPI 가 새 호기 이름 아래에 남았다.** | 스토어가 마지막 요청의 응답만 반영하고, 실패하면 이전 결과를 비운다. `resilience.spec.ts`, `analysis-store.spec.js` |
| 2026-10-05 | 업로드 화면에 직접 들어오면 호기 목록을 읽는 동안 **"업로드 가능한 호기가 없습니다"** 와 "남은 단계 보기" 가 잠깐 보였다. 테스트가 이 순간을 잡아 간헐적으로 건너뛰면서 드러났다. | 목록을 읽는 동안은 로딩 표시만 보인다. |
| 2026-10-05 | 분석 실행 화면에 진입한 직후 호기를 바꾸면, 진입 시 요청한 **이전 호기의 적재 기간 응답이 늦게 도착해** 새 호기의 기본 기간을 덮어썼다. 해당 기간에 데이터가 없어 분석이 "작업이 실패했습니다"로 끝났다. | `AnalysisRunView.applyDefaultRange` 가 마지막 요청의 응답만 반영한다. `scenario.spec.ts` 가 종료일이 선택한 호기의 적재 종료일인지 확인한다. |

## 10. 수용 기준 (AC)

- [x] AC-21-1: 로컬 스택(Django · Celery · Vite)에서 `npm run test:e2e` 가 설치된 Chrome으로 전 테스트를 통과한다.
- [x] AC-21-2: 같은 DB에 대해 연속으로 여러 번 실행해도 통과한다. 재실행 시 중복 업로드나 로그인 스로틀로 깨지지 않는다.
- [x] AC-21-3: `E2E_BASE_URL` 이 원격이면 `@mutates` 테스트가 실행 목록에서 빠진다(59개 → 38개).
- [x] AC-21-4: 데이터를 바꾸는 테스트가 끝난 뒤 테스트 사용자는 남지 않고, 테스트 호기는 비활성 상태다.
- [ ] AC-21-5: GitHub Actions에서 빈 DB로 전 테스트를 통과한다. 워크플로는 작성됐지만 아직 실행해 보지 않았다.
