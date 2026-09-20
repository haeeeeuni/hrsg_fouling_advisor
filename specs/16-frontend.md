# 16. 프론트엔드 명세 (Vue 3 SPA)

관련 요구사항: TR-01

---

## 1. 기술 구성

| 항목 | 선택 |
|------|------|
| 프레임워크 | Vue 3 (Composition API, `<script setup>`) |
| 빌드 | Vite |
| 라우팅 | Vue Router 4 (history 모드) |
| 상태 | Pinia |
| UI | Bootstrap 5 (+ Bootstrap Icons) |
| HTTP | axios (인터셉터로 CSRF·오류 공통 처리) |
| 차트 | Chart.js + vue-chartjs (1종만 사용) |
| 날짜 | dayjs |
| 테스트 | Vitest |

## 2. 디렉터리 구조

```
frontend/src/
├── main.js
├── App.vue
├── router/
│   └── index.js            # 라우트 + 인증/권한 가드
├── stores/
│   ├── auth.js             # 로그인 상태, 사용자 정보
│   ├── units.js            # 호기 목록, 선택 호기
│   ├── analysis.js         # 분석 실행/결과 캐시
│   └── settings.js         # 유효 설정값
├── api/
│   ├── client.js           # axios 인스턴스, 인터셉터
│   ├── auth.js  units.js  uploads.js  analysis.js
│   ├── maintenance.js  reports.js  settings.js  models.js
├── composables/
│   ├── useJobPolling.js    # 비동기 job 진행률 폴링
│   ├── useFormat.js        # 숫자/금액/날짜 포맷
│   └── useToast.js
├── components/
│   ├── common/   (AppNavbar, AppSidebar, LoadingSpinner, EmptyState,
│   │              ConfirmDialog, ToastContainer, PageHeader, DataTable)
│   ├── charts/   (FoulingTrendChart, ResidualChart, ScatterChart,
│   │              ClusterBarChart, QualityGauge, TornadoChart)
│   ├── dashboard/(KpiCard, GradeBadge, WarningBanner, BenefitPanel,
│   │              ModelAccuracyPanel, DataQualityPanel)
│   ├── upload/   (FileDropzone, ValidationReport, MappingPreview)
│   └── admin/    (SettingForm, ColumnMappingEditor, UserForm,
│                  CleaningEventForm, KeywordEditor)
├── views/
│   ├── LoginView.vue
│   ├── DashboardView.vue
│   ├── UploadView.vue
│   ├── AnalysisRunView.vue
│   ├── AnalysisHistoryView.vue
│   ├── ComparisonView.vue
│   ├── MaintenanceView.vue
│   ├── ReportsView.vue
│   ├── ProfileView.vue
│   └── admin/
│       ├── AdminLayout.vue
│       ├── UsersView.vue
│       ├── UnitsView.vue
│       ├── ColumnMappingView.vue
│       ├── SettingsView.vue
│       ├── BenefitSettingsView.vue
│       ├── CleaningEventsView.vue
│       ├── KeywordsView.vue
│       ├── ModelsView.vue
│       ├── RunHistoryView.vue
│       └── UnitComparisonView.vue
├── utils/
│   ├── format.js           # 숫자/금액/단위 포맷터
│   └── constants.js        # 등급, 색상, 라벨 매핑
└── assets/styles/
    └── main.css
```

## 3. 라우팅

| 경로 | 뷰 | 권한 |
|------|-----|------|
| `/login` | LoginView | 공개 |
| `/` | → `/dashboard` 리디렉션 | 인증 |
| `/dashboard` | DashboardView | 인증 |
| `/upload` | UploadView | 인증 |
| `/analysis/new` | AnalysisRunView | 인증 |
| `/analysis/history` | AnalysisHistoryView | 인증 |
| `/analysis/:id` | DashboardView (특정 실행 결과) | 인증 |
| `/comparison` | ComparisonView | 인증 |
| `/maintenance` | MaintenanceView | 인증 |
| `/reports` | ReportsView | 인증 |
| `/profile` | ProfileView | 인증 |
| `/admin/...` | admin/* | 관리자 |
| `/:pathMatch(.*)` | NotFoundView | – |

### 가드 규칙
```
beforeEach:
  1. auth 스토어가 초기화되지 않았으면 GET /auth/me/ 로 복원
  2. meta.requiresAuth && !isAuthenticated  → /login (redirect 쿼리 보존)
  3. meta.requiresAdmin && role !== 'ADMIN' → /dashboard + "권한 없음" 토스트
  4. isAuthenticated && to.path === '/login' → /dashboard
```

## 4. 레이아웃
- 상단 네비게이션: 로고, 호기 선택 드롭다운(전역), 사용자 메뉴(프로필/비밀번호 변경/로그아웃)
- 좌측 사이드바: 대시보드 / 데이터 업로드 / 분석 실행 / 분석 이력 / 세정 전후 비교 / 정비 이력 / 리포트 / (관리자) 관리자 콘솔
- 호기 선택은 `units` 스토어에 유지되며 페이지 이동 시 보존된다(로컬 스토리지 저장).

## 5. 상태 관리 (Pinia)

```
auth      : user, isAuthenticated, isAdmin, login(), logout(), fetchMe(), changePassword()
units     : list, selectedUnitId, selectedUnit, fetchUnits(), selectUnit()
analysis  : currentRun, runResult(캐시), job(진행률), runAnalysis(), fetchResult()
settings  : effectiveSettings(호기별), fetchEffective()
```

- 서버 응답은 스토어에 저장해 재방문 시 재요청하지 않는다(호기·분석 변경 시 무효화).
- 컴포넌트는 스토어 액션만 호출하고 axios를 직접 호출하지 않는다.

## 6. 공통 UX 규칙

| 상황 | 처리 |
|------|------|
| 로딩 | 스켈레톤 또는 스피너, 버튼 비활성화 + 중복 클릭 방지 |
| 빈 상태 | `EmptyState` 컴포넌트로 원인 + 다음 행동 안내 |
| 오류 | 서버 `error.message`를 토스트로 표시, `details`는 상세 영역에 표시 |
| 401 응답 | 인터셉터가 auth 초기화 후 `/login`으로 이동 |
| 파괴적 작업 | `ConfirmDialog`로 확인(대상 이름을 문구에 포함) |
| 장시간 작업 | 진행률 바 + 단계명 표시, 이탈해도 job 상태 복원 가능 |
| 폼 검증 | 클라이언트 즉시 검증 + 서버 검증 오류를 필드별로 매핑 |

## 7. 포맷 규칙 (`utils/format.js`)

| 대상 | 형식 | 예 |
|------|------|-----|
| 오염도 지수 | 소수 1자리 | `62.4` |
| 금액 | 천단위 구분 + 억 병기 | `768,200,000 원 (7.68억)` |
| 차압 | 소수 2자리 + `kPa` | `3.82 kPa` |
| 온도 | 소수 1자리 + `℃` | `112.4 ℃` |
| 출력 | 소수 1자리 + `MW` | `148.2 MW` |
| 비율 | 소수 1자리 + `%` | `59.4 %` |
| 날짜 | `YYYY-MM-DD` | `2025-09-20` |
| 일시 | `YYYY-MM-DD HH:mm` | `2025-09-20 14:02` |
| D-day | `D-84` / `이미 도달` / `예측 불가` | |
| 없음 | `–` (하이픈), `0`과 구분 | |

## 8. 등급 표현 (`utils/constants.js`)
```js
export const GRADE = {
  NORMAL:  { label: '정상', variant: 'success', range: 'FI < 30' },
  CAUTION: { label: '주의', variant: 'warning', range: '30 ≤ FI < 60' },
  WARNING: { label: '경고', variant: 'danger',  range: 'FI ≥ 60' },
}
```
- 색상만으로 정보를 전달하지 않고 항상 텍스트 라벨을 함께 표시한다.

## 9. 접근성·품질
- 모든 입력에 `<label>` 연결, 버튼에 명확한 텍스트(아이콘 단독 버튼은 `aria-label`).
- 키보드만으로 로그인 → 업로드 → 분석 실행 → 리포트 다운로드가 가능해야 한다.
- 차트는 대체 텍스트와 함께 데이터 표를 제공(접이식)한다.
- 텍스트 대비 WCAG AA 준수.

## 10. 빌드·배포
- `npm run build` → `dist/`
- API 프록시: 개발 시 `vite.config.js`의 `server.proxy`로 `/api` → `http://localhost:8000`
- 운영은 Django가 `dist/`를 정적 서빙하거나 Nginx가 SPA + 리버스 프록시를 담당(`18-nonfunctional.md`).
- SPA history 모드이므로 서버에 `index.html` 폴백 설정이 필요하다.

## 11. 수용 기준 (AC)
- [ ] AC-16-1: 비로그인 상태로 임의 경로 접근 시 로그인으로 이동하고, 로그인 후 원래 경로로 복귀한다.
- [ ] AC-16-2: 일반 사용자에게 관리자 메뉴가 보이지 않고, 직접 URL 접근도 차단된다.
- [ ] AC-16-3: 호기 선택이 페이지 이동·새로고침 후에도 유지된다.
- [ ] AC-16-4: 분석 실행 중 페이지를 이동했다 돌아와도 진행 상태가 복원된다.
- [ ] AC-16-5: 모든 금액·지수 표기가 공통 포맷터를 통해 일관되게 표시된다.
