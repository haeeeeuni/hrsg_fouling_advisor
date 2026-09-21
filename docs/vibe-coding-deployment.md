<!--
Vibe Coding 가이드의 "## Deployment" 절 초안.

이 저장소의 배포 문서는 DEPLOY.md 다. 이 파일은 가이드 독자(Vue + Django +
PostgreSQL 앱을 같은 흐름으로 만드는 사람)를 위한 튜토리얼 원고이며,
HRSG 프로젝트에서 실제로 겪은 문제를 근거로 썼다.

가이드 문서에 붙여넣을 때는 이 주석을 지운다.
-->

## Deployment

개발이 끝난 App을 실제로 사용할 수 있게 올리는 단계다. 목적에 따라 두 갈래로 나뉜다.

| 목적 | 방식 | 필요한 것 |
|------|------|-----------|
| **프로젝트 시연** — 링크로 보여주기 | Render (PaaS) | GitHub 계정, Render 계정 |
| **사내 운영** — 실제 업무 사용 | Docker Compose | 사내 서버, Docker Engine |

두 방식은 배타적이지 않다. 같은 코드로 데모를 올리고 사내에 배포할 수 있다.

> **주의:** 사내 시스템으로 만든 App을 Render 같은 공개 플랫폼에 올릴 때는
> **실제 업무 데이터를 넣지 않는다.** 샘플 데이터로만 시연한다.
> 기본 관리자 비밀번호도 반드시 바꾼다.

---

### Step 1: 배포 준비 상태 점검

Claude Prompt에 다음과 같이 입력한다.

```yaml
배포를 준비하려고 해. 지금 저장소에 배포에 필요한 것이 무엇이 있고 무엇이 없는지 확인해 줘.

- 운영용 Django 설정 (DEBUG=False, ALLOWED_HOSTS, 보안 헤더)
- WSGI 서버 (gunicorn)
- 정적 파일 수집 (collectstatic) 설정
- 환경 변수 관리 (.env, SECRET_KEY)
- 헬스체크 엔드포인트

없는 것은 목록으로만 알려주고 아직 만들지 마.
```

대부분의 경우 `settings/prod.py`는 있어도 **gunicorn, 배포 파일, 헬스체크는 없다.**
개발 단계에서 `python manage.py runserver`만 썼기 때문이다.

> `runserver`는 개발 전용 서버다. 운영에 쓰면 안 된다는 경고가 Django 문서에 명시되어 있다.

---

### Step 2: 데모 배포 (Render)

#### 2-1. 배포 파일 생성

Claude Prompt에 다음과 같이 입력한다.

```yaml
Render에 데모를 배포하려고 해. 다음을 만들어 줘.

- render.yaml (Blueprint): web 서비스 + PostgreSQL
- Dockerfile: 프론트엔드 빌드 결과를 Django가 함께 서빙하는 단일 이미지
- 데모 전용 Django 설정 파일 (운영 설정을 상속하되 PaaS에 맞게 조정)

중요한 제약:
- 프론트엔드가 상대 경로로 API를 호출하고 세션 쿠키를 쓰므로,
  SPA와 API가 반드시 같은 오리진이어야 한다. 정적 사이트를 분리하지 마라.
- 운영 설정 파일(prod.py)은 수정하지 마라. 데모용은 따로 만들어라.
```

**왜 단일 서비스인가** — Vue SPA를 Render의 Static Site로, Django를 Web Service로
나누면 도메인이 달라진다. 그러면 세션 쿠키가 전달되지 않아 CORS 설정과
`SameSite=None` 완화가 필요해진다. 보안을 낮추는 변경이므로 데모라도 피하는 편이 좋다.

#### 2-2. 이미지 크기 확인

Claude Prompt에 다음과 같이 입력한다.

```yaml
만든 Dockerfile로 이미지를 빌드하고 크기를 확인해 줘. 예상보다 크면 원인을 찾아 줘.
```

> **자주 걸리는 함정:** `.dockerignore`는 **빌드 컨텍스트 기준**으로 적용된다.
> `backend/.dockerignore`를 만들어 두었어도 빌드 컨텍스트가 저장소 루트면 무시된다.
> 실제로 이 때문에 `.venv`(520MB)와 테스트 데이터(1.2GB)가 이미지에 들어가
> **5.84GB**가 된 사례가 있다. 루트에 `.dockerignore`를 두어 1.08GB로 줄였다.

#### 2-3. 로컬에서 먼저 띄워 본다

```yaml
빌드한 이미지를 로컬에서 컨테이너로 띄우고, 다음을 확인해 줘.

- 브라우저 진입점(/)에서 SPA가 뜨는지
- /assets/ 아래 JS·CSS 파일이 올바른 Content-Type으로 내려오는지
- SPA 라우트(/dashboard 등)가 404가 아닌지
- /api/ 요청이 SPA 폴백에 먹히지 않는지
```

> **자주 걸리는 함정:** `collectstatic`은 정적 파일을 `/static/` 아래로 옮기는데
> Vite가 만든 `index.html`은 `/assets/`를 참조한다. 경로가 어긋나면
> **자바스크립트 대신 HTML이 내려와 화면이 완전히 빈다.**
> 브라우저에서는 그냥 흰 화면만 보여 원인을 찾기 어렵다.
> `curl`로 Content-Type을 확인하면 바로 드러난다.
>
> ```bash
> curl -s -o /dev/null -w "%{http_code} %{content_type}\n" http://localhost:9000/assets/index-xxx.js
> # 정상: 200 text/javascript
> # 문제: 200 text/html      ← 폴백 HTML이 내려온 것
> ```

#### 2-4. Render에 올린다

1. [Render](https://render.com) 로그인 → **New** → **Blueprint**
2. GitHub 저장소 연결 → `render.yaml`이 자동 인식된다
3. **Apply** → 빌드가 시작된다

`SECRET_KEY`는 Render가 생성하고, DB 연결 문자열은 자동 주입된다.

**무료 플랜 제약**

| 항목 | 내용 |
|------|------|
| 웹 인스턴스 | 미사용 시 잠듦 → 첫 접속이 수십 초 걸린다 |
| 메모리 | 작다. 분석 라이브러리를 쓰면 워커 수를 제한해야 OOM을 피한다 |
| PostgreSQL | 유효 기간이 있다. 만료되면 재생성해야 한다 |
| 백그라운드 워커 | **없다 (유료)** |

Celery 같은 비동기 워커를 쓰는 App이면 무료 플랜에서 작업이 영영 끝나지 않는다.
이럴 때는 요청 안에서 동기 실행하도록 데모 설정을 두는 방법이 있다.

```yaml
무료 플랜에는 백그라운드 워커가 없어. 데모에서만 작업을 요청 안에서 동기 실행하도록
설정을 추가해 줘. 작업 상태 폴링 API는 그대로 동작해야 해.
```

#### 2-5. 배포 후 확인

```bash
curl https://<앱이름>.onrender.com/api/health/ready/
```

브라우저로 접속해 **실제 로그인까지** 해 본다.

> **로컬에서 검증되지 않는 항목이 있다.** 운영 설정은 보통 `SESSION_COOKIE_SECURE=True`라
> HTTPS에서만 쿠키가 전달된다. 로컬 HTTP 테스트에서는 로그인이 200을 반환해도
> 다음 요청이 401이 된다. Render는 HTTPS이므로 실제로는 동작하지만,
> **배포 후 첫 로그인은 반드시 직접 확인한다.**

---

### Step 3: 사내 운영 배포 (Docker Compose)

사내망 서버에 올리는 경우다. 외부에 노출되지 않고, 데이터가 회사 밖으로 나가지 않는다.

#### 3-1. 배포 구성 생성

```yaml
사내 서버에 배포할 구성을 만들어 줘.

- Nginx: SPA 서빙 + /api/ 리버스 프록시 + 정적 파일
- Gunicorn: Django WSGI
- PostgreSQL, (필요하면) Redis + Celery 워커
- docker-compose.prod.yml 로 묶고, DEPLOY.md 에 절차를 정리해 줘

업로드 원본 파일은 링크만 알면 받아갈 수 없도록 Nginx에서 직접 접근을 차단해 줘.
```

#### 3-2. 반드시 확인할 것

```yaml
만든 Compose 구성을 실제로 띄워서 다음을 확인해 줘.

- 마이그레이션 → 시드 → 정적파일 수집이 순서대로 수행되는지
- 모든 컨테이너가 healthy 인지
- 보안 헤더(HSTS, X-Frame-Options 등)가 응답에 포함되는지
- 비인증 요청이 401을 반환하는지 (디버그 페이지가 아니라)
- 업로드 파일 경로에 직접 접근하면 차단되는지
- 시드 명령을 두 번 실행해도 데이터가 중복되지 않는지
```

> **헬스체크와 HTTPS 리다이렉트가 충돌한다.** 운영 설정에서 HTTP를 HTTPS로
> 강제 리다이렉트하면, 컨테이너 내부에서 http로 들어오는 헬스체크가 301을 받아
> **기동 판정이 영영 실패한다.** 헬스체크 경로만 리다이렉트 예외로 빼야 한다.

#### 3-3. 서버에 올린다

서버에는 **Docker만 설치되어 있으면 된다.** Python도 Node도 PostgreSQL도 필요 없다.

```bash
git clone <저장소 URL>
cd <프로젝트>
# .env 작성 (SECRET_KEY, 도메인, DB 비밀번호)
docker compose -f docker-compose.prod.yml up -d --build
```

---

### Step 4: 배포 후 성능 확인

```yaml
명세에 적힌 성능 목표를 실제로 측정해 줘. 목표만 있고 실측이 없으면
통과하는지 알 수 없어. 측정 결과를 명세 문서에 기록해 줘.
```

목표만 적혀 있고 한 번도 재보지 않은 경우가 많다. 실제로 재보면
여유가 큰지 아슬아슬한지 알 수 있고, 병목이 어디인지도 드러난다.

---

### Tips

#### 배포 전에 반드시 바꿀 것

- **기본 관리자 비밀번호** — 가이드대로 만들면 `admin1234!` 같은 초기값이 그대로 남는다
- **SECRET_KEY** — `.env.example`을 복사해 쓰면 예시값이 그대로 들어간다.
  유출되면 세션 위조가 가능하다. 다음처럼 새로 만든다.
  ```bash
  python -c "import secrets; print(secrets.token_urlsafe(64))"
  ```

Claude에게 아예 안전장치를 넣어 달라고 하는 편이 낫다.

```yaml
운영 설정에서 SECRET_KEY가 예시값이거나 너무 짧으면 서버가 아예 뜨지 않도록 막아 줘.
조용히 취약한 상태로 뜨는 것보다 기동이 실패하는 편이 안전해.
```

#### localhost 링크는 다른 PC에서 열리지 않는다

`http://localhost:5173`은 **그 컴퓨터 자신**을 가리킨다. 다른 PC에서 열면
그 PC의 5173 포트를 찾는다. 팀원에게 보여주려면 배포를 하거나,
같은 네트워크라면 서버를 외부 인터페이스에 바인딩하고 `ALLOWED_HOSTS`에 IP를 추가해야 한다.

#### Docker Desktop 설치 시 sudo

`brew install --cask docker`는 `/usr/local/bin`에 심볼릭 링크를 만들기 위해
**관리자 비밀번호를 요구한다.** VS Code의 Claude Code 패널에서 실행하면
비밀번호를 입력할 터미널이 없어 실패한다. **터미널 앱을 직접 열어 실행한다.**

sudo 없이 쓰려면 Colima 같은 대안도 있다.

```bash
brew install colima docker docker-compose
colima start
```

#### 기업에서 Docker Desktop 사용

Docker Desktop은 일정 규모 이상 기업의 상용 사용 시 **유료 구독**이 필요하다.
서버에 들어가는 Docker Engine(리눅스)은 무료이므로 배포 자체와는 무관하지만,
개발자 PC에 까는 경우 확인이 필요하다.
