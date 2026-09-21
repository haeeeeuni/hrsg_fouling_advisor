# 18. 비기능 요구사항

---

## 1. 성능

| 항목 | 목표 |
|------|------|
| 로그인 응답 | < 1초 |
| 대시보드 최초 로딩(캐시된 분석 결과) | < 3초 |
| CSV 검증 + 적재 (100만 행 / 약 100 MB) | < 5분 |
| 분석 실행 (1년치 10분 주기 데이터, 약 5만 행) | < 60초 |
| 모델 재학습 | < 3분 |
| PDF 리포트 생성 | < 30초 |
| 엑셀 리포트 생성 | < 20초 |
| 목록 API 응답 (페이지 50건) | < 500ms |
| 동시 사용자 | 20명 (사내 규모) |

### 성능 설계 지침
- 대용량 CSV는 `chunksize` 스트리밍 처리, 메모리 2 GB 이하 유지.
- `Measurement` 조회는 반드시 `(unit, timestamp)` 인덱스를 타도록 필터 순서를 유지.
- FI 시계열 등 차트 데이터는 일 단위로 집계해 반환(원시 포인트 직접 전송 금지).
- 분석 결과는 `AnalysisRun`에 비정규화 요약 필드를 두어 목록 조회에서 조인을 줄인다.
- N+1 쿼리 방지: `select_related` / `prefetch_related` 사용.

## 2. 보안

| 항목 | 요구 |
|------|------|
| 인증 | 세션 쿠키(HttpOnly, Secure, SameSite=Lax) |
| 비밀번호 | Django PBKDF2 해시, 평문 저장·로그 금지 |
| 권한 | 서버 측 재검증 필수(프론트 가드는 UX용) |
| CSRF | 모든 상태 변경 요청에 토큰 필요 |
| CORS | 운영은 동일 오리진, 개발만 화이트리스트 |
| 업로드 | 확장자·MIME·크기·행수 검증, 원본은 미디어 루트 밖 별도 경로 저장 |
| CSV 인젝션 | 엑셀/CSV 출력 시 `=`, `+`, `-`, `@` 로 시작하는 셀 앞에 `'` 삽입 |
| 비밀정보 | `SECRET_KEY`, DB 비밀번호는 `.env`, 저장소 커밋 금지 |
| 운영 설정 | `DEBUG=False`, `ALLOWED_HOSTS` 명시, 보안 헤더(HSTS, X-Content-Type-Options, X-Frame-Options) |
| SQL 인젝션 | ORM 사용, raw SQL은 파라미터 바인딩 필수 |
| 감사 | 관리자 변경·로그인 시도 전부 기록 |

### 개인정보
- 수집 항목은 성명, 사번, 부서, 연락처로 한정한다.
- 로그·에러 리포트에 비밀번호·사번 전체를 남기지 않는다(마스킹).
- 계정 삭제는 비활성화를 기본으로 하고, 물리 삭제 시 관련 이력의 사용자 참조는 익명 처리한다.

## 3. 신뢰성 / 가용성
- 분석·업로드 실패 시 원자성 보장(트랜잭션), 부분 적재 금지.
- 비동기 작업 실패 시 재시도 1회 후 실패 기록.
- DB 백업: 일 1회 전체 덤프, 7일 보관(운영 환경 책임).
- 업로드 원본 파일은 최소 30일 보관해 재적재가 가능하게 한다.

## 4. 로깅 / 관측

| 레벨 | 대상 |
|------|------|
| INFO | 로그인/로그아웃, 업로드 시작·완료, 분석 시작·완료, 모델 학습 |
| WARNING | 검증 경고, 데이터 품질 저하, 모델 지표 미달, 도메인 밖 데이터 |
| ERROR | 예외, 작업 실패 |

- 구조적 로그(JSON) 권장. 필드: `timestamp`, `level`, `logger`, `user_id`, `unit_id`, `run_id`, `message`.
- 분석 실행 로그는 단계별 소요 시간을 기록해 병목을 추적할 수 있게 한다.
- 민감정보 마스킹 필터를 적용한다.

## 5. 국제화 / 표기
- UI 언어는 한국어 단일(다국어 미지원).
- 시간대는 `Asia/Seoul` 고정(`TIME_ZONE='Asia/Seoul'`, `USE_TZ=True`).
- 모든 파일 입출력 기본 인코딩은 UTF-8, CSV 읽기는 CP949 폴백 지원.
- 엑셀·PDF의 한글 표기가 깨지지 않아야 한다(`12-reports.md` 3.1 필수 사항).

## 6. 브라우저 지원
- Chrome / Edge 최신 2개 버전 (사내 표준 브라우저)
- 최소 해상도 1280 × 800
- Internet Explorer 미지원

## 7. 배포 구성

```
[Nginx]
  ├─ /            → frontend/dist (SPA, index.html 폴백)
  ├─ /api/        → Gunicorn (Django)
  ├─ /static/     → Django collectstatic 결과
  └─ /media/      → 업로드 원본 (직접 접근 차단, 인증 경유 다운로드)

[Gunicorn] → Django
[PostgreSQL]
[비동기 작업] Celery + Redis (권장) 또는 Django 백그라운드 스레드(소규모 대안)
```

### 환경 변수
```
DJANGO_SECRET_KEY, DJANGO_DEBUG, DJANGO_ALLOWED_HOSTS
DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT
MEDIA_ROOT, REPORT_ROOT, MODEL_ARTIFACT_ROOT
CELERY_BROKER_URL (사용 시)
```

### 초기 구동 절차
```
1. 환경 변수 설정
2. python manage.py migrate
3. python manage.py seed_defaults      # 기본 관리자 + 설정 시드 + 키워드 시드
4. python manage.py collectstatic
5. gunicorn config.wsgi
```
- `seed_defaults`는 **멱등**해야 한다(여러 번 실행해도 중복 생성 없음).

### 구현 (2026-09-21, Phase 8)

위 구성을 Docker Compose 로 옮겼다. 절차는 `DEPLOY.md` 참조.

| 산출물 | 내용 |
|--------|------|
| `docker-compose.prod.yml` | nginx / app(gunicorn) / worker(celery) / db / redis |
| `deploy/nginx/hrsg.conf` | SPA 폴백, `/api/` 프록시, `/static/`, `/media/` **internal** |
| `backend/Dockerfile` | python:3.13-slim, 비-root 실행, 동봉 폰트 존재 검증 |
| `frontend/Dockerfile` | 빌드 전용 — 산출물만 nginx 로 넘긴다 |
| `backend/gunicorn.conf.py` | 워커 수·타임아웃. nginx `proxy_read_timeout` 보다 짧게 |
| `DEPLOY.md` | 구동·백업·롤백·배포 후 점검 |

**추가된 동작 (원안에 없던 것):**

- **헬스체크** `GET /api/health/live/`, `GET /api/health/ready/` — 컨테이너·LB 가 기동을
  판단할 경로가 필요하다. 인증 없이 열되 내부 구성(버전·경로·예외)은 노출하지 않는다.
  둘을 나눈 이유는 DB 가 잠깐 끊겼다고 컨테이너를 재시작하면 상황이 더 나빠지기 때문이다.
- **`SECURE_SSL_REDIRECT`** — §2 가 Secure 쿠키와 HSTS 를 요구하므로 HTTPS 가 전제다.
  단 헬스체크는 컨테이너 내부에서 http 로 들어오므로 `SECURE_REDIRECT_EXEMPT` 로 뺀다.
  빼지 않으면 301 이 나가 기동 판정이 실패한다.
- **`SECRET_KEY` 기동 거부** — 플레이스홀더이거나 50자 미만이면 `prod.py` 가 예외를 던진다.
  §2 가 `.env` 관리를 요구하지만, 빠뜨렸을 때 조용히 취약한 상태로 뜨는 것을 막는다.

### 데모 배포 (2026-09-21, 시연 전용)

위 구성은 사내 운영용이다. 프로젝트 시연을 위해 PaaS(Render) 경로를 **별도로** 추가했다.

> **이 경로는 `PROJECT.md` §1.5(외부 공개 서비스 제외)와 `specs/01` §1(폐쇄형 사내 시스템)에
> 어긋난다.** 시연 목적에 한정하며 실제 운전 데이터를 올리지 않는다
> (`scripts/generate_sample_data.py` 산출물만 사용).

| 산출물 | 내용 |
|--------|------|
| `render.yaml` | Blueprint — web / Postgres / Key Value |
| `Dockerfile.render` | 단일 이미지 (SPA 빌드 + Django) |
| `config/settings/demo.py` | `prod.py` 상속. 차이는 아래 세 가지뿐 |
| `.dockerignore`(루트) | 저장소 루트를 컨텍스트로 쓰는 빌드용 |

`prod.py` 와의 차이:

1. **WhiteNoise 가 SPA·정적 파일을 서빙한다.** PaaS 는 컨테이너 하나만 띄우므로 Nginx 가 없다.
   프론트가 `baseURL: '/api'` 상대 경로 + `withCredentials` 를 쓰므로 SPA 와 API 가 같은
   오리진이어야 세션 쿠키가 동작한다. 정적 사이트를 분리하면 CORS 와 `SameSite=None` 완화가
   필요해지므로 단일 서비스로 둔다.
2. **HTTPS 리다이렉트를 끈다.** PaaS 가 앞단에서 이미 처리한다.
3. **`DEMO_RUN_TASKS_INLINE`** — 무료 플랜에는 백그라운드 워커가 없다. 켜면 업로드·분석이
   요청 안에서 끝난다. `CELERY_TASK_STORE_EAGER_RESULT` 를 함께 켜야 동기 실행 결과가
   백엔드에 저장되어 `GET /api/jobs/{id}/` 폴링(`specs/15` §1)이 성립한다.

**WhiteNoise 추가 근거:** `AGENTS.md` §9 는 명세에 없는 라이브러리 추가를 금지한다.
§7 원안이 PaaS 를 다루지 않아 어떤 방식이든 명세 밖이므로, Django 에서 정적 파일을 서빙하는
표준 수단인 WhiteNoise 를 **데모 설정에서만** 쓴다. 사내 운영 경로(`prod.py`)는 그대로다.

## 8. 테스트 기준
| 대상 | 기준 |
|------|------|
| `analysis/services/` | 커버리지 80% 이상, 성질 기반 테스트 포함 |
| API | 권한(401/403), 검증 오류, 정상 경로 |
| 통합 | 샘플 데이터 → 업로드 → 분석 → 리포트 전 구간 1개 이상 |
| PDF | 한글 텍스트 추출 검증 테스트 |
| 프론트 | 포맷터·스토어 단위 테스트 |

## 9. 유지보수성
- 설정값·기준값은 전부 DB. 코드 수정 없이 튜닝 가능해야 한다.
- 분석 로직은 Django 의존 없는 순수 함수로 유지해 단위 테스트·재사용이 쉽도록 한다.
- 새 호기 추가는 화면 작업만으로 완료되어야 한다(코드 변경 불필요).
- 모든 명세 변경은 `specs/` 갱신과 함께 이루어진다.

## 10. 수용 기준 (AC)
- [ ] AC-18-1: 100만 행 CSV 적재가 5분 이내에 끝난다.
- [ ] AC-18-2: `DEBUG=False` 운영 설정에서 정상 동작하고 보안 헤더가 응답에 포함된다.
- [ ] AC-18-3: 로그에 비밀번호·전체 사번이 남지 않는다.
- [ ] AC-18-4: `seed_defaults`를 두 번 실행해도 데이터가 중복되지 않는다.
- [ ] AC-18-5: 엑셀 출력물에 CSV 인젝션 방지 처리가 적용된다.
