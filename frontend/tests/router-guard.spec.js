/** 라우터 가드 (specs/11 AC-11-1·AC-11-3). */
import { createPinia, setActivePinia } from 'pinia'
import { describe, expect, it, vi } from 'vitest'

vi.mock('@/api/auth', () => ({
  fetchMe: vi.fn(),
  fetchCsrf: vi.fn(),
}))

import * as authApi from '@/api/auth'
import router from '@/router'
import { useUiStore } from '@/stores/ui'

/**
 * 라우터는 모듈 싱글턴이지만 가드는 호출 시점의 활성 pinia 에서 스토어를 꺼낸다.
 * 새 pinia 를 주면 세션 복원부터 다시 하는 '새로고침 직후' 상태가 된다.
 */
async function freshRouter(user) {
  setActivePinia(createPinia())
  authApi.fetchMe.mockResolvedValue({ data: { authenticated: Boolean(user), user } })
  return router
}

describe('라우터 가드', () => {
  it('비로그인으로 보호 경로에 오면 소개 화면 + 로그인 패널, 돌아갈 경로를 기억한다', async () => {
    const router = await freshRouter(null)

    await router.push('/calculator')

    expect(router.currentRoute.value.name).toBe('intro')
    const ui = useUiStore()
    expect(ui.loginOpen).toBe(true)
    expect(ui.loginRedirect).toBe('/calculator')
  })

  it('일반 사용자는 관리자 모드에 들어갈 수 없다', async () => {
    const router = await freshRouter({ id: 2, username: 'hong', is_admin: false })

    await router.push('/admin/users')

    expect(router.currentRoute.value.name).toBe('home')
  })

  it('관리자는 관리자 모드에 들어간다', async () => {
    const router = await freshRouter({ id: 1, username: 'admin', is_admin: true })

    await router.push('/admin/users')

    expect(router.currentRoute.value.name).toBe('admin-users')
  })

  it('로그인한 사용자는 회원가입 화면 대신 홈으로 간다', async () => {
    const router = await freshRouter({ id: 2, username: 'hong', is_admin: false })

    await router.push('/signup')

    expect(router.currentRoute.value.name).toBe('home')
  })

  it('소개 화면은 로그인 없이 열린다', async () => {
    const router = await freshRouter(null)

    await router.push('/')

    expect(router.currentRoute.value.name).toBe('intro')
    expect(useUiStore().loginOpen).toBe(false)
  })
})
