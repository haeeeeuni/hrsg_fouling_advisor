import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/api/auth', () => ({
  fetchCsrf: vi.fn(() => Promise.resolve({ data: {} })),
  fetchMe: vi.fn(),
  login: vi.fn(),
  logout: vi.fn(() => Promise.resolve({})),
  signup: vi.fn(),
  updateMe: vi.fn(),
  changePassword: vi.fn(() => Promise.resolve({})),
}))

import * as authApi from '@/api/auth'
import { useAuthStore } from '@/stores/auth'

const ADMIN = { id: 1, username: 'admin', full_name: '관리자', is_admin: true, must_change_password: true }

describe('auth 스토어', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('세션이 있으면 사용자를 복원한다', async () => {
    authApi.fetchMe.mockResolvedValue({ data: { authenticated: true, user: ADMIN } })
    const auth = useAuthStore()

    await auth.fetchMe()

    expect(auth.initialized).toBe(true)
    expect(auth.isAuthenticated).toBe(true)
    expect(auth.isAdmin).toBe(true)
    expect(auth.mustChangePassword).toBe(true)
  })

  it('비로그인 응답이면 사용자가 없다', async () => {
    authApi.fetchMe.mockResolvedValue({ data: { authenticated: false, user: null } })
    const auth = useAuthStore()

    await auth.fetchMe()

    expect(auth.initialized).toBe(true)
    expect(auth.isAuthenticated).toBe(false)
  })

  it('서버에 닿지 않아도 초기화는 끝난다 — 앱이 멈추지 않는다', async () => {
    authApi.fetchMe.mockRejectedValue(new Error('network'))
    const auth = useAuthStore()

    await auth.fetchMe()

    expect(auth.initialized).toBe(true)
    expect(auth.user).toBeNull()
  })

  it('로그인 전에 CSRF 쿠키를 받는다', async () => {
    authApi.login.mockResolvedValue({ data: { authenticated: true, user: ADMIN } })
    const auth = useAuthStore()

    await auth.login({ username: 'admin', password: 'x' })

    expect(authApi.fetchCsrf.mock.invocationCallOrder[0]).toBeLessThan(
      authApi.login.mock.invocationCallOrder[0],
    )
    expect(auth.user).toEqual(ADMIN)
  })

  it('가입 신청은 로그인 상태를 바꾸지 않는다', async () => {
    authApi.signup.mockResolvedValue({ data: { username: 'new.user', approval_status: 'PENDING' } })
    const auth = useAuthStore()

    const result = await auth.signup({ username: 'new.user' })

    expect(result.approval_status).toBe('PENDING')
    expect(auth.isAuthenticated).toBe(false)
  })

  it('비밀번호를 바꾸면 변경 요구 표시가 사라진다', async () => {
    const auth = useAuthStore()
    auth.user = { ...ADMIN }

    await auth.changePassword({ currentPassword: 'a', newPassword: 'b' })

    expect(auth.mustChangePassword).toBe(false)
  })

  it('로그아웃 요청이 실패해도 로컬 상태는 비운다', async () => {
    authApi.logout.mockRejectedValue(new Error('network'))
    const auth = useAuthStore()
    auth.user = { ...ADMIN }

    await expect(auth.logout()).rejects.toThrow()

    expect(auth.user).toBeNull()
  })
})
