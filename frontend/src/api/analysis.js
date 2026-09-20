/** 분석 API (specs/15 §6). */
import client from './client'

/** 분석 실행 → 202 { job_id, analysis_run_id } */
export function runAnalysis({
  unitId,
  periodStart,
  periodEnd,
  settingsOverride,
  benefitParamsOverride,
}) {
  return client.post('/analysis-runs/', {
    unit_id: unitId,
    period_start: periodStart,
    period_end: periodEnd,
    settings_override: settingsOverride ?? {},
    benefit_params_override: benefitParamsOverride ?? {},
  })
}

export function fetchRuns(params = {}) {
  return client.get('/analysis-runs/', { params })
}

export function fetchRun(id) {
  return client.get(`/analysis-runs/${id}/`)
}

export function fetchFoulingIndex(id, params = {}) {
  return client.get(`/analysis-runs/${id}/fouling-index/`, { params })
}

export function fetchResiduals(id) {
  return client.get(`/analysis-runs/${id}/residuals/`)
}

export function fetchClusters(id) {
  return client.get(`/analysis-runs/${id}/clusters/`)
}

export function fetchModelMetrics(id) {
  return client.get(`/analysis-runs/${id}/model-metrics/`)
}

export function fetchDataQuality(id) {
  return client.get(`/analysis-runs/${id}/data-quality/`)
}

export function fetchTrend(id) {
  return client.get(`/analysis-runs/${id}/trend/`)
}

export function fetchBenefit(id) {
  return client.get(`/analysis-runs/${id}/benefit/`)
}

/** 편익 파라미터만 바꿔 재계산 — 분석은 재실행하지 않는다. */
export function recalculateBenefit(id, benefitParams) {
  return client.post(`/analysis-runs/${id}/recalculate-benefit/`, {
    benefit_params_override: benefitParams,
  })
}
