/** 관리자 — 사용자·가입 승인·로그인 이력·감사 로그 API (specs/10 §6). */
import client from './client'

export function fetchOverview() {
  return client.get('/admin/overview/')
}

export function fetchUsers(params = {}) {
  return client.get('/admin/users/', { params })
}

export function updateUser(id, payload) {
  return client.patch(`/admin/users/${id}/`, payload)
}

/** 기본은 비활성화. hard=true 면 물리 삭제. */
export function deleteUser(id, hard = false) {
  return client.delete(`/admin/users/${id}/${hard ? '?hard=true' : ''}`)
}

export function approveUser(id) {
  return client.post(`/admin/users/${id}/approve/`)
}

export function rejectUser(id, reason) {
  return client.post(`/admin/users/${id}/reject/`, { reason })
}

export function resetPassword(id, newPassword) {
  return client.post(`/admin/users/${id}/reset-password/`, { new_password: newPassword })
}

export function fetchLoginHistories(params = {}) {
  return client.get('/admin/login-histories/', { params })
}

export function fetchAuditLogs(params = {}) {
  return client.get('/admin/audit-logs/', { params })
}
