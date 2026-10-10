/** 데이터 요청 체크리스트 API (specs/10 §5·§6). 요청 건은 본인 것만 보인다. */
import client from './client'

export const fetchRequests = (params = {}) => client.get('/checklist/requests/', { params })
export const createRequest = (payload) => client.post('/checklist/requests/', payload)
export const fetchRequest = (id) => client.get(`/checklist/requests/${id}/`)
export const updateRequest = (id, payload) => client.patch(`/checklist/requests/${id}/`, payload)
export const deleteRequest = (id) => client.delete(`/checklist/requests/${id}/`)
export const updateItem = (id, itemId, payload) => client.patch(`/checklist/requests/${id}/items/${itemId}/`, payload)
export const syncTemplate = (id) => client.post(`/checklist/requests/${id}/sync-template/`)
export const fetchEmailText = (id, { lang, scope }) =>
  client.get(`/checklist/requests/${id}/email-text/`, { params: { lang, scope } })

// --- 관리자 템플릿 ---
export const fetchTemplateItems = () => client.get('/admin/checklist-items/')
export const createTemplateItem = (payload) => client.post('/admin/checklist-items/', payload)
export const updateTemplateItem = (id, payload) => client.patch(`/admin/checklist-items/${id}/`, payload)
export const deactivateTemplateItem = (id) => client.delete(`/admin/checklist-items/${id}/`)
export const reorderTemplateItems = (ids) => client.post('/admin/checklist-items/reorder/', { ids })
export const exportTemplateItems = () => client.get('/admin/checklist-items/export/', { responseType: 'blob' })
export function importTemplateItems(file) {
  const form = new FormData()
  form.append('file', file)
  return client.post('/admin/checklist-items/import/', form, { headers: { 'Content-Type': 'multipart/form-data' } })
}
