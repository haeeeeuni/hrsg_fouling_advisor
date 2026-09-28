# 20. UI/UX 가이드

## 테마

**AdminHMD** — https://themewagon.com/themes/adminhmd/ (Bootstrap 5.3, 오픈소스, 상업적 사용 가능)

> 2026-09-21 ~ 09-28 은 Spark(https://themewagon.com/themes/spark/)를 썼다. 전환 이유는 §5.

---

## 1. 적용 방식

AdminHMD 는 **Bootstrap 5.3 기반 관리자 대시보드 템플릿**이므로 `AGENTS.md` §2 의 고정 스택
(Bootstrap 5 + 순수 CSS3, 그 외 UI 프레임워크 금지)과 충돌하지 않는다. jQuery·ApexCharts
의존이 없고 bootstrap-icons 를 쓴다 — 우리와 같다.

템플릿의 HTML 을 그대로 가져오는 대신 **디자인 토큰과 컴포넌트 스타일만 이식**한다.
이미 동작하는 화면 21종(`specs/16`)을 버리고 템플릿 마크업으로 갈아엎을 이유가 없고,
Bootstrap 의 CSS 변수를 덮어쓰면 기존 마크업이 그대로 테마를 따라가기 때문이다.

- 테마 정의: `frontend/src/assets/styles/adminhmd-theme.css` **한 곳**
- Bootstrap 5 의 `--bs-*` 변수를 재정의해 기존 유틸리티 클래스가 자동으로 테마를 따르게 한다
- 템플릿에서 **가져오지 않는 것**: 의미 색(§3), 데모 이미지, `main.js`(우리 셸은 Vue 가 그린다)

### 셸 클래스는 `ui-` 접두를 쓴다

`spark-sidebar` 처럼 테마 이름을 붙이면 테마를 바꿀 때마다 화면 21종의 마크업을 전부
고쳐야 한다. 실제로 Spark → AdminHMD 전환에서 그 비용을 치렀다. 이후로는
`ui-sidebar` / `ui-main` / `ui-navbar` / `ui-card-dark` 처럼 테마 중립 이름을 쓰고,
**테마 교체는 CSS 파일 하나를 갈아 끼우는 것으로 끝낸다.**

현재 쓰는 셸 클래스 17종:
`ui-sidebar` `ui-main` `ui-main--bare` `ui-content` `ui-navbar` `ui-page-title` `ui-pill`
`ui-brand` `ui-menu-title` `ui-menu-link` `ui-sidebar-footer` `ui-user-name`
`ui-card-dark` `ui-stat-label` `ui-stat-value` `ui-auth` `btn-accent`

---

## 2. 디자인 토큰 (템플릿 `assets/css/style.css` 의 `:root`)

| 토큰 | 값 | 용도 |
|------|-----|------|
| `--admin-sidebar` | `#111827` | 사이드바 배경 |
| `--admin-sidebar-soft` | `#1F2937` | 메뉴 hover, 강조 카드 배경 |
| `--admin-primary` | `#2563EB` | 액센트 — 활성 메뉴, 기본 버튼, 링크 |
| `--admin-primary-dark` | `#1D4ED8` | hover |
| `--admin-bg` | `#F5F7FB` | 캔버스 배경 |
| `--admin-surface` | `#FFFFFF` | 카드·네비 표면 |
| `--admin-border` | `#DBE4EF` | 카드·입력 테두리 |
| `--admin-text` / `--admin-muted` | `#1F2937` / `#6B7280` | 본문 / 보조 텍스트 |
| 그림자 | `0 10px 24px rgba(15,23,42,.06)` 외 2단계 | 카드·드롭다운 |
| 라운드 | `10 / 8 / 6 px` | 카드는 `--radius-md`(8px) |
| 사이드바 / 네비 | `280px` / `80px` | 레이아웃 고정값 |

**폰트는 웹폰트를 쓰지 않는다.** 템플릿이 `"Segoe UI", Arial` 시스템 스택이라 그대로 따랐다.
한글 글리프가 없는 라틴 폰트를 앞에 두고 한글용(`Pretendard` → `Apple SD Gothic Neo` →
`Malgun Gothic`)을 뒤에 둔다 — **순서를 바꾸면 한글 폰트가 먼저 잡혀 숫자까지 한글 폰트로
렌더된다.** 대신 OS 에 따라 라틴 글자가 다르게 보인다(Windows: Segoe UI, macOS: SF).

### 레이아웃
전체 높이 고정 사이드바(좌) + 메인 영역 상단 네비게이션. Spark 와 사이드바 폭(280px)이
같아 셸 마크업은 그대로 쓴다. 네비는 Spark 의 투명 배경에서 **흰 표면 + 아래 경계선**으로 바뀐다.

---

## 3. 등급 색은 테마보다 우선한다

FI 등급(정상/주의/경고)의 초록·노랑·빨강은 **도메인 의미를 담은 색**이고
차트·배지·경고 배너가 공유한다(`specs/16` §8, `specs/11` §3).
`--bs-primary` 만 테마 색으로 바꾸고 `--bs-success/warning/danger` 는 덮어쓰지 않는다.

**템플릿이 정의한 의미 색은 가져오지 않는다.** AdminHMD 의 `--admin-success` 는
청록(`#0F766E`)이라 "정상" 으로 읽히지 않는다. 등급 판독이 무너진다.

---

## 4. 접근성

`specs/16` §8 의 "색상만으로 정보를 전달하지 않는다" 규칙은 그대로다.
사이드바 활성 항목은 **채워진 블록**이라 색뿐 아니라 "배경이 있다/없다" 로도 구분된다
(Spark 에서는 왼쪽 라임 막대가 그 역할을 했다).

명암비 실측(2026-09-28, WCAG AA 4.5:1 기준) — 전 항목 통과:

| 대상 | 비율 |
|---|---|
| 기본 버튼·활성 메뉴 (흰 글자 / `#2563EB`) | 5.17:1 |
| 본문 텍스트 | 13.69:1 |
| 보조 텍스트 `#6B7280` / `#F5F7FB` | **4.51:1** |
| 사이드바 메뉴(비활성) | 9.13:1 |
| 등급 배지 3종 | 4.53 ~ 12.88:1 |

보조 텍스트가 4.51:1 로 기준선에 가장 가깝다. `--admin-muted` 를 더 밝게 바꾸면 미달한다.

---

## 5. 전환 기록 (Spark → AdminHMD, 2026-09-28)

| | Spark | AdminHMD |
|---|---|---|
| 사이드바 | `#051C12` 짙은 녹 | `#111827` 차콜 |
| 액센트 | `#B4F105` 라임 | `#2563EB` 블루 |
| 카드 라운드 | 24px | 8px |
| 카드 | 테두리 없음 + 부드러운 그림자 | 1px 테두리 + 넓은 그림자 |
| 폰트 | Plus Jakarta Sans (웹폰트) | 시스템 스택 |
| 다크 모드 | 없음 | **템플릿이 제공(미적용, §6)** |

색보다 **라운드 24px → 8px** 가 인상을 더 크게 바꾼다. 발전소 운영 화면이라는 성격에
조밀하고 업무적인 쪽이 맞다고 보고 전환했다.

검토했으나 채택하지 않은 것: **Slim**(https://themewagon.com/themes/slim/)은 React +
Material UI 라 `AGENTS.md` §2(Vue 3 고정, Bootstrap 이외 UI 프레임워크 금지)와 충돌한다.
디자인 토큰이 556KB JS 번들 안에 있어 추출도 어렵다.

---

## 6. 미결

1. **다크 모드** — 템플릿이 `html[data-theme="dark"]` 로 전체 토큰 세트를 제공하지만
   적용하지 않았다. 채택하려면 **Chart.js 6종의 축·격자·범례 색을 JS 에서 따로 맞춰야 한다**
   (CSS 변수를 따라가지 않는다). 토글 UI 와 사용자별 저장도 필요하다.
2. **템플릿 페이지 구성** — 마크업·위젯 배치까지 따라갈지는 정하지 않았다. 현재는 토큰만
   이식하고 화면 구성은 `specs/11`·`specs/16` 을 따른다.
3. **출처 표기** — 템플릿 마크업을 복사하지 않고 토큰만 참조했으므로 배포물에 포함되는
   템플릿 코드가 없다. 그래도 표기를 남길 것인가?
