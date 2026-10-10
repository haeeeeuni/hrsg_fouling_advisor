/**
 * 계산기 입력 ↔ URL 쿼리 (specs/05 CALC-6).
 * 새로고침·링크 공유·챗봇 계산 카드의 "계산기에서 열기"가 같은 입력으로 계산기를 연다.
 */

/** 쿼리 키 ↔ 입력 필드. 짧게 두어 링크가 길어지지 않게 한다. */
export const LOSS_QUERY_KEYS = {
  gt: 'gt_model_id',
  pw: 'gt_power_mw',
  bp: 'backpressure_kpa',
  cbp: 'clean_backpressure_kpa',
  exh: 'exhaust_temp_c',
  stk: 'stack_temp_c',
  cstk: 'clean_stack_temp_c',
  hrs: 'operating_hours_per_day',
  smp: 'smp_won_per_kwh',
  m: 'cleaning_method_id',
}

const STAGE_FIELDS = [
  'drum_pressure_barg',
  'evaporator_outlet_gas_temp_c',
  'economizer_outlet_water_temp_c',
  'design_pinch_c',
  'design_approach_c',
]

function toNumber(raw) {
  if (raw === undefined || raw === null || raw === '') return null
  const value = Number(raw)
  return Number.isFinite(value) ? value : null
}

export function encodeLoss(inputs) {
  const query = {}
  for (const [key, field] of Object.entries(LOSS_QUERY_KEYS)) {
    const value = inputs[field]
    if (value !== null && value !== undefined && value !== '') query[key] = String(value)
  }
  return query
}

export function decodeLoss(query) {
  const inputs = {}
  for (const [key, field] of Object.entries(LOSS_QUERY_KEYS)) {
    inputs[field] = toNumber(query[key])
  }
  return inputs
}

/** 압력단: `120,335,318,,|30,200,180,,` — 빈 칸은 설계값 없음 */
export function encodeStages(stages) {
  return stages.map((s) => STAGE_FIELDS.map((f) => (s[f] ?? '')).join(',')).join('|')
}

export function decodeStages(raw) {
  if (!raw || typeof raw !== 'string') return null
  const stages = raw.split('|').map((chunk) => {
    const values = chunk.split(',')
    return Object.fromEntries(STAGE_FIELDS.map((f, i) => [f, toNumber(values[i])]))
  })
  return stages.length ? stages.slice(0, 3) : null
}
