/** 호기 목록과 전역 선택 상태 (specs/16 §4, §5). */
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import * as unitsApi from '@/api/units'

const STORAGE_KEY = 'hrsg.selectedUnitId'

function readStored() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? Number(raw) : null
  } catch {
    return null
  }
}

export const useUnitsStore = defineStore('units', () => {
  const list = ref([])
  const selectedUnitId = ref(readStored())
  const loading = ref(false)
  const loaded = ref(false)

  const selectedUnit = computed(
    () => list.value.find((u) => u.id === selectedUnitId.value) ?? null,
  )
  const activeUnits = computed(() => list.value.filter((u) => u.is_active))
  /** 업로드 가능한 호기 = 활성 + 매핑 완료 (specs/03 §2) */
  const uploadableUnits = computed(() => activeUnits.value.filter((u) => u.is_mapping_complete))

  async function fetchUnits(force = false) {
    if (loaded.value && !force) return list.value
    loading.value = true
    try {
      const { data } = await unitsApi.fetchUnits()
      list.value = data.results ?? data
      loaded.value = true
      // 선택된 호기가 사라졌거나 없으면 첫 활성 호기를 고른다.
      if (!list.value.some((u) => u.id === selectedUnitId.value)) {
        selectUnit(activeUnits.value[0]?.id ?? null)
      }
    } finally {
      loading.value = false
    }
    return list.value
  }

  function selectUnit(id) {
    selectedUnitId.value = id
    try {
      if (id) localStorage.setItem(STORAGE_KEY, String(id))
      else localStorage.removeItem(STORAGE_KEY)
    } catch {
      // 저장에 실패해도 세션 내 선택은 유지된다.
    }
  }

  /** 매핑 저장 등으로 호기 상태가 바뀐 뒤 목록을 무효화한다. */
  function invalidate() {
    loaded.value = false
  }

  return {
    list,
    selectedUnitId,
    selectedUnit,
    activeUnits,
    uploadableUnits,
    loading,
    loaded,
    fetchUnits,
    selectUnit,
    invalidate,
  }
})
