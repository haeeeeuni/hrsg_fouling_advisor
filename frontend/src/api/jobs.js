/** 비동기 작업 상태 폴링 (specs/10 §7). */
import client from './client'

export function fetchJob(jobId) {
  return client.get(`/jobs/${jobId}/`)
}

export function cancelJob(jobId) {
  return client.post(`/jobs/${jobId}/cancel/`)
}
