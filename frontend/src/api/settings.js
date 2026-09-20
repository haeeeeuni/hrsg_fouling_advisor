/** 설정 관리 API (specs/15 §10). */
import client from './client'

export function fetchSettings(params = {}) {
  return client.get('/settings/', { params })
}

export function patchSettings(updates) {
  return client.patch('/settings/', updates)
}

export function restoreDefaults({ category, keys }) {
  return client.post('/settings/restore-defaults/', { category, keys })
}

/** 해당 호기에 실제 적용되는 최종값 (인증 사용자) */
export function fetchEffective(unitId) {
  return client.get('/settings/effective/', { params: unitId ? { unit_id: unitId } : {} })
}

export function fetchUnitSettings(unitId) {
  return client.get(`/units/${unitId}/settings/`)
}

export function saveUnitSettings(unitId, updates) {
  return client.put(`/units/${unitId}/settings/`, updates)
}

export function clearUnitSetting(unitId, key) {
  return client.delete(`/units/${unitId}/settings/${key}/`)
}
