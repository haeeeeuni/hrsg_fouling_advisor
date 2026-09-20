# HRSG Fouling Advisor

복합화력 발전소 **HRSG(배열회수보일러) 가스측 오염도**를 운전 데이터에서 산출해,
**세정 시점(D-day)** 과 **세정 편익(원)** 을 제시하는 사내 웹앱.

세정 시점을 담당자의 경험과 고정 정비 주기로 정하면 너무 이른 세정(불필요한 정지 손실)과
너무 늦은 세정(누적 출력 손실) 사이를 오가게 된다. 이 앱은 그 판단을 데이터 기반으로 바꾼다.

```
운전 데이터 CSV  →  오염도 지수(FI 0~100)  →  임계치 도달 D-day  →  세정 순편익(원)  →  PDF/엑셀 리포트
```

---

## 핵심 아이디어

오염이 진행되면 두 가지 신호가 나타난다.

| 경로 | 관측값 | 결과 |
|------|--------|------|
| 가스측 차압 상승 | `hrsg_gas_dp_kpa` ↑ | GT 배압 상승 → **GT 출력 감소** |
| 전열면 열전달 저하 | `stack_temp_c` ↑ | 배열회수량 감소 → **ST 출력 감소** |

문제는 **차압과 스택온도가 오염 없이도 부하·외기온에 따라 크게 변한다**는 점이다.
그래서 원시 차압을 그대로 보면 오염과의 상관이 거의 없다(샘플 데이터 기준 0.165).

해결책은 **기대값 모델**이다. "세정 직후 = 오염 없음" 구간으로만 학습한 모델이
현재 운전 조건에서의 기대 차압·기대 스택온도를 예측하고, **잔차(실측 − 기대)** 를 오염 신호로 쓴다.
같은 샘플에서 운전 조건을 보정한 지표는 오염도와 상관 0.997을 보인다.

---

## 분석 파이프라인

`backend/analysis/pipeline.py` 가 `analysis/services/*.py` 의 순수 함수를 순서대로 호출한다.

```
Measurement (원본, 불변)
  ↓ cleaning + segmentation   결측·이상치 정제 → 구간 분류 → STEADY 구간만 유효
  ↓ clustering                부하대 × 계절 군집 (예: L3-SU) — 같은 조건끼리만 비교
  ↓ expected_model            청정 기준 기간으로만 학습한 차압·스택온도 기대값 모델
  ↓ fouling_index             잔차 → 평활 → 정규화 → 가중합 → FI (0~100)
  ↓ trend                     FI 회귀(LINEAR/ROBUST/EXPONENTIAL) → D-day + 95% 예측구간
  ↓ benefit                   Δ차압·Δ스택온도 → MW 손실 → 원/일 → 순편익·회수기간·권고 시점
  → AnalysisRun + FoulingIndexPoint + TrendForecast + BenefitResult
```

기동·정지·부하 급변·덕트버너 가동 구간은 분석에서 빠지지만 **원본은 지우지 않고 플래그로만 표시**한다.

---

## 주요 기능

**일반 사용자**
- 호기별 운전 데이터 CSV 업로드 — 한글 헤더·CP949 인코딩 자동 인식, 검증과 적재 분리
- 분석 실행 → 대시보드에서 FI 추이·등급·D-day·예상 편익 확인
- 정비 이력에서 세정 후보 자동 추출(승인 전까지는 이력으로 등록되지 않음)
- 세정 전후 비교(공통 군집에서만, p-value 포함)
- 한글 깨짐 없는 PDF·엑셀 리포트 다운로드

**관리자**
- 임계치·등급 경계·가중치·편익 계수 등 **84개 설정값**을 화면에서 변경 (호기별 오버라이드 지원)
- 사용자·호기·컬럼 매핑·세정 이력·오염 키워드 사전 관리
- 모델 재학습 — 신·구 지표를 비교해 **승인해야 활성화**된다
- 분석 실행 이력(설정 스냅샷 전체)·감사 로그
- 자동 재계산, 예측 정확도 백테스트, 호기 간 세정 우선순위 비교

---

## 시작하기

### 요구 사항
Docker · Python 3.11+ · Node 18+

### 1. 인프라

```bash
docker compose up -d db redis
```

PostgreSQL 16 + Redis 7이 올라온다. **SQLite는 운영·로컬·테스트 전부 금지**다(`AGENTS.md` §2).

### 2. 백엔드

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env           # 최초 1회

python manage.py migrate
python manage.py seed_defaults # 기본 관리자 + 설정값 + 키워드 시드 (멱등)
python manage.py runserver
```

별도 터미널에서 워커를 띄운다. 업로드 검증·적재·분석·재학습·리포트가 전부 여기서 돈다.

```bash
celery -A config worker -l info
```

### 3. 프론트엔드

```bash
cd frontend
npm install
npm run dev                    # http://localhost:5173
```

### 4. 로그인

**성명 + 사번 + 비밀번호** 3요소로 로그인한다.

| 성명 | 사번 | 비밀번호 |
|------|------|----------|
| 관리자 | `ADM01` | `qwer` |

이 계정은 **관리자 역할 사용자가 하나도 없을 때만** 생성되며, 로그인 후 비밀번호 변경 배너가 뜬다.

### 5. 샘플 데이터로 한 바퀴 돌려보기

실제 데이터 없이 전 기능을 확인할 수 있다.

```bash
cd backend
python scripts/generate_sample_data.py --unit-code U1 --months 24 --cleanings 3 --seed 42 \
  --out sample_unit1.csv \
  --maintenance-out sample_unit1_maintenance.csv \
  --truth-out sample_unit1_truth.csv \
  --korean-headers
```

| 옵션 | 용도 |
|------|------|
| `--korean-headers` | 한글 컬럼명으로 출력 — 컬럼 매핑 검증용 |
| `--messy` | 결측·이상치·중복·형식 오류 주입 — 업로드 검증 테스트용 |
| `--truth-out` | 정답 오염도 시계열 — 산출 FI와의 상관계수로 정확도 검증 (기준 ≥ 0.9) |

같은 `--seed` 는 같은 파일을 만든다. 호기 등록 → 컬럼 매핑 → 업로드 → 분석 → 리포트까지
`specs/17` §6의 9단계 시나리오가 `analysis/tests/test_integration_scenario.py` 로 고정되어 있다.

---

## 테스트

```bash
cd backend
pytest                                             # 전체 (PostgreSQL 필요)
pytest -m "not django_db"                          # DB 없이 돌릴 수 있는 순수 함수 테스트만
pytest --cov=analysis/services                     # analysis/services 커버리지 80% 이상이 기준
pytest analysis/tests/test_backtest_no_leakage.py  # 백테스트 미래 정보 누설 차단
pytest analysis/tests/test_integration_scenario.py # 9단계 통합 시나리오

cd ../frontend
npm run test                                       # Vitest — 포맷터·스토어·폴링
```

분석 서비스는 합성 데이터로 **성질 기반 검증**을 한다: 오염 없음 → FI ≈ 0 /
잔차 선형 증가 → FI 단조 증가 / 세정 직후 → FI 급락 / FI가 0~100을 벗어나지 않음.

린트·포맷은 `black`(line-length 100) · `isort` · `ruff`를 쓴다.

```bash
cd backend && black . && isort . && ruff check .
```

---

## 구조

```
backend/
  config/       Django settings(base/dev/prod), urls, celery
  accounts/     User(employee_no 로그인), 권한, 로그인 이력
  units/        호기, 컬럼 매핑, 설정값(Setting / UnitSetting)
  ingestion/    업로드 검증·적재, Measurement
  analysis/     분석 도메인 — models / services / pipeline / views
  maintenance/  정비 이력, 세정 이력, 오염 키워드 사전
  reports/      PDF·엑셀 생성기, 나눔고딕 폰트 동봉
  common/       에러 포맷, job 추상화, 감사 로그
  scripts/      샘플 데이터 생성기
frontend/src/
  api/          axios 인스턴스 + 엔드포인트별 모듈
  stores/       Pinia (auth / units / analysis / settings)
  views/        사용자 화면 9종 + admin/ 관리자 콘솔 12종
  components/   charts / dashboard / admin / common
  composables/  useJobPolling, useToast
```

### 기술 스택

| 레이어 | 사용 기술 |
|--------|-----------|
| Frontend | Vue 3 (`<script setup>`), Vite, Vue Router, Pinia, Bootstrap 5, Chart.js |
| Backend | Python 3.11+, Django 5, Django REST Framework |
| 분석 | pandas, numpy, scikit-learn, scipy |
| 리포트 | ReportLab(PDF), openpyxl(엑셀), matplotlib |
| 비동기 | Celery + Redis |
| DB | PostgreSQL 16 |

---

## 설계상 꼭 알아야 할 것

몇 가지는 모르면 코드를 잘못 읽게 된다.

- **설정값은 전부 DB에 있다.** 임계치·가중치·편익 계수 어느 것도 코드에 상수로 두지 않는다.
  조회 우선순위는 `UnitSetting`(호기) → `Setting`(전역) → 코드 시드 기본값.
  `analysis/tests/test_no_hardcoded_settings.py` 가 하드코딩을 상시 검사한다.
- **재현성이 보장된다.** `AnalysisRun` 하나만 보고 결과를 재현할 수 있도록
  설정 스냅샷·모델 버전·군집 정의·매핑 버전을 모두 저장한다. 난수는 `RANDOM_SEED` 고정.
- **설정을 바꿔도 과거 분석 결과는 변하지 않는다.** 다음 분석부터 적용된다.
- **분석 코드는 원본 CSV 컬럼명을 모른다.** 호기별 `ColumnMapping`이 표준 항목명으로 바꾼 뒤에만 진입한다.
- **타깃 누설 방지.** 스택온도 모델에 스택온도 파생값을 넣지 않는 것은 물론,
  `delta_t`(GT배기온도 − 스택온도)도 차압 모델에서 기본 비활성이다 — 스택온도 자체가 오염 지표라
  대리 누설이 되어 FI를 과소평가한다.
- **백테스트의 컷오프는 파이프라인 전체를 관통한다.** 데이터 조회 상한, 청정 기준 기간 후보,
  세정 이력 기반 추세 절단까지 모두 잘린다. 한 곳만 빠뜨려도 미래를 엿본 결과가 나오는데,
  그래도 그럴듯한 숫자가 나오기 때문에 전용 누설 테스트로 지점마다 고정한다.
- **오래 걸리는 작업은 `202 + job_id` 패턴**이다. `GET /api/jobs/{job_id}/` 로 진행률을 폴링한다.

---

## 문서

| 문서 | 내용 |
|------|------|
| `PROJECT.md` | 프로젝트 개요·아키텍처·용어집 — 단일 진실 공급원 |
| `AGENTS.md` | 코딩 규칙, 스택 고정, 레이어 책임, 커밋 규칙 |
| `CLAUDE.md` | 여러 명세를 읽어야 파악되는 전체 그림과 비자명한 결합들 |
| `specs/00~19` | 기능별 상세 명세. 각 문서 끝의 **수용 기준(AC)** 이 사실상 테스트 명세다 |

기능 하나를 건드릴 때는 최소한 셋을 읽는다:
해당 `specs/NN-*.md` → `specs/14-data-model.md` → `specs/15-api.md`.

---

## 진행 상황

`PROJECT.md` §6의 마일스톤 기준으로 **M1~M7 구현 완료**, 현재 M8(안정화) 단계다.

| 단계 | 내용 | 상태 |
|------|------|------|
| M1 | 기반 구축 — 인증, 설정값, SPA 스캐폴드 | 완료 |
| M2 | 데이터 파이프라인 — 호기·매핑·업로드·적재 | 완료 |
| M3 | 분석 엔진 — 정제·군집·기대값 모델·FI | 완료 |
| M4 | 의사결정 지원 — 추세·D-day·편익·대시보드 | 완료 |
| M5 | 이력 및 리포트 — 키워드 추출·전후 비교·PDF/엑셀 | 완료 |
| M6 | 관리자 콘솔 — 설정 화면·모델 관리·감사 로그 | 완료 |
| M7 | 옵션 기능 — 자동 재계산·백테스트·호기 간 비교 | 완료 |
| M8 | 안정화 — 성능 측정, 전체 테스트 수행 | 진행 중 |

---

## 범위 밖

DCS/PI 실시간 연계(수집은 CSV 업로드 기반), 세정 작업 자체의 제어·자동화,
가스터빈 압축기 오염 진단, 모바일 전용 앱, 다국어 지원(한국어 UI 단일).
