/**
 * 화면 공통 상태 — 테마와 헤더 로그인 패널 (specs/11 §3, specs/12 §2.1).
 *
 * 테마: 저장된 선택이 없으면 OS 설정(prefers-color-scheme)을 따른다. 사용자가 토글하면
 * localStorage 에 남긴다. 저장소를 못 쓰는 환경(사생활 보호 모드 등)에서도 동작해야 하므로
 * 읽기·쓰기를 모두 try/catch 로 감싼다. index.html 의 인라인 스크립트가 같은 키를 읽어
 * 첫 렌더 전에 테마를 적용한다(깜빡임 방지) — 키 이름을 바꾸면 거기도 바꾼다.
 */
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

export const THEME_STORAGE_KEY = 'hrsg.theme'

function readStoredTheme() {
  try {
    const value = window.localStorage.getItem(THEME_STORAGE_KEY)
    return value === 'light' || value === 'dark' ? value : null
  } catch {
    return null
  }
}

function systemPrefersDark() {
  try {
    return window.matchMedia('(prefers-color-scheme: dark)').matches
  } catch {
    return false
  }
}

export const useUiStore = defineStore('ui', () => {
  /** 사용자가 고른 테마. null 이면 OS 설정을 따른다. */
  const chosenTheme = ref(readStoredTheme())
  const systemDark = ref(systemPrefersDark())

  const theme = computed(() => chosenTheme.value ?? (systemDark.value ? 'dark' : 'light'))

  function applyTheme() {
    document.documentElement.setAttribute('data-bs-theme', theme.value)
  }

  function toggleTheme() {
    chosenTheme.value = theme.value === 'dark' ? 'light' : 'dark'
    try {
      window.localStorage.setItem(THEME_STORAGE_KEY, chosenTheme.value)
    } catch {
      // 저장하지 못해도 이번 방문에서는 바뀐 테마가 유지된다.
    }
    applyTheme()
  }

  /** OS 설정 변화를 따라간다. 사용자가 직접 고른 뒤에는 그 선택이 우선한다. */
  function watchSystemTheme() {
    try {
      const query = window.matchMedia('(prefers-color-scheme: dark)')
      query.addEventListener('change', (event) => {
        systemDark.value = event.matches
        applyTheme()
      })
    } catch {
      // matchMedia 가 없는 환경 — OS 연동 없이 동작한다.
    }
  }

  // --- 헤더 로그인 패널 ---
  const loginOpen = ref(false)
  /** 로그인 후 돌아갈 경로. 보호 경로에 비로그인으로 들어왔을 때 채운다. */
  const loginRedirect = ref(null)

  function openLogin(redirect = null) {
    loginRedirect.value = redirect
    loginOpen.value = true
  }

  function closeLogin() {
    loginOpen.value = false
  }

  return {
    chosenTheme,
    theme,
    applyTheme,
    toggleTheme,
    watchSystemTheme,
    loginOpen,
    loginRedirect,
    openLogin,
    closeLogin,
  }
})
