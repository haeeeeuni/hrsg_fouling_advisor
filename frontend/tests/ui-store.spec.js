import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { THEME_STORAGE_KEY, useUiStore } from '@/stores/ui'

function mockSystemDark(dark) {
  window.matchMedia = vi.fn(() => ({
    matches: dark,
    addEventListener: vi.fn(),
  }))
}

describe('ui 스토어 — 테마 (specs/12 UI-5)', () => {
  beforeEach(() => {
    window.localStorage.clear()
    document.documentElement.removeAttribute('data-bs-theme')
    mockSystemDark(false)
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('저장된 선택이 없으면 OS 설정을 따른다', () => {
    mockSystemDark(true)
    setActivePinia(createPinia())
    const ui = useUiStore()

    ui.applyTheme()

    expect(ui.theme).toBe('dark')
    expect(document.documentElement.getAttribute('data-bs-theme')).toBe('dark')
  })

  it('토글하면 문서에 적용하고 저장한다', () => {
    setActivePinia(createPinia())
    const ui = useUiStore()

    ui.toggleTheme()

    expect(ui.theme).toBe('dark')
    expect(document.documentElement.getAttribute('data-bs-theme')).toBe('dark')
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe('dark')
  })

  it('저장된 선택이 OS 설정보다 우선한다 — 새로고침 후에도 유지된다', () => {
    window.localStorage.setItem(THEME_STORAGE_KEY, 'light')
    mockSystemDark(true)
    setActivePinia(createPinia())

    expect(useUiStore().theme).toBe('light')
  })

  it('저장소를 쓸 수 없어도 토글은 동작한다', () => {
    setActivePinia(createPinia())
    const ui = useUiStore()
    vi.spyOn(window.localStorage, 'setItem').mockImplementation(() => {
      throw new Error('blocked')
    })

    expect(() => ui.toggleTheme()).not.toThrow()
    expect(ui.theme).toBe('dark')
  })

  it('알 수 없는 저장값은 무시한다', () => {
    window.localStorage.setItem(THEME_STORAGE_KEY, 'purple')
    setActivePinia(createPinia())

    expect(useUiStore().chosenTheme).toBeNull()
  })
})

describe('ui 스토어 — 로그인 패널', () => {
  it('열 때 돌아갈 경로를 기억한다', () => {
    setActivePinia(createPinia())
    const ui = useUiStore()

    ui.openLogin('/calculator')

    expect(ui.loginOpen).toBe(true)
    expect(ui.loginRedirect).toBe('/calculator')

    ui.closeLogin()
    expect(ui.loginOpen).toBe(false)
  })
})
