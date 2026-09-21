# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 현재 상태

**Phase 7(M7, 옵션 기능)까지 구현된 상태다.** 마일스톤은 `PROJECT.md` §6 (M0 명세 → M8 안정화).

- **있음:** `accounts`(인증 + 사용자 관리 + 로그인 이력), `units`(호기·매핑·설정 + 호기별 오버라이드),
  `ingestion`, `analysis`(분석 전 단계 + 모델 관리·재학습·청정 기준 기간 + **자동 재계산·백테스트·호기 간 비교**),
  `maintenance`, `reports`, `common`(에러 포맷·job 추상화·**감사 로그**), `seed_defaults`,
  `scripts/generate_sample_data.py`, Vue SPA(사용자 화면 7종 + 관리자 콘솔 12종).
- **배포:** `docker-compose.prod.yml` + `deploy/nginx/hrsg.conf` + `DEPLOY.md` (`specs/18` §7).
  헬스체크는 `/api/health/live/`(프로세스) 와 `/api/health/ready/`(DB 포함) 두 갈래다.
  `prod.py` 는 `SECRET_KEY` 가 플레이스홀더이거나 50자 미만이면 **기동을 거부한다.**
- **M8 완료.** Compose 스택 기동 검증(2026-09-21)과 `specs/18` §1 성능 측정을 마쳤다.
  실측: 105만 행 적재 155.5초(기준 300초), 분석 7.5초(기준 60초), PDF 4.4초, 엑셀 0.2초.
  **미구현 확인:** `specs/06` §120 이 요구하는 `joblib.dump` 모델 아티팩트 저장이 빠져 있다
  (`ModelVersion.artifact_path` 필드만 있고 쓰는 코드가 없다).

**AC-13-4(하드코딩 없음)는 `analysis/tests/test_no_hardcoded_settings.py` 가 상시 검사한다.**
로직 한가운데 매직 넘버는 금지, 이름 붙은 모듈 상수 폴백과 함수 기본 인자는 허용이다
(AGENTS.md §1.2 "코드에는 초기 시드값만 둔다").

`specs/17` §6의 9단계 통합 시나리오는 `analysis/tests/test_integration_scenario.py` 로 고정돼 있다.

로컬 개발에는 **Docker와 Node가 필요**하다(`docker-compose.yml`의 PostgreSQL + Redis, `frontend/`의 Vite).

**`AGENTS.md`가 코딩 규칙의 단일 진실 공급원이다.** 스택 고정, 레이어 책임, 네이밍, 커밋 규칙은 거기에 있으니 이 문서에서 반복하지 않는다.
이 문서는 "여러 명세를 읽어야 파악되는 전체 그림"만 담는다.

## 명세 읽는 순서

기능 하나를 건드릴 때 최소한 이 셋을 읽는다: 해당 기능 `specs/NN-*.md` → `specs/14-data-model.md`(모델) → `specs/15-api.md`(엔드포인트).
`specs/00-requirements-index.md` 의 추적 매트릭스(FR-U/FR-A/FR-D/TR/NFR ID)로 요구사항 ↔ 명세 문서를 역추적할 수 있고,
§6에 명세 간 의존 그래프가 있다. 각 명세 끝의 `수용 기준 (AC)` 체크리스트가 사실상 테스트 명세다.

## 도메인 한 줄 요약

HRSG(배열회수보일러) 가스측 오염도를 운전 데이터에서 산출해, **세정 시점(D-day)과 세정 편익(원)** 을 제시하는 사내 웹앱.
핵심 인과: 오염 → 가스측 차압↑(GT 배압↑ → GT 출력↓) + 스택온도↑(배열회수↓ → ST 출력↓).
도메인 용어집은 `PROJECT.md` §3.

## 분석 파이프라인 (시스템의 심장)

`analysis/pipeline.py` 가 아래 순서대로 `analysis/services/*.py` 의 순수 함수를 호출하고 결과를 DB에 적재한다.
각 단계의 규칙은 대응 명세에 있으며, **단계 간 계약(무엇을 입력받아 무엇을 내보내는지)** 은 이렇다:

```
Measurement (원본, 불변)
  ↓ cleaning.py + segmentation.py        specs/04  결측/이상치 정제 → segment_state 부여 → STEADY 구간만 유효
  ↓ clustering.py                        specs/05  cluster_key = "{load_band}-{season}" (예 L3-SU), 기본 RULE / 대안 KMEANS
  ↓ expected_model.py                    specs/06  청정 기준 기간으로만 학습한 MODEL_DP / MODEL_ST 로 기대값 예측
  ↓ fouling_index.py                     specs/07  잔차 = 실측 − 기대 → 평활 → 정규화 → w_dp·S_dp + w_st·S_st → clip(0,100)
  ↓ trend.py                             specs/08  FI_daily 회귀(LINEAR/ROBUST/EXPONENTIAL) → 임계치 도달 D-day + 신뢰구간
  ↓ benefit.py                           specs/09  Δdp·Δstack → MW 손실 → 원/일 → 순편익·회수기간·권고 세정 시점
  → AnalysisRun + CleanedPoint + FoulingIndexPoint + TrendForecast + BenefitResult
```

파이프라인을 이해할 때 꼭 알아야 할 비자명한 결합들:

- **청정 기준 기간(Clean Baseline)이 모든 것의 기준점이다.** 기대값 모델은 "세정 직후 = 오염 없음" 구간으로만 학습하고,
  그때의 잔차 통계 `σ_dp`/`σ_st`가 `ModelVersion`에 저장되어 **FI 정규화(SIGMA 방식)의 분모**가 된다.
  즉 `06` 의 학습 산출물이 `07` 의 입력이다. 기준 기간 결정 우선순위: 관리자 지정 → 세정 이력 기반 → 데이터 최초 30일(+경고).
- **세정 이벤트는 추세를 리셋한다.** `08` 의 추세 적합 구간은 반드시 최근 세정 이후로 절단한다(전후를 섞으면 안 됨).
- **군집은 공정한 비교를 위한 장치다.** FI 종합값은 군집별 FI의 표본 수 가중 평균이고, 세정 전후 비교·호기 간 비교는
  양쪽 모두 표본이 있는 **공통 군집**에서만 수행한다(`05` §3, `12` §2.2).
- **음의 잔차는 오염이 아니다** → 0으로 클리핑. FI는 항상 0~100.
- **타깃 누설 금지**: `MODEL_ST` 피처에 `stack_temp_c` 파생값을 넣지 않는다. `MODEL_DP` 도 dp 계열을 넣지 않는다(`06` §3.3).
  `delta_t`(= GT배기온도 − 스택온도)는 `MODEL_DP`에서도 **기본 비활성**이다 — 스택온도가 오염 지표라 대리 누설이 되어 FI를 과소평가한다.
- **이상치·고착 탐지는 운전 중 구간에만 적용한다.** 정지 구간의 0/일정값은 정상이며, 지우면 기동·정지 전환점이 사라져 구간 분류가 무너진다.
- **MAD 이상치 윈도는 3시간이다**(24시간 아님). 주야 부하 블록이 이봉분포를 만들어 긴 윈도에서는 야간 블록 전체가 오탐된다(`04` §5.2 정정 근거).
- **세정 후 잔류 오염은 "세정 시점"의 FI 기준이다**(분석 시점 FI 가 아니다). 혼동하면 늦게 세정할수록 유리해 보이는 왜곡이 생긴다(`benefit.gross_benefit_precise`).
- **권고 세정 시점은 3개 시나리오 표와 함께 읽는다.** 평가 기간이 고정이라 구조적 끝단 효과가 있다(`09` §4.7).
- **PDF 한글은 동봉 폰트를 파일 경로로 지정해야 한다.** family 이름만 쓰면 같은 이름의 시스템 폰트가 선택돼
  서버에서 한글이 네모가 된다 → 차트는 항상 `reports.pdf.fonts.font_properties()` 를 넘긴다.
  나눔고딕에 `℃`(U+2103)·`−`(U+2212) 글리프가 없어 PDF 출력 전 `pdf_safe()` 로 치환한다(엑셀은 불필요).
- **추출된 세정 후보는 승인 전까지 `CleaningEvent` 가 아니다**(오탐 방지). 세정 이력을 지워도 과거 분석 수치는 스냅샷이라 불변이다.
- **재학습한 모델은 비활성으로 저장된다.** 관리자가 신·구 지표를 비교하고 승인해야 활성화되며, 그 전까지 기존 활성 모델이 쓰인다(AC-06-5).
- **설정 변경은 다음 분석부터 적용된다.** 기존 결과는 `settings_snapshot` 을 보관하므로 바뀌지 않는다(AC-13-1).
- **관리자 변경은 전부 `AuditLog` 에 남는다**(사용자·호기·매핑·설정·세정이력·키워드·모델활성화·배치롤백). 비밀번호는 스냅샷에서 제외한다.
- **백테스트의 컷오프는 파이프라인 전체를 관통한다.** `PipelineContext.cutoff` 가 걸리면 (1) 데이터 조회 상한,
  (2) 청정 기준 기간 후보, (3) 세정 이력 기반 추세 절단 기준 세 지점이 모두 그 시각에서 잘린다.
  **한 곳만 빠뜨려도 미래를 엿본 결과가 나오고, 그래도 예외 없이 그럴듯한 숫자가 나온다**(AC-19-4).
  또한 컷오프 실행은 `ClusterDefinition`·`ModelVersion` 을 저장하지 않는다 — 과거 시점 재현이 운영 모델을 덮으면 안 된다.
- **자동 재계산은 기준 분석의 `settings_snapshot` 을 그대로 쓴다.** 그래야 결과 변화가 설정 변경이 아니라
  데이터 변화에서만 나온다(AC-19-3). 모델 자동 재학습은 **기본 꺼짐** — 오염이 진행된 구간으로 학습하면 기준 자체가 오염된다.
- **호기 간 비교는 FI·잔차 기반 지표만 쓴다.** 절대 차압·스택온도는 설비마다 달라 비교가 성립하지 않는다(`19` §3.2).
  우선순위 점수는 **비교 대상 호기들 사이의 상대 순위**일 뿐 절대 오염도가 아니므로 근거 지표를 반드시 함께 보여준다.

## 지켜야 할 시스템 불변식

이 네 가지는 거의 모든 명세에 반복해서 나오는 제약이다. 코드가 이를 어기면 명세 위반이다.

1. **원본 불변.** `Measurement`는 절대 수정·삭제하지 않는다. 제외는 파생 테이블의 `is_valid` / `exclusion_reason` 플래그로만 표현하고, 사유별 건수를 UI에 띄운다.
2. **설정값은 전부 DB.** 임계치·등급 경계·가중치·필터 임계값·편익 계수 어느 것도 코드에 상수로 두지 않는다.
   조회 우선순위는 **`UnitSetting`(호기 오버라이드) → `Setting`(전역) → 코드 시드 기본값**. 새 튜닝값을 만들면 `Setting` 시드와 관리자 화면 항목을 같은 변경에 포함한다.
3. **재현성.** `AnalysisRun` 하나만 보고도 결과를 재현할 수 있어야 한다 → `settings_snapshot`, `benefit_params_snapshot`,
   `model_version_dp/st`, `cluster_definition`, `column_mapping_version` 를 모두 스냅샷으로 저장. 난수는 공통 상수 `RANDOM_SEED` 고정.
4. **표준 항목명만 쓴다.** 분석 코드는 원본 CSV 컬럼명을 알지 못한다. 호기별 `ColumnMapping`이 원본 → 표준 항목으로 변환한 뒤에만 진입한다.

### 표준 항목 어휘 (`specs/02` §3)

필수: `timestamp`, `gt_power_mw`, `ambient_temp_c`, `gt_exhaust_temp_c`, `exhaust_flow`, `hrsg_gas_dp_kpa`, `stack_temp_c`, `duct_burner_on`
대체: `fuel_flow` / `igv_position_pct` → `exhaust_flow`, `gt_backpressure_kpa` → `hrsg_gas_dp_kpa` (호기의 `dp_source`/`flow_source`가 결정)
선택: `st_power_mw`, `steam_flow_tph`, `feedwater_temp_c`, `ambient_pressure_kpa`, `humidity_pct`

차압 미계측(배압 대체) 호기는 가중치 기본값이 뒤집힌다(`w_dp=0.4`, `w_st=0.6`).

## API·프론트 계약에서 놓치기 쉬운 점

- **인증은 세션 쿠키(HttpOnly, SameSite=Lax) + CSRF로 확정됐다**(`specs/15` §1, `01` §3.3, `AGENTS.md` §6). JWT는 사용하지 않는다.
- **로그인은 성명 + 사번 + 비밀번호 3요소.** `USERNAME_FIELD = 'employee_no'`, `username` 필드는 제거. 커스텀 User는 **첫 마이그레이션 이전에** 확정해야 한다(`specs/14` §7).
- **앱 권한은 `role == 'ADMIN'` 으로 판정한다.** Django의 `is_staff`/`is_superuser`는 `/admin/` 접근용일 뿐 권한 판정에 쓰지 않는다.
- **오래 걸리는 작업은 전부 202 + job_id 패턴**(검증·적재·분석·재학습·리포트). `GET /api/jobs/{job_id}/` 로 `status`/`progress`/`stage` 폴링, 프론트는 `useJobPolling.js`로 처리하며 페이지를 이탈했다 돌아와도 복원돼야 한다.
- **동시성 제약**: 호기당 분석 동시 1건(중복 시 409 `ANALYSIS_ALREADY_RUNNING`), 사용자당 업로드 동시 1건.
- **업로드는 검증과 적재가 분리**된다. `validate` → 사용자 확인 → `commit`.
  **구조 오류**(컬럼 누락·중복 헤더·필수 항목 미매핑)만 적재를 차단하고, 행 단위 오류(타임스탬프 해석 실패 등)는 해당 행만 제외하고 진행한다(`specs/03` §4.4).
- **차트 데이터는 일 단위 집계로 반환**한다. 원시 포인트를 그대로 내려보내지 않는다(`specs/18` §1).
- 편익 파라미터만 바꿔 다시 계산할 때는 분석 전체를 재실행하지 않고 `POST /api/analysis-runs/{id}/recalculate-benefit/` 를 쓴다.
- **`/api/units/comparison/` 은 `analysis/urls.py` 에 있고, `config/urls.py` 에서 `analysis` 를 `units` 보다 먼저 include 한다.**
  순서를 되돌리면 units 라우터의 `units/{pk}/` 가 `comparison` 을 pk 로 먹어버린다.

## 명령어

정본은 `AGENTS.md` §10. `analysis/` 관련 명령은 Phase 3 이후에 유효하다.

```bash
# 인프라 먼저 (SQLite 금지 — 로컬·테스트도 PostgreSQL)
docker compose up -d db redis

# Backend
cd backend && source .venv/bin/activate
cp .env.example .env        # 최초 1회
python manage.py migrate
python manage.py seed_defaults      # 기본 관리자 + Setting 시드 + 키워드 시드 (멱등이어야 함)
python manage.py runserver
celery -A config worker -l info   # 별도 터미널. 업로드 검증·적재가 워커에서 돈다.
pytest
pytest analysis/tests/test_fouling_index.py::test_ac_07_4_fi_never_leaves_zero_hundred  # 단일 테스트
pytest analysis/tests/test_integration_scenario.py   # specs/17 §6 9단계 통합 시나리오
pytest analysis/tests/test_backtest_no_leakage.py    # AC-19-4 미래 정보 누설 차단
pytest -m "not django_db"           # PostgreSQL 없이 돌릴 수 있는 순수 함수 테스트만
pytest --cov=analysis/services      # 커버리지 80% 이상이 기준

# 샘플 데이터 (전 파이프라인 검증의 기준 데이터)
python scripts/generate_sample_data.py --unit-code U1 --months 24 --cleanings 3 --seed 42 \
  --out sample_unit1.csv --maintenance-out sample_unit1_maintenance.csv
#   --korean-headers : 한글 헤더 출력(컬럼 매핑 검증용)
#   --messy          : 결측·이상치·중복·형식오류 주입(업로드 검증 테스트용)
#   --truth-out      : 정답 fouling_level 시계열 → FI 정확도 검증용(상관계수 ≥ 0.9 기준)

# Frontend
cd frontend && npm install && npm run dev
npm run build
npm run test
```

## 테스트 환경에서 한 번씩 걸리는 것

- **Celery eager 모드는 `override_settings` 로만 켜진다.** `current_app.conf` 에 직접 대입하거나
  `conf.update()` 를 써도 먹히지 않는다 — 앱이 `config_from_object("django.conf:settings")` 로
  읽어서 Django settings 값이 우선한다. 픽스처는 루트 `conftest.py` 에 있다.
  `EAGER_PROPAGATES` 는 꺼 둔다. 켜면 태스크 예외가 뷰까지 올라와 500 이 되는데,
  운영에서는 뷰가 이미 202 를 준 뒤 워커가 실패를 DB 에 기록하므로 그 경로를 검증할 수 없게 된다.
- **로그인 스로틀 카운터는 테스트마다 비운다**(IP 기준 분당 10회). 안 비우면 뒤 테스트가 429 를 받는다.
- **Node 26 은 자체 `localStorage` 전역을 갖는데 `--localstorage-file` 없이는 `undefined` 이고
  jsdom 구현을 가린다.** `frontend/tests/setup.js` 가 비어 있을 때만 채운다.
- **`git bisect` 주의:** `6380e16`(fix) 한 지점은 테스트가 실패한다. 코드 버그와 테스트 환경 문제가
  서로를 가리고 있어 두 커밋(`6380e16`, `4489578`)을 같이 적용해야 통과한다.
  이 구간을 지날 때는 쫓는 버그의 테스트만 판정 기준으로 쓰거나 `git bisect skip` 한다.

## 분석 로직 테스트 방식

`analysis/services/` 는 Django 모델을 import 하지 않는 순수 함수여야 하고, 합성 데이터로 **성질 기반 검증**을 한다
(`AGENTS.md` §8, `specs/07` AC): 오염 없음 → FI ≈ 0 / 잔차 선형 증가 → FI 단조 증가 / 세정 직후 → FI 급락 / FI가 0~100 밖으로 저장되지 않음.
`generate_sample_data.py` 산출물로 업로드 → 분석 → 리포트 통합 테스트를 최소 1개 유지한다(`specs/17` §6에 9단계 시나리오가 있다).
