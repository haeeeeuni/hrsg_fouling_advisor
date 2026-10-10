/** 로그인 상태 스토어 (specs/11 §5). */
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import * as authApi from '@/api/auth'

export const useAuthStore = defineStore('auth', () => {
  const user = ref(null)
  /** 부팅 시 GET /auth/me/ 로 세션을 복원했는지 여부 (라우터 가드가 이 값을 본다) */
  const initialized = ref(false)

  const isAuthenticated = computed(() => user.value !== null)
  const isAdmin = computed(() => user.value?.is_admin === true)
  const mustChangePassword = computed(() => user.value?.must_change_password === true)

  async function fetchMe() {
    try {
      const { data } = await authApi.fetchMe()
      user.value = data.authenticated ? data.user : null
    } catch {
      // 서버에 닿지 않아도 앱은 떠야 한다 — 비로그인으로 시작한다(specs/13 NFR-4).
      user.value = null
    } finally {
      initialized.value = true
    }
    return user.value
  }

  async function login(credentials) {
    // CSRF 쿠키를 먼저 받아야 POST 가 통과한다.
    await authApi.fetchCsrf()
    const { data } = await authApi.login(credentials)
    user.value = data.user
    initialized.value = true
    return data.user
  }

  async function signup(payload) {
    await authApi.fetchCsrf()
    const { data } = await authApi.signup(payload)
    return data
  }

  async function logout() {
    try {
      await authApi.logout()
    } finally {
      user.value = null
    }
  }

  async function updateProfile(payload) {
    const { data } = await authApi.updateMe(payload)
    user.value = data.user
    return data.user
  }

  async function changePassword(payload) {
    await authApi.changePassword(payload)
    if (user.value) user.value = { ...user.value, must_change_password: false }
  }

  /** 401 인터셉터에서 호출한다. 서버 요청 없이 로컬 상태만 비운다. */
  function clear() {
    user.value = null
  }

  return {
    user,
    initialized,
    isAuthenticated,
    isAdmin,
    mustChangePassword,
    fetchMe,
    login,
    signup,
    logout,
    updateProfile,
    changePassword,
    clear,
  }
})
