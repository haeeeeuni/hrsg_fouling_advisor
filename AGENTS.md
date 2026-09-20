# AGENTS.md — 코딩 에이전트 작업 지침

이 저장소에서 코드를 작성·수정하는 모든 AI 에이전트와 개발자는 이 문서의 규칙을 따른다.
프로젝트 개요는 `PROJECT.md`, 상세 요구사항은 `specs/`에 있다.

---

## 1. 최우선 원칙

1. **명세 우선(Spec-first).** 코드를 쓰기 전에 해당 기능의 `specs/*.md`를 읽는다. 명세와 코드가 충돌하면 명세가 우선이며, 명세가 틀렸다고 판단되면 코드를 고치기 전에 명세를 먼저 수정하고 근거를 남긴다.
2. **설정값은 코드에 하드코딩하지 않는다.** 임계치, 등급 경계, 가중치, 편익 계수, 필터 임계값 등 모든 튜닝 가능한 값은 DB(`Setting` 계열 모델)에 저장하고 관리자 화면에서 변경 가능해야 한다. 코드에는 **초기 시드값(seed/default)** 만 둔다.
3. **재현성.** 모든 분석 결과는 실행자, 실행 일시, 데이터 기간, 적용 설정값 스냅샷, 모델 버전을 함께 저장한다. 같은 입력 + 같은 설정 = 같은 결과여야 한다(난수는 `random_state` 고정).
4. **한국어 우선.** UI 문구, 사용자 대상 에러 메시지, 리포트는 한국어로 작성한다. 코드 식별자·주석은 영어, 도메인 용어 주석은 한국어 병기를 허용한다.
5. **추측 금지.** 요구사항이 모호하면 임의로 확장하지 말고, 명세에 `TODO(질문):` 로 남기고 가장 단순한 해석으로 구현한다.

---

## 2. 기술 스택 고정

변경하려면 반드시 사전 합의가 필요하다.

| 레이어 | 고정 스택 |
|--------|-----------|
| Frontend | Vue 3 (Composition API, `<script setup>`), Vite, Vue Router, Pinia, Bootstrap 5, 순수 CSS3 |
| Backend | Python 3.11+, Django 5.x, Django REST Framework |
| ORM | Django ORM (raw SQL은 성능상 불가피할 때만, 주석으로 사유 명시) |
| 분석 | pandas, numpy, scikit-learn, scipy |
| 리포트 | openpyxl(엑셀), ReportLab 또는 WeasyPrint(PDF) |
| DB | PostgreSQL |

- **금지:** TypeScript 전환, Options API 혼용, jQuery, Bootstrap 이외의 UI 프레임워크, Django Template 기반 화면(관리자 `/admin/` 제외), SQLite를 운영 DB로 사용.
- **허용:** 테스트/로컬 개발 편의를 위한 SQLite는 금지. 로컬도 PostgreSQL(Docker) 사용.

---

## 3. 디렉터리 및 레이어 규칙

```
backend/
  config/         Django settings, urls, wsgi
  accounts/       User(AbstractUser 확장), 인증
  units/          Unit(호기), ColumnMapping, Setting
  ingestion/      업로드 파일, 검증, 원본 적재
  analysis/       분석 도메인 (models / services / serializers / views)
  maintenance/    정비이력, 세정이력, 키워드 사전
  reports/        PDF/엑셀 생성기, fonts/
  common/         공통 유틸, 예외, 응답 포맷
  scripts/        운영/개발 스크립트
frontend/src/
  api/            axios 인스턴스 + 엔드포인트별 모듈
  stores/         Pinia 스토어
  router/         라우트 정의 + 인증 가드
  views/          라우트 단위 페이지
  components/     재사용 컴포넌트
  composables/    재사용 로직
```

### 레이어 책임
- **View(DRF)**: HTTP 입출력, 권한 확인, 직렬화. **분석 로직을 두지 않는다.**
- **Serializer**: 입력 검증, 표현 변환.
- **Service (`analysis/services/*.py`)**: 순수 함수 중심의 분석 로직. Django 모델을 import 하지 않고 **DataFrame / dataclass / dict 를 입출력**으로 받는다. → 단위 테스트가 쉽고 재사용 가능해야 한다.
- **Model**: 데이터 정의와 단순 파생 속성만. 무거운 계산 금지.
- **Task/Orchestrator (`analysis/pipeline.py`)**: 서비스들을 순서대로 호출하고 결과를 DB에 저장하는 얇은 조립층.

---

## 4. 코딩 컨벤션

### Python
- 포맷터 `black` (line-length 100), import 정렬 `isort`, 린트 `ruff`.
- 타입 힌트를 공개 함수에 필수로 작성한다.
- 함수는 한 가지 일만 하고, 60줄을 넘으면 분리를 검토한다.
- 예외는 `common/exceptions.py`의 도메인 예외를 사용하고, DRF 핸들러가 일관된 JSON으로 변환한다.
- 시간은 **항상 timezone-aware (Asia/Seoul)** 로 다룬다. DB 저장은 UTC, 표시·집계는 KST.
- pandas: `SettingWithCopyWarning`을 유발하는 체이닝 대입 금지, `.copy()` 명시.
- 난수 사용 시 `random_state=RANDOM_SEED`(공통 상수)를 반드시 전달.

### Vue / JS
- 컴포넌트 파일명 `PascalCase.vue`, 뷰(페이지)는 `views/XxxView.vue`.
- `<script setup>` + Composition API만 사용.
- API 호출은 컴포넌트에서 직접 axios를 쓰지 않고 `src/api/*.js` 모듈을 경유한다.
- 전역 상태는 Pinia(`auth`, `unit`, `analysis`, `settings`)로 한정. 컴포넌트 지역 상태를 기본으로 한다.
- 스타일은 Bootstrap 5 유틸리티 클래스를 우선 사용하고, 부득이한 경우만 `<style scoped>`.
- 숫자 표기는 공통 포맷터(`utils/format.js`)를 사용한다: 금액 `#,##0 원`, 지수 소수점 1자리, 온도 `℃`, 차압 `kPa`.

### 네이밍
| 대상 | 규칙 | 예 |
|------|------|-----|
| Python 모듈/함수/변수 | snake_case | `compute_fouling_index` |
| Django 모델 | PascalCase 단수 | `AnalysisRun` |
| DRF 엔드포인트 | 복수 kebab/snake 없는 소문자 | `/api/analysis-runs/` |
| JSON 필드 | snake_case (백엔드와 동일) | `fouling_index` |
| Vue 컴포넌트 | PascalCase | `FoulingTrendChart.vue` |
| 상수 | UPPER_SNAKE | `DEFAULT_THRESHOLD` |

---

## 5. 데이터·분석 규칙

1. **표준 항목명 고정.** 파일의 원본 컬럼명은 호기별 `ColumnMapping`을 통해 표준 항목(`timestamp`, `gt_power_mw`, `ambient_temp_c`, `gt_exhaust_temp_c`, `exhaust_flow`, `hrsg_gas_dp_kpa`, `stack_temp_c`, `duct_burner_on`, …)으로 변환한 뒤에만 분석 코드에 들어간다. 분석 코드는 원본 컬럼명을 절대 알지 못한다.
2. **단위 명시.** 모든 수치 필드명에 단위 접미사를 붙인다(`_mw`, `_c`, `_kpa`, `_kgps`, `_pct`).
3. **제외 구간.** 기동/정지/부하 급변/덕트버너 가동 구간은 분석에서 제외하되, **원본은 삭제하지 않고 플래그로 표시**한다(사유 추적 가능해야 함).
4. **결측/이상치 처리 이력**을 요약 통계로 남기고 UI에 표시한다(총 행수, 제외 행수, 제외 사유별 건수).
5. **모델 버전.** 기대값 모델을 학습할 때마다 `ModelVersion` 레코드를 만들고, 학습 기간·피처·하이퍼파라미터·MAE·R²·아티팩트 경로를 저장한다. 분석 결과는 어떤 모델 버전을 썼는지 반드시 참조한다.
6. **FI는 0~100으로 clip** 한다. 산출 중간값(정규화 전 잔차)도 함께 저장해 추적 가능해야 한다.
7. **비교는 같은 조건끼리.** 세정 전후 비교, 호기 간 비교는 반드시 같은 부하대/계절 군집 내에서 수행한다.

---

## 6. API 규칙

- 베이스 경로 `/api/`, 버전 없는 단일 버전으로 시작.
- 인증: 세션 또는 JWT 중 하나로 통일(`specs/15-api.md` 결정 사항 준수). 모든 엔드포인트는 인증 필수(로그인 제외).
- 성공 응답은 리소스 JSON을 그대로, 목록은 DRF 페이지네이션 래퍼(`count`, `next`, `previous`, `results`).
- 에러 응답 포맷 고정:
  ```json
  { "error": { "code": "VALIDATION_ERROR", "message": "필수 컬럼이 없습니다.", "details": {"missing_columns": ["stack_temp_c"]} } }
  ```
- 오래 걸리는 작업(분석 실행, 모델 재학습)은 즉시 `202` + `job_id`를 반환하고 상태 폴링 엔드포인트를 제공한다.
- 파괴적 작업(삭제)은 `DELETE`만 사용하고, 관리자 권한을 서버에서 재확인한다(프론트 가드만 믿지 않는다).

---

## 7. 보안 규칙

- 비밀번호는 Django 기본 해셔(PBKDF2) 사용. 평문 저장·로그 출력 금지.
- 기본 관리자 계정(`관리자 / ADM01 / qwer`)은 **최초 기동 시 계정이 하나도 없을 때만** 생성하고, 로그인 후 비밀번호 변경을 유도하는 배너를 표시한다.
- 비밀번호, 사번, 파일 원본 경로를 로그에 남기지 않는다.
- 업로드 파일은 확장자·MIME·크기·행수 상한을 검증한다. CSV 수식 인젝션(`=`, `+`, `-`, `@`로 시작하는 셀) 방지 처리.
- `SECRET_KEY`, DB 비밀번호 등은 환경변수(`.env`)로 관리하고 저장소에 커밋하지 않는다.
- 관리자 전용 API에는 `IsAdminRole` 권한 클래스를 명시적으로 지정한다(기본 권한에 의존 금지).

---

## 8. 테스트 규칙

- 백엔드: `pytest` + `pytest-django`. 최소 커버리지 기준은 `analysis/services/` **80% 이상**.
- 분석 서비스는 합성 데이터로 **성질 기반 검증**을 한다.
  - 오염이 없는 데이터 → FI ≈ 0
  - 잔차가 선형 증가 → FI 단조 증가
  - 세정 이벤트 후 → FI 급락
- API는 권한 테스트(비로그인 401, 일반 사용자의 관리자 API 403)를 반드시 포함한다.
- 프론트엔드: Vitest로 포맷터·계산 유틸·스토어 단위 테스트.
- `scripts/generate_sample_data.py`로 만든 데이터가 **업로드 → 분석 → 리포트**까지 통과하는 통합 테스트를 1개 이상 유지한다.

---

## 9. 작업 절차 (에이전트용 체크리스트)

기능 하나를 구현할 때:

1. `PROJECT.md`와 해당 `specs/*.md`를 읽는다.
2. 영향 범위를 파악한다(모델 변경 여부 → 마이그레이션 필요 여부).
3. 백엔드: 모델 → 마이그레이션 → 서비스 → 시리얼라이저 → 뷰 → URL → 테스트 순서.
4. 프론트엔드: api 모듈 → 스토어 → 뷰/컴포넌트 → 라우트 → 테스트 순서.
5. 설정값이 생겼다면 `Setting` 시드와 관리자 화면 항목을 함께 추가한다.
6. 테스트 실행 후 결과를 그대로 보고한다(실패는 숨기지 않는다).
7. 명세에 없는 동작을 추가했다면 해당 `specs/*.md`를 갱신한다.

### 금지 행동
- 마이그레이션 파일을 손으로 지우고 다시 만들기(이미 적용된 경우)
- 테스트를 통과시키기 위해 단언(assert)을 약화시키기
- 명세에 없는 라이브러리 임의 추가
- 요구되지 않은 리팩터링으로 변경 범위를 넓히기
- 실패한 단계를 "완료"로 보고하기

---

## 10. 명령어 (구현 후 유효)

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_defaults          # 기본 관리자/설정 시드
python manage.py runserver
pytest

# 샘플 데이터 생성
python scripts/generate_sample_data.py --unit 1 --months 18 --cleanings 3 --out sample_unit1.csv

# Frontend
cd frontend
npm install
npm run dev
npm run build
npm run test
```

---

## 11. 커밋 규칙

- Conventional Commits: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`
- 제목은 한국어 또는 영어, 50자 이내. 본문에 변경 이유와 영향 범위.
- 하나의 커밋은 하나의 논리적 변경. 마이그레이션과 모델 변경은 같은 커밋에 둔다.
- 사용자가 요청하지 않은 커밋·푸시는 하지 않는다.
