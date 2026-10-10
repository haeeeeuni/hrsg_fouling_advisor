/** 계산기 API (specs/10 §4). 계산식은 서버에만 있다 — 브라우저에서 계산하지 않는다(specs/05 CALC-8). */
import client from './client'

export function fetchOptions() {
  return client.get('/calculator/options/')
}

export function calculateLoss(inputs, config = {}) {
  return client.post('/calculator/loss/', inputs, config)
}

export function compareMethods(inputs, config = {}) {
  return client.post('/calculator/methods/', inputs, config)
}

export function checkPinchApproach(payload, config = {}) {
  return client.post('/calculator/pinch-approach/', payload, config)
}
