/** 관리자 — 참조 데이터 API (specs/10 §6, specs/06). */
import client from './client'

export const fetchGtModels = () => client.get('/admin/gt-models/')
export const createGtModel = (payload) => client.post('/admin/gt-models/', payload)
export const updateGtModel = (id, payload) => client.patch(`/admin/gt-models/${id}/`, payload)
export const deactivateGtModel = (id) => client.delete(`/admin/gt-models/${id}/`)
export const downloadGtTemplate = () => client.get('/admin/gt-models/template/', { responseType: 'blob' })
export function importGtModels(file) {
  const form = new FormData()
  form.append('file', file)
  return client.post('/admin/gt-models/import/', form, { headers: { 'Content-Type': 'multipart/form-data' } })
}

export const fetchMethods = () => client.get('/admin/cleaning-methods/')
export const createMethod = (payload) => client.post('/admin/cleaning-methods/', payload)
export const updateMethod = (id, payload) => client.patch(`/admin/cleaning-methods/${id}/`, payload)
export const deactivateMethod = (id) => client.delete(`/admin/cleaning-methods/${id}/`)

export const fetchSmpPrices = () => client.get('/admin/smp-prices/', { params: { page_size: 100 } })
export const createSmpPrice = (payload) => client.post('/admin/smp-prices/', payload)
export const deleteSmpPrice = (id) => client.delete(`/admin/smp-prices/${id}/`)

export const fetchParameterSets = () => client.get('/admin/calc-parameter-sets/')
export const createParameterSet = (params, note) => client.post('/admin/calc-parameter-sets/', { params, note })
export const activateParameterSet = (id) => client.post(`/admin/calc-parameter-sets/${id}/activate/`)
export const previewParameters = (params) => client.post('/admin/calc-parameter-sets/preview/', { params })
