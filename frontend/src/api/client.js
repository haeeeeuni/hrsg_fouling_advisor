/**
 * axios 인스턴스 (specs/16 §1, §6).
 * - 세션 쿠키 + CSRF 토큰 방식이므로 withCredentials 가 필수다.
 * - 401 응답은 auth 스토어를 초기화하고 /login 으로 보낸다.
 * 컴포넌트는 axios 를 직접 쓰지 않고 api/*.js 모듈만 사용한다(AGENTS.md §4).
 */
import axios from 'axios'

const client = axios.create({
  baseURL: '/api',
  withCredentials: true,
  // Django 기본 쿠키/헤더 이름
  xsrfCookieName: 'csrftoken',
  xsrfHeaderName: 'X-CSRFToken',
  headers: { 'Content-Type': 'application/json' },
})

/** 401 처리를 라우터에 위임하기 위한 훅. main.js 에서 주입한다. */
let onUnauthorized = null
export function setUnauthorizedHandler(handler) {
  onUnauthorized = handler
}

/** 서버 공통 에러 포맷을 꺼낸다 (specs/15 §1). */
export function extractError(error) {
  const payload = error?.response?.data?.error
  if (payload) {
    return {
      code: payload.code ?? 'REQUEST_ERROR',
      message: payload.message ?? '요청을 처리할 수 없습니다.',
      details: payload.details ?? {},
    }
  }
  if (error?.response) {
    return { code: 'REQUEST_ERROR', message: '요청을 처리할 수 없습니다.', details: {} }
  }
  return { code: 'NETWORK_ERROR', message: '서버에 연결할 수 없습니다.', details: {} }
}

client.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error?.response?.status
    const url = error?.config?.url ?? ''
    // /auth/me/ 는 부팅 시 세션 확인용이라 401 이 정상 흐름이다. 리디렉션하지 않는다.
    if (status === 401 && !url.includes('/auth/me')) {
      onUnauthorized?.()
    }
    error.parsed = extractError(error)
    return Promise.reject(error)
  },
)

export default client
