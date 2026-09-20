/** 인증 API 모듈 (specs/15 §2). */
import client from './client'

export function fetchCsrf() {
  return client.get('/auth/csrf/')
}

export function login({ fullName, employeeNo, password }) {
  return client.post('/auth/login/', {
    full_name: fullName,
    employee_no: employeeNo,
    password,
  })
}

export function logout() {
  return client.post('/auth/logout/')
}

export function fetchMe() {
  return client.get('/auth/me/')
}

export function changePassword({ currentPassword, newPassword }) {
  return client.post('/auth/change-password/', {
    current_password: currentPassword,
    new_password: newPassword,
  })
}
