/** 모델 관리 API (specs/15 §11). */
import client from './client'

export function fetchModelVersions(params = {}) {
  return client.get('/model-versions/', { params })
}

/** 재학습 → 202 + job_id. 승인 전까지 기존 활성 모델이 유지된다. */
export function trainModels({ unitId, targets, algorithm, baselinePeriodIds }) {
  return client.post('/model-versions/train/', {
    unit_id: unitId,
    targets,
    algorithm: algorithm || undefined,
    baseline_period_ids: baselinePeriodIds || undefined,
  })
}

export function compareModel(id) {
  return client.get(`/model-versions/${id}/compare/`)
}

export function activateModel(id) {
  return client.post(`/model-versions/${id}/activate/`)
}

export function fetchBaselinePeriods(params = {}) {
  return client.get('/clean-baseline-periods/', { params })
}

export function createBaselinePeriod(payload) {
  return client.post('/clean-baseline-periods/', payload)
}

export function deleteBaselinePeriod(id) {
  return client.delete(`/clean-baseline-periods/${id}/`)
}

export function previewBaselinePeriod(id) {
  return client.get(`/clean-baseline-periods/${id}/preview/`)
}
