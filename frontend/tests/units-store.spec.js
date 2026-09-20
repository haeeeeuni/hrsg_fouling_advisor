import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/api/units', () => ({
  fetchUnits: vi.fn(),
}))

import { fetchUnits as fetchUnitsApi } from '@/api/units'
import { useUnitsStore } from '@/stores/units'

const UNITS = [
  { id: 1, code: 'U1', name: '1호기', is_active: true, is_mapping_complete: true },
  { id: 2, code: 'U2', name: '2호기', is_active: true, is_mapping_complete: false },
  { id: 3, code: 'U3', name: '3호기', is_active: false, is_mapping_complete: true },
]

describe('units store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    fetchUnitsApi.mockReset()
    fetchUnitsApi.mockResolvedValue({ data: { results: UNITS } })
  })

  it('활성 호기만 activeUnits 에 들어간다', async () => {
    const store = useUnitsStore()
    await store.fetchUnits()

    expect(store.activeUnits.map((u) => u.id)).toEqual([1, 2])
  })

  it('업로드 가능 호기는 활성 + 매핑 완료만 포함한다', async () => {
    const store = useUnitsStore()
    await store.fetchUnits()

    expect(store.uploadableUnits.map((u) => u.id)).toEqual([1])
  })

  it('선택된 호기가 없으면 첫 활성 호기를 고른다', async () => {
    const store = useUnitsStore()
    await store.fetchUnits()

    expect(store.selectedUnitId).toBe(1)
    expect(store.selectedUnit.code).toBe('U1')
  })

  it('AC-16-3: 호기 선택이 localStorage 에 보존된다', async () => {
    const store = useUnitsStore()
    await store.fetchUnits()
    store.selectUnit(2)

    expect(localStorage.getItem('hrsg.selectedUnitId')).toBe('2')

    // 새 스토어(새로고침 상황)에서도 복원된다.
    setActivePinia(createPinia())
    const reloaded = useUnitsStore()
    expect(reloaded.selectedUnitId).toBe(2)
  })

  it('저장된 호기가 사라지면 첫 활성 호기로 대체한다', async () => {
    localStorage.setItem('hrsg.selectedUnitId', '99')
    setActivePinia(createPinia())
    const store = useUnitsStore()

    await store.fetchUnits()

    expect(store.selectedUnitId).toBe(1)
  })

  it('두 번째 호출은 서버를 다시 부르지 않는다', async () => {
    const store = useUnitsStore()
    await store.fetchUnits()
    await store.fetchUnits()

    expect(fetchUnitsApi).toHaveBeenCalledTimes(1)
  })

  it('invalidate 후에는 다시 조회한다', async () => {
    const store = useUnitsStore()
    await store.fetchUnits()
    store.invalidate()
    await store.fetchUnits()

    expect(fetchUnitsApi).toHaveBeenCalledTimes(2)
  })
})
