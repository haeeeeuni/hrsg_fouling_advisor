import 'bootstrap/dist/css/bootstrap.min.css'
import 'bootstrap-icons/font/bootstrap-icons.css'
import '@/assets/styles/adminhmd-theme.css'
import '@/assets/styles/main.css'

/*
 * Bootstrap JS 는 쓰는 것만 가져온다.
 * - dropdown : 헤더 사용자 메뉴 (data-bs-toggle="dropdown")
 * - collapse : 모바일 헤더의 기능 메뉴 접기
 * - offcanvas: 모바일 관리자 메뉴
 * CSS 만 가져오면 마크업은 그려지지만 열리지 않는다(이전 앱에서 로그아웃에 접근하지 못했다).
 */
import 'bootstrap/js/dist/dropdown'
import 'bootstrap/js/dist/collapse'
import 'bootstrap/js/dist/offcanvas'

import { createPinia } from 'pinia'
import { createApp } from 'vue'

import App from './App.vue'
import { setUnauthorizedHandler } from '@/api/client'
import router from '@/router'
import { useAuthStore } from '@/stores/auth'
import { useUiStore } from '@/stores/ui'

const app = createApp(App)
app.use(createPinia())
app.use(router)

const ui = useUiStore()
ui.applyTheme()
ui.watchSystemTheme()

// 세션이 끊긴 채 API 를 부르면 소개 화면으로 보내고 로그인 패널을 연다 (specs/11 §1).
setUnauthorizedHandler(() => {
  useAuthStore().clear()
  const current = router.currentRoute.value
  ui.openLogin(current.fullPath)
  if (current.meta.requiresAuth) router.replace({ name: 'intro' })
})

app.mount('#app')
