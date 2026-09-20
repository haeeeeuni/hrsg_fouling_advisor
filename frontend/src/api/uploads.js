/** 업로드 API (specs/15 §5). 검증과 적재는 분리되어 있다. */
import client from './client'

/** 운전 데이터 검증 → 202 { job_id, batch_id } */
export function validateOperation({ unitId, file, confirmDuplicateFile = false }, onProgress) {
  const form = new FormData()
  form.append('unit_id', unitId)
  form.append('file', file)
  if (confirmDuplicateFile) form.append('confirm_duplicate_file', 'true')

  return client.post('/uploads/operation/validate/', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (event) => {
      if (onProgress && event.total) {
        onProgress(Math.round((event.loaded / event.total) * 100))
      }
    },
  })
}

/** 검증 통과 배치 적재 → 202 { job_id } */
export function commitUpload(batchId, duplicatePolicy = 'SKIP') {
  return client.post(`/uploads/${batchId}/commit/`, { duplicate_policy: duplicatePolicy })
}

export function cancelUpload(batchId) {
  return client.post(`/uploads/${batchId}/cancel/`)
}

export function fetchUploads(params = {}) {
  return client.get('/uploads/', { params })
}

export function fetchUpload(batchId) {
  return client.get(`/uploads/${batchId}/`)
}

/** 관리자 전용 — 배치 롤백 */
export function rollbackUpload(batchId) {
  return client.delete(`/uploads/${batchId}/`)
}
