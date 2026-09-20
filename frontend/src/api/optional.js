/** 옵션 기능 API — 자동 재계산·백테스트·호기 간 비교·알림 (specs/19). */
import client from './client'

// --- 자동 재계산 (specs/19 §1) ---

export function fetchAutoRecalc(unitId) {
  return client.get(`/units/${unitId}/auto-recalc/`)
}

export function saveAutoRecalc(unitId, payload) {
  return client.put(`/units/${unitId}/auto-recalc/`, payload)
}

// --- 백테스트 (specs/19 §2) ---

export function fetchBacktests(params = {}) {
  return client.get('/backtests/', { params })
}

export function fetchBacktest(id) {
  return client.get(`/backtests/${id}/`)
}

/** 실행 → 202 + job_id. 완료는 useJobPolling 으로 감시한다. */
export function runBacktest({ unitId, lookaheadDays }) {
  return client.post('/backtests/', {
    unit_id: unitId,
    lookahead_days: lookaheadDays || undefined,
  })
}

/** 세정 1회 이하 호기는 메뉴를 비활성화한다 (AC-19-6). */
export function fetchBacktestAvailability() {
  return client.get('/backtests/availability/')
}

// --- 호기 간 비교 (specs/19 §3) ---

export function fetchUnitComparison(unitIds = []) {
  const params = unitIds.length ? { unit_ids: unitIds.join(',') } : {}
  return client.get('/units/comparison/', { params })
}

// --- 알림 (specs/19 §1.4) ---

export function fetchNotifications(params = {}) {
  return client.get('/notifications/', { params })
}

export function markNotificationRead(id) {
  return client.post(`/notifications/${id}/read/`)
}

export function markAllNotificationsRead() {
  return client.post('/notifications/read-all/')
}
