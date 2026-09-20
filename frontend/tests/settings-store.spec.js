import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/api/settings', () => ({
  fetchEffective: vi.fn(),
}))

import { fetchEffective } from '@/api/settings'
import { useSettingsStore } from '@/stores/settings'

const SETTINGS = { fouling_threshold: 60, weight_dp: 0.6, grade_caution_min: 30 }

describe('settings store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    fetchEffective.mockResolvedValue({ data: { unit_id: 1, settings: SETTINGS } })
  })

  it('유효 설정값을 불러온다', async () => {
    const store = useSettingsStore()

    await store.fetchEffective(1)

    expect(store.effective.fouling_threshold).toBe(60)
    expect(fetchEffective).toHaveBeenCalledWith(1)
  })

  it('같은 호기는 다시 부르지 않는다', async () => {
    const store = useSettingsStore()
    await store.fetchEffective(1)
    await store.fetchEffective(1)

    expect(fetchEffective).toHaveBeenCalledTimes(1)
  })

  it('호기가 바뀌면 다시 부른다', async () => {
    const store = useSettingsStore()
    await store.fetchEffective(1)
    await store.fetchEffective(2)

    expect(fetchEffective).toHaveBeenCalledTimes(2)
  })

  it('invalidate 후에는 다시 부른다', async () => {
    const store = useSettingsStore()
    await store.fetchEffective(1)
    store.invalidate()
    await store.fetchEffective(1)

    expect(fetchEffective).toHaveBeenCalledTimes(2)
  })

  it('get 은 없는 키에 대해 fallback 을 돌려준다', async () => {
    const store = useSettingsStore()
    await store.fetchEffective(1)

    expect(store.get('weight_dp')).toBe(0.6)
    expect(store.get('no_such_key', 42)).toBe(42)
  })

  it('0 도 값으로 취급한다', async () => {
    fetchEffective.mockResolvedValue({ data: { settings: { discount_rate_annual: 0 } } })
    const store = useSettingsStore()
    await store.fetchEffective(1)

    expect(store.get('discount_rate_annual', 99)).toBe(0)
  })
})
