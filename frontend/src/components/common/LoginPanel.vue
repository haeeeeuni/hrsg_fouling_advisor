<script setup>
/**
 * 상단 우측 로그인 (specs/01 AUTH-6, specs/11 §3).
 *
 * Bootstrap 드롭다운 대신 Vue 상태(ui.loginOpen)로 연다 — 보호 경로에 비로그인으로 들어왔을 때
 * 라우터 가드가 코드로 열어야 하기 때문이다. 데스크톱은 버튼 아래 패널, 모바일은 화면 상단 시트.
 */
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { useAuthStore } from '@/stores/auth'
import { useUiStore } from '@/stores/ui'

const auth = useAuthStore()
const ui = useUiStore()
const router = useRouter()

const root = ref(null)
const usernameInput = ref(null)
const form = ref({ username: '', password: '' })
const submitting = ref(false)
const error = ref(null)

watch(
  () => ui.loginOpen,
  async (open) => {
    if (!open) return
    error.value = null
    await nextTick()
    usernameInput.value?.focus()
  },
)

function onDocumentClick(event) {
  if (ui.loginOpen && root.value && !root.value.contains(event.target)) ui.closeLogin()
}

function onKeydown(event) {
  if (event.key === 'Escape' && ui.loginOpen) ui.closeLogin()
}

onMounted(() => {
  document.addEventListener('mousedown', onDocumentClick)
  document.addEventListener('keydown', onKeydown)
})
onBeforeUnmount(() => {
  document.removeEventListener('mousedown', onDocumentClick)
  document.removeEventListener('keydown', onKeydown)
})

async function onSubmit() {
  if (submitting.value) return // 중복 클릭 방지
  submitting.value = true
  error.value = null
  try {
    await auth.login({ username: form.value.username, password: form.value.password })
    const redirect = ui.loginRedirect
    ui.closeLogin()
    form.value = { username: '', password: '' }
    await router.replace(redirect || { name: 'home' })
  } catch (err) {
    error.value = err.parsed ?? { code: 'NETWORK_ERROR', message: '로그인에 실패했습니다.', details: {} }
  } finally {
    submitting.value = false
  }
}

function goSignup() {
  ui.closeLogin()
  router.push({ name: 'signup' })
}
</script>

<template>
  <div ref="root" class="ui-login">
    <button
      type="button"
      class="btn btn-primary btn-sm"
      :aria-expanded="ui.loginOpen ? 'true' : 'false'"
      aria-controls="loginPanel"
      @click="ui.loginOpen ? ui.closeLogin() : ui.openLogin()"
    >
      <i class="bi bi-box-arrow-in-right me-1" aria-hidden="true"></i>로그인
    </button>

    <div
      v-if="ui.loginOpen"
      id="loginPanel"
      class="ui-login-panel card"
      role="dialog"
      aria-modal="false"
      aria-labelledby="loginTitle"
    >
      <div class="card-body">
        <h2 id="loginTitle" class="h6 mb-3">로그인</h2>
        <form novalidate @submit.prevent="onSubmit">
          <div class="mb-2">
            <label for="loginUsername" class="form-label">ID</label>
            <input
              id="loginUsername"
              ref="usernameInput"
              v-model.trim="form.username"
              type="text"
              class="form-control"
              autocomplete="username"
              autocapitalize="off"
              spellcheck="false"
              required
            />
          </div>
          <div class="mb-3">
            <label for="loginPassword" class="form-label">비밀번호</label>
            <input
              id="loginPassword"
              v-model="form.password"
              type="password"
              class="form-control"
              autocomplete="current-password"
              required
            />
          </div>

          <div
            v-if="error"
            class="alert py-2 small"
            :class="error.code === 'ACCOUNT_PENDING' ? 'alert-warning' : 'alert-danger'"
            role="alert"
          >
            {{ error.message }}
            <div v-if="error.details?.retry_after_sec" class="mt-1">
              {{ Math.ceil(error.details.retry_after_sec / 60) }}분 후 다시 시도할 수 있습니다.
            </div>
          </div>

          <button class="btn btn-primary w-100" type="submit" :disabled="submitting">
            <span v-if="submitting" class="spinner-border spinner-border-sm me-2" aria-hidden="true"></span>
            로그인
          </button>
        </form>

        <p class="small text-secondary mt-3 mb-0">
          계정이 없나요?
          <button type="button" class="btn btn-link btn-sm p-0 align-baseline" @click="goSignup">
            회원가입
          </button>
          후 관리자 승인을 받으면 로그인할 수 있습니다.
        </p>
      </div>
    </div>
  </div>
</template>
