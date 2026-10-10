/** 관리자 — 설정값 API (specs/10 §6, specs/08 ADM-4). */
import client from './client'

export function fetchSettings(params = {}) {
  return client.get('/admin/settings/', { params })
}

export function patchSettings(updates) {
  return client.patch('/admin/settings/', updates)
}

export function resetSetting(key) {
  return client.post(`/admin/settings/${key}/reset/`)
}
