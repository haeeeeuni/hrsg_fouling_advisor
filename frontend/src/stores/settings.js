/** 유효 설정값 스토어 (specs/16 §5). */
import { defineStore } from 'pinia'
import { ref } from 'vue'

import * as api from '@/api/settings'

export const useSettingsStore = defineStore('settings', () => {
  const effective = ref({})
  const loadedUnitId = ref(null)
  const loading = ref(false)

  /** 호기가 바뀌면 무효화하고 다시 읽는다. */
  async function fetchEffective(unitId, force = false) {
    if (!force && loadedUnitId.value === unitId && Object.keys(effective.value).length) {
      return effective.value
    }
    loading.value = true
    try {
      const { data } = await api.fetchEffective(unitId)
      effective.value = data.settings
      loadedUnitId.value = unitId
    } finally {
      loading.value = false
    }
    return effective.value
  }

  function get(key, fallback = null) {
    return effective.value[key] ?? fallback
  }

  function invalidate() {
    loadedUnitId.value = null
  }

  return { effective, loadedUnitId, loading, fetchEffective, get, invalidate }
})
