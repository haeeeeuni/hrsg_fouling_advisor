/** 호기·컬럼 매핑 API (specs/15 §4). */
import client from './client'

export function fetchUnits(params = {}) {
  return client.get('/units/', { params })
}

export function fetchUnit(id) {
  return client.get(`/units/${id}/`)
}

export function createUnit(payload) {
  return client.post('/units/', payload)
}

export function updateUnit(id, payload) {
  return client.patch(`/units/${id}/`, payload)
}

export function deleteUnit(id) {
  return client.delete(`/units/${id}/`)
}

export function fetchDataSummary(id) {
  return client.get(`/units/${id}/data-summary/`)
}

export function fetchStandardFields() {
  return client.get('/standard-fields/')
}

export function fetchColumnMappings(unitId) {
  return client.get(`/units/${unitId}/column-mappings/`)
}

export function saveColumnMappings(unitId, mappings) {
  return client.put(`/units/${unitId}/column-mappings/`, { mappings })
}

export function fetchMappingVersions(unitId) {
  return client.get(`/units/${unitId}/column-mappings/versions/`)
}

export function previewMapping(unitId, file, mappings) {
  const form = new FormData()
  form.append('file', file)
  if (mappings) form.append('mappings', JSON.stringify(mappings))
  return client.post(`/units/${unitId}/column-mappings/preview/`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}
