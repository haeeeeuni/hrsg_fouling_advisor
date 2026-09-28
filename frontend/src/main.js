import 'bootstrap/dist/css/bootstrap.min.css'
import 'bootstrap-icons/font/bootstrap-icons.css'
import '@/assets/styles/adminhmd-theme.css'
import '@/assets/styles/main.css'

/*
 * 드롭다운(네비 계정 메뉴·알림 벨)은 data-bs-toggle="dropdown" 으로 동작한다.
 * CSS 만 가져오면 마크업은 그려지지만 열리지 않는다 — 로그아웃에 접근할 수 없었다.
 * 번들 전체 대신 쓰는 것만 가져온다(Popper 는 dropdown 이 의존해 함께 들어온다).
 */
import 'bootstrap/js/dist/dropdown'

import { createPinia } from 'pinia'
import { createApp } from 'vue'

import App from './App.vue'
import { setUnauthorizedHandler } from '@/api/client'
import router from '@/router'
import { useAuthStore } from '@/stores/auth'

const app = createApp(App)
app.use(createPinia())
app.use(router)

// 401 이 오면 로컬 인증 상태를 비우고 로그인으로 보낸다 (specs/16 §6).
setUnauthorizedHandler(() => {
  useAuthStore().clear()
  const current = router.currentRoute.value
  if (current.name !== 'login') {
    router.replace({ name: 'login', query: { redirect: current.fullPath } })
  }
})

app.mount('#app')
