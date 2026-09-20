/** 라우트 정의 + 인증/권한 가드 (specs/16 §3). */
import { createRouter, createWebHistory } from 'vue-router'

import { useToast } from '@/composables/useToast'
import { useAuthStore } from '@/stores/auth'

const routes = [
  { path: '/login', name: 'login', component: () => import('@/views/LoginView.vue') },
  { path: '/', redirect: '/dashboard' },
  {
    path: '/dashboard',
    name: 'dashboard',
    component: () => import('@/views/DashboardView.vue'),
    meta: { requiresAuth: true, title: '대시보드' },
  },
  {
    path: '/upload',
    name: 'upload',
    component: () => import('@/views/UploadView.vue'),
    meta: { requiresAuth: true, title: '데이터 업로드' },
  },
  {
    path: '/analysis/new',
    name: 'analysis-run',
    component: () => import('@/views/AnalysisRunView.vue'),
    meta: { requiresAuth: true, title: '분석 실행' },
  },
  {
    path: '/maintenance',
    name: 'maintenance',
    component: () => import('@/views/MaintenanceView.vue'),
    meta: { requiresAuth: true, title: '정비 이력' },
  },
  {
    path: '/comparison',
    name: 'comparison',
    component: () => import('@/views/ComparisonView.vue'),
    meta: { requiresAuth: true, title: '세정 전후 비교' },
  },
  {
    path: '/reports',
    name: 'reports',
    component: () => import('@/views/ReportsView.vue'),
    meta: { requiresAuth: true, title: '리포트' },
  },
  {
    path: '/profile',
    name: 'profile',
    component: () => import('@/views/ProfileView.vue'),
    meta: { requiresAuth: true, title: '내 정보' },
  },
  {
    path: '/admin',
    component: () => import('@/views/admin/AdminLayout.vue'),
    meta: { requiresAuth: true, requiresAdmin: true },
    children: [
      { path: '', redirect: { name: 'admin-units' } },
      {
        path: 'units',
        name: 'admin-units',
        component: () => import('@/views/admin/UnitsView.vue'),
        meta: { requiresAuth: true, requiresAdmin: true, title: '호기 관리' },
      },
      {
        path: 'column-mapping',
        name: 'admin-column-mapping',
        component: () => import('@/views/admin/ColumnMappingView.vue'),
        meta: { requiresAuth: true, requiresAdmin: true, title: '컬럼 매핑' },
      },
      {
        path: 'keywords',
        name: 'admin-keywords',
        component: () => import('@/views/admin/KeywordsView.vue'),
        meta: { requiresAuth: true, requiresAdmin: true, title: '오염 키워드' },
      },
      {
        path: 'cleaning-events',
        name: 'admin-cleaning-events',
        component: () => import('@/views/admin/CleaningEventsView.vue'),
        meta: { requiresAuth: true, requiresAdmin: true, title: '세정 이력' },
      },
    ],
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    component: () => import('@/views/NotFoundView.vue'),
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()

  // 1. 스토어가 초기화되지 않았으면 세션을 복원한다.
  if (!auth.initialized) {
    await auth.fetchMe()
  }

  // 2. 인증이 필요한데 미인증이면 로그인으로 보내되 원래 경로를 보존한다.
  if (to.meta.requiresAuth && !auth.isAuthenticated) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }

  // 3. 관리자 전용 라우트는 서버 권한과 별개로 UX 차원에서 막는다(서버에서 재검증됨).
  if (to.meta.requiresAdmin && !auth.isAdmin) {
    useToast().push('권한이 없습니다.', 'danger')
    return { name: 'dashboard' }
  }

  // 4. 이미 로그인한 사용자가 로그인 페이지로 가면 대시보드로 돌린다.
  if (to.name === 'login' && auth.isAuthenticated) {
    return { name: 'dashboard' }
  }

  return true
})

export default router
