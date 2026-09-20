/** 세정 이력 API (specs/15 §7). */
import client from './client'

export function fetchCleaningEvents(params = {}) {
  return client.get('/cleaning-events/', { params })
}

export function createCleaningEvent(payload) {
  return client.post('/cleaning-events/', payload)
}

export function updateCleaningEvent(id, payload) {
  return client.patch(`/cleaning-events/${id}/`, payload)
}

export function deleteCleaningEvent(id) {
  return client.delete(`/cleaning-events/${id}/`)
}

// --- 정비 이력 (specs/15 §7) ---

export function uploadMaintenance({ unitId, file, sheet }) {
  const form = new FormData()
  form.append('unit_id', unitId)
  form.append('file', file)
  if (sheet) form.append('sheet', sheet)
  return client.post('/uploads/maintenance/', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export function fetchMaintenanceRecords(params = {}) {
  return client.get('/maintenance-records/', { params })
}

/** 세정 이벤트로 등록 — 승인 전에는 등록되지 않는다. */
export function acceptRecord(id, payload = {}) {
  return client.post(`/maintenance-records/${id}/accept/`, payload)
}

export function ignoreRecord(id) {
  return client.post(`/maintenance-records/${id}/ignore/`)
}

export function reExtract(unitId) {
  return client.post('/maintenance-records/re-extract/', { unit_id: unitId })
}

// --- 오염 키워드 사전 (관리자) ---

export function fetchKeywords(params = {}) {
  return client.get('/fouling-keywords/', { params })
}

export function createKeyword(payload) {
  return client.post('/fouling-keywords/', payload)
}

export function updateKeyword(id, payload) {
  return client.patch(`/fouling-keywords/${id}/`, payload)
}

export function deleteKeyword(id) {
  return client.delete(`/fouling-keywords/${id}/`)
}

export function restoreDefaultKeywords() {
  return client.post('/fouling-keywords/restore-defaults/')
}

// --- 세정 전후 비교 (specs/15 §8) ---

export function createComparison(payload) {
  return client.post('/comparisons/', payload)
}

export function fetchComparisons(params = {}) {
  return client.get('/comparisons/', { params })
}

export function fetchComparison(id) {
  return client.get(`/comparisons/${id}/`)
}
