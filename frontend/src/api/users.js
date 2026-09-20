/** 사용자 관리 API (specs/15 §3). */
import client from './client'

export function fetchUsers(params = {}) {
  return client.get('/users/', { params })
}

export function createUser(payload) {
  return client.post('/users/', payload)
}

export function updateUser(id, payload) {
  return client.patch(`/users/${id}/`, payload)
}

/** 기본은 비활성화. hard=true 면 물리 삭제(이력 없는 계정만). */
export function deleteUser(id, hard = false) {
  return client.delete(`/users/${id}/${hard ? '?hard=true' : ''}`)
}

export function resetPassword(id, newPassword) {
  return client.post(`/users/${id}/reset-password/`, { new_password: newPassword })
}

export function fetchLoginHistories(params = {}) {
  return client.get('/login-histories/', { params })
}

export function fetchAuditLogs(params = {}) {
  return client.get('/audit-logs/', { params })
}
