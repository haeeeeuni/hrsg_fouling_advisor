/** 라우트 정의 + 인증/권한 가드 (specs/11 §1). */
import { createRouter, createWebHistory } from 'vue-router'

import { useToast } from '@/composables/useToast'
import { useAuthStore } from '@/stores/auth'
import { useUiStore } from '@/stores/ui'
import { FEATURES } from '@/utils/constants'

const featureRoutes = FEATURES.map((feature) => ({
  // 기능 화면은 해당 마일스톤에서 실제 화면으로 바뀐다. 그 전까지는 준비 중 안내를 보인다.
  path: `/${feature.key}/:rest(.*)*`,
  name: feature.route,
  component: () => import('@/views/ComingSoonView.vue'),
  props: { feature },
  meta: { requiresAuth: true, title: feature.title },
}))

/** 관리자 모드 메뉴 (specs/08 §2). 마일스톤마다 메뉴가 늘어난다. AdminLayout 이 이 목록으로 사이드바를 그린다. */
export const ADMIN_MENU = [
  { path: '', name: 'admin-overview', title: '개요', icon: 'bi-speedometer2', view: 'OverviewView' },
  { path: 'signups', name: 'admin-signups', title: '가입 승인', icon: 'bi-person-check', view: 'SignupApprovalsView' },
  { path: 'users', name: 'admin-users', title: '사용자', icon: 'bi-people', view: 'UsersView' },
  { path: 'settings', name: 'admin-settings', title: '설정', icon: 'bi-sliders', view: 'SettingsView' },
  { path: 'audit-logs', name: 'admin-audit-logs', title: '감사 로그', icon: 'bi-journal-text', view: 'AuditLogView' },
]

// 동적 import 는 정적 문자열이어야 번들러가 청크를 나눈다. 메뉴 이름으로 고른다.
const ADMIN_VIEWS = {
  OverviewView: () => import('@/views/admin/OverviewView.vue'),
  SignupApprovalsView: () => import('@/views/admin/SignupApprovalsView.vue'),
  UsersView: () => import('@/views/admin/UsersView.vue'),
  SettingsView: () => import('@/views/admin/SettingsView.vue'),
  AuditLogView: () => import('@/views/admin/AuditLogView.vue'),
}

const adminRoutes = ADMIN_MENU.map((item) => ({
  path: item.path,
  name: item.name,
  component: ADMIN_VIEWS[item.view],
  meta: { title: item.title, requiresAuth: true, requiresAdmin: true },
}))

const routes = [
  { path: '/', name: 'intro', component: () => import('@/views/IntroView.vue') },
  {
    path: '/signup',
    name: 'signup',
    component: () => import('@/views/SignupView.vue'),
    meta: { guestOnly: true, title: '회원가입' },
  },
  {
    path: '/home',
    name: 'home',
    component: () => import('@/views/HomeView.vue'),
    meta: { requiresAuth: true, title: '홈' },
  },
  ...featureRoutes,
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
    children: adminRoutes,
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
  scrollBehavior: () => ({ top: 0 }),
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()

  // 1. 새로고침 직후에는 세션 복원이 끝날 때까지 기다린다 — 기다리지 않으면 로그인한 사용자가
  //    잠깐 비로그인으로 판정돼 소개 화면으로 튕긴다.
  if (!auth.initialized) {
    await auth.fetchMe()
  }

  // 2. 보호 경로에 비로그인으로 오면 소개 화면 + 로그인 패널. 로그인하면 원래 경로로 돌아간다.
  if (to.meta.requiresAuth && !auth.isAuthenticated) {
    useUiStore().openLogin(to.fullPath)
    return { name: 'intro' }
  }

  // 3. 관리자 전용 라우트는 서버 권한과 별개로 UX 차원에서 막는다(서버에서 재검증됨).
  if (to.meta.requiresAdmin && !auth.isAdmin) {
    useToast().push('관리자 권한이 필요합니다.', 'danger')
    return { name: 'home' }
  }

  // 4. 이미 로그인한 사용자는 회원가입 화면이 필요 없다.
  if (to.meta.guestOnly && auth.isAuthenticated) {
    return { name: 'home' }
  }

  return true
})

router.afterEach((to) => {
  const title = to.meta?.title
  document.title = title ? `${title} · HRSG 레퍼런스 앱` : 'HRSG 레퍼런스 앱'
})

export default router
