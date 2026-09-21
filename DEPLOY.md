# 배포 가이드

`specs/18-nonfunctional.md` §7의 운영 구성을 Docker Compose로 옮긴 것이다.

```
[Nginx]  :443
  ├─ /          → frontend/dist (SPA, index.html 폴백)
  ├─ /api/      → Gunicorn (app)
  ├─ /static/   → collectstatic 결과
  └─ /media/    → internal. 직접 접근 차단, Django 인증 경유만 허용

[app]     Gunicorn + Django
[worker]  Celery — 업로드 적재·분석·재학습·리포트
[db]      PostgreSQL 16
[redis]   Celery 브로커 겸 결과 백엔드
```

개발용 인프라는 `docker-compose.yml`(PostgreSQL + Redis만)이 따로 있다. 혼동하지 않는다.

---

## 1. 준비

### 요구 사항
Docker Engine 24+ / Docker Compose v2

### TLS 인증서

`deploy/certs/` 에 `server.crt` / `server.key` 를 둔다. 사내 CA 발급분이나 Let's Encrypt 결과를 쓴다.

테스트용 자체 서명 인증서가 필요하면:

```bash
mkdir -p deploy/certs
openssl req -x509 -newkey rsa:2048 -nodes -days 365 \
  -keyout deploy/certs/server.key -out deploy/certs/server.crt \
  -subj "/CN=hrsg.example.co.kr"
```

브라우저 경고가 뜨므로 **운영에는 쓰지 않는다.**

### 환경 변수

저장소 루트에 `.env` 를 만든다. 커밋하지 않는다(`AGENTS.md` §7).

```bash
# 반드시 새로 생성한다. 예시값이거나 50자 미만이면 기동이 거부된다.
DJANGO_SECRET_KEY=<python -c "import secrets; print(secrets.token_urlsafe(64))">
DJANGO_ALLOWED_HOSTS=hrsg.example.co.kr
DB_PASSWORD=<충분히 긴 무작위 문자열>

# 선택
DB_NAME=hrsg
DB_USER=hrsg
HTTP_PORT=80
HTTPS_PORT=443
```

`SECRET_KEY` 가 유출되면 세션 위조가 가능하다. `config/settings/prod.py` 가 플레이스홀더와
50자 미만을 거부하므로, 값을 빠뜨리면 조용히 취약한 상태로 뜨지 않고 기동 자체가 실패한다.

---

## 2. 구동

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

`migrate` 서비스가 먼저 한 번 돌고 끝나며, 그 안에서 `specs/18` §7의 절차가 순서대로 수행된다.

1. `migrate` — 스키마 적용
2. `seed_defaults` — 기본 관리자 + 설정 84건 + 오염 키워드 25건 (**멱등**, AC-18-4)
3. `collectstatic` — 정적 파일 수집

`app` 과 `worker` 는 이 작업이 **성공적으로 끝난 뒤에만** 뜬다(`service_completed_successfully`).

### 상태 확인

```bash
docker compose -f docker-compose.prod.yml ps
curl -fsS https://<도메인>/api/health/ready/   # {"status":"ok","checks":{"database":true}}
```

| 엔드포인트 | 용도 |
|---|---|
| `/api/health/live/` | 프로세스 생존. 의존 서비스는 보지 않는다 |
| `/api/health/ready/` | DB 연결까지 확인. LB가 트래픽을 보낼지 판단 |

둘을 나눈 이유: DB가 잠깐 끊겼다고 컨테이너를 재시작하면 상황이 더 나빠진다.
헬스체크는 인증 없이 열려 있고 HTTPS 리다이렉트에서도 제외된다(`SECURE_REDIRECT_EXEMPT`).

---

## 3. 최초 로그인

**성명 + 사번 + 비밀번호** 3요소로 로그인한다.

| 성명 | 사번 | 비밀번호 |
|---|---|---|
| 관리자 | `ADM01` | `qwer` |

이 계정은 **관리자 역할 사용자가 하나도 없을 때만** 생성된다(`specs/01` §4).

> **첫 로그인 직후 비밀번호를 바꾼다.** 배너가 뜨고 `must_change_password=True` 로 표시되지만
> 강제되지는 않는다. 네 글자 기본값을 그대로 두면 안 된다.

---

## 4. 운영 중 작업

### 로그

```bash
docker compose -f docker-compose.prod.yml logs -f app
docker compose -f docker-compose.prod.yml logs -f worker
```

`specs/18` §4 — INFO(로그인·업로드·분석·학습) / WARNING(검증 경고·품질 저하·지표 미달) /
ERROR(예외·작업 실패). 비밀번호와 전체 사번은 남지 않는다(AC-18-3).

### DB 백업

`specs/18` §3은 **일 1회 전체 덤프, 7일 보관**을 요구한다. 운영 환경 책임이므로 cron 등으로 건다.

```bash
docker compose -f docker-compose.prod.yml exec -T db \
  pg_dump -U hrsg hrsg | gzip > backup-$(date +%F).sql.gz
```

복원:

```bash
gunzip -c backup-2026-09-21.sql.gz | \
  docker compose -f docker-compose.prod.yml exec -T db psql -U hrsg hrsg
```

업로드 원본은 `appvar` 볼륨의 `uploads/` 에 있고 **최소 30일 보관**해야 재적재가 가능하다
(`specs/18` §3). DB 덤프만으로는 복구되지 않으므로 볼륨도 함께 백업한다.

### 업데이트

```bash
git pull
docker compose -f docker-compose.prod.yml up -d --build
```

`migrate` 가 매번 다시 돌지만 멱등이라 안전하다.

### 롤백

```bash
git checkout <이전 태그>
docker compose -f docker-compose.prod.yml up -d --build
```

**마이그레이션이 포함된 변경은 코드만 되돌려서는 복구되지 않는다.** 스키마를 먼저 되돌리거나
백업에서 복원한다. 되돌릴 마이그레이션이 있는지 먼저 확인한다:

```bash
docker compose -f docker-compose.prod.yml run --rm migrate python manage.py showmigrations
```

### 규모 조정

분석이 몰려 대기가 길어지면 워커를 늘린다. 분석 한 건이 메모리를 꽤 쓰므로 서버 여유를 보고 올린다.

```bash
docker compose -f docker-compose.prod.yml up -d --scale worker=3
```

웹 요청이 느리면 `GUNICORN_WORKERS` 를 조정한다. 다만 오래 걸리는 작업은 전부 Celery가
맡으므로(202 + job_id 패턴) 웹 워커가 병목인 경우는 드물다.

---

## 5. 배포 후 점검

`specs/18` §10 수용 기준 중 배포와 직접 관련된 항목이다.
아래 항목은 **2026-09-21 Docker Desktop 29.8.0 / Compose v5.5.1 에서 전부 실행해 통과를 확인했다.**

```bash
# AC-18-2 — DEBUG=False 에서 정상 동작 + 보안 헤더
curl -sI https://<도메인>/api/units/ | grep -iE "strict-transport|x-content-type|x-frame|referrer-policy"
#   Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
#   X-Content-Type-Options: nosniff
#   X-Frame-Options: DENY
#   Referrer-Policy: same-origin

# 비인증 요청은 401 (디버그 페이지가 아니라 공통 에러 포맷)
curl -s https://<도메인>/api/units/
#   {"error":{"code":"NOT_AUTHENTICATED","message":"로그인이 필요합니다."}}

# HTTP 는 HTTPS 로 넘어간다
curl -sI http://<도메인>/ | head -1        # 301

# /media/ 직접 접근 차단 (specs/18 §2)
curl -s -o /dev/null -w "%{http_code}\n" https://<도메인>/media/any-file
#   404 — internal 이라 외부에서 진입 경로가 없다

# AC-18-4 — seed_defaults 멱등
docker compose -f docker-compose.prod.yml run --rm migrate python manage.py seed_defaults
#   "설정값: 신규 0건" 이어야 한다
```

---

## 6. 검증 기록 (2026-09-21)

| 항목 | 결과 |
|---|---|
| 이미지 빌드 | app/worker/migrate 각 1.07GB, frontend-build 7.94MB |
| 기동 순서 | migrate 완료 → app·worker → (app healthy) → nginx |
| 헬스체크 | `ready` = `{"status":"ok","checks":{"database":true}}` |
| HTTP → HTTPS | 301 |
| 보안 헤더 (AC-18-2) | HSTS · X-Content-Type-Options · X-Frame-Options · Referrer-Policy |
| 비인증 응답 | 401 + 공통 에러 포맷 |
| 로그인 | `관리자/ADM01/qwer` 성공, 세션·CSRF 쿠키에 Secure 플래그 |
| `/media/` 직접 접근 | 404 (internal) |
| `seed_defaults` 재실행 (AC-18-4) | 신규 0건 |
| Celery 워커 | prefork 2 concurrency, ERROR 0건 |

## 7. 알려진 제약

- **`--pool=solo` 이슈는 리눅스 컨테이너에 없다.** macOS + Python 3.13에서 Celery 기본
  prefork 풀이 깨지는 문제(`ValueError: not enough values to unpack`)는 로컬 개발 한정이다.
  컨테이너에서 기본 prefork 로 정상 동작하는 것을 확인했다.
- **동시 사용자 20명 규모**를 전제로 한 구성이다(`PROJECT.md` §1.6). 그 이상이면 `db` 를
  관리형 PostgreSQL로 분리하고 `app`/`worker` 를 별도 호스트로 나누는 편이 낫다.
- **Redis는 영속화하지 않는다.** 작업 상태는 휘발되지만 `UploadBatch`/`AnalysisRun` 같은
  도메인 테이블이 진실이므로 결과가 사라지지는 않는다. 재시작 시 진행 중이던 작업은 유실된다.
