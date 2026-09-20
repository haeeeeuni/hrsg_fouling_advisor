/** 리포트 생성·다운로드 API (specs/15 §9). */
import client from './client'

export function exportAnalysis(runId, format) {
  return client.post(`/analysis-runs/${runId}/export/`, { format })
}

export function exportComparison(comparisonId, format) {
  return client.post(`/comparisons/${comparisonId}/export/`, { format })
}

export function fetchReports(params = {}) {
  return client.get('/reports/', { params })
}

/** 파일을 내려받아 브라우저 저장 대화상자를 띄운다. 한글 파일명을 그대로 쓴다. */
export async function downloadReport(reportId, fileName) {
  const response = await client.get(`/reports/${reportId}/download/`, { responseType: 'blob' })
  const url = window.URL.createObjectURL(response.data)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = fileName
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  window.URL.revokeObjectURL(url)
}
