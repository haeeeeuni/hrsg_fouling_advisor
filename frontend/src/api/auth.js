/** 인증·가입 API 모듈 (specs/10 §2). */
import client from './client'

export function fetchCsrf() {
  return client.get('/auth/csrf/')
}

export function signup(payload) {
  return client.post('/auth/signup/', {
    username: payload.username,
    password: payload.password,
    password_confirm: payload.passwordConfirm,
    full_name: payload.fullName,
    organization: payload.organization,
    email: payload.email,
    signup_reason: payload.signupReason,
  })
}

export function checkUsername(username) {
  return client.get('/auth/username-available/', { params: { username } })
}

export function login({ username, password }) {
  return client.post('/auth/login/', { username, password })
}

export function logout() {
  return client.post('/auth/logout/')
}

/** 공개 엔드포인트 — 로그인하지 않았으면 { authenticated: false, user: null } */
export function fetchMe() {
  return client.get('/auth/me/')
}

export function updateMe({ fullName, organization, email }) {
  return client.patch('/auth/me/', { full_name: fullName, organization, email })
}

export function changePassword({ currentPassword, newPassword }) {
  return client.post('/auth/password/', {
    current_password: currentPassword,
    new_password: newPassword,
  })
}
