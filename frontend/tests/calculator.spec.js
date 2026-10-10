/** 계산기 — 디바운스·늦은 응답 무시, URL 입력 복원 (specs/05 CALC-6, AC-05-7). */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { effectScope, nextTick } from 'vue'

import { useLatestRequest } from '@/composables/useLatestRequest'
import { decodeLoss, decodeStages, encodeLoss, encodeStages } from '@/utils/calcQuery'

function inScope(fn) {
  const scope = effectScope()
  const result = scope.run(fn)
  return { ...result, stop: () => scope.stop() }
}

describe('useLatestRequest', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('연달아 바꾸면 마지막 입력으로 한 번만 요청한다', async () => {
    const request = vi.fn((x) => Promise.resolve(x))
    const { run, data } = inScope(() => useLatestRequest(request, { delay: 300 }))

    run(1)
    run(2)
    run(3)
    await vi.advanceTimersByTimeAsync(300)

    expect(request).toHaveBeenCalledTimes(1)
    expect(request).toHaveBeenCalledWith(3)
    expect(data.value).toBe(3)
  })

  it('늦게 도착한 옛 응답은 최신 결과를 덮지 않는다', async () => {
    const resolvers = {}
    const request = (x) => new Promise((resolve) => (resolvers[x] = () => resolve(`결과 ${x}`)))
    const { runNow, data, loading } = inScope(() => useLatestRequest(request))

    runNow('옛')
    runNow('새')
    resolvers['새']()
    await nextTick()
    await Promise.resolve()
    resolvers['옛']()
    await Promise.resolve()
    await Promise.resolve()

    expect(data.value).toBe('결과 새')
    expect(loading.value).toBe(false)
  })

  it('요청 중에도 이전 결과를 유지한다(깜빡임 없음)', async () => {
    let resolveSecond
    const request = vi
      .fn()
      .mockResolvedValueOnce('첫 결과')
      .mockImplementationOnce(() => new Promise((r) => (resolveSecond = r)))
    const { runNow, data, loading } = inScope(() => useLatestRequest(request))

    await runNow()
    const pending = runNow()

    expect(loading.value).toBe(true)
    expect(data.value).toBe('첫 결과')
    resolveSecond('둘째 결과')
    await pending
    expect(data.value).toBe('둘째 결과')
  })

  it('cancel 하면 대기 중인 요청을 보내지 않는다', async () => {
    const request = vi.fn(() => Promise.resolve(1))
    const { run, cancel } = inScope(() => useLatestRequest(request, { delay: 300 }))

    run()
    cancel()
    await vi.advanceTimersByTimeAsync(500)

    expect(request).not.toHaveBeenCalled()
  })

  it('오류는 서버 에러 형식으로 담는다', async () => {
    const parsed = { code: 'VALIDATION_ERROR', message: '입력값이 올바르지 않습니다.', details: { bp: ['x'] } }
    const { runNow, error } = inScope(() => useLatestRequest(() => Promise.reject(Object.assign(new Error(), { parsed }))))

    await runNow()

    expect(error.value).toEqual(parsed)
  })
})

describe('계산기 URL 쿼리', () => {
  it('입력을 짧은 키로 담고 그대로 복원한다', () => {
    const inputs = { gt_model_id: 2, backpressure_kpa: 4.6, stack_temp_c: 100, smp_won_per_kwh: null }

    const query = encodeLoss(inputs)

    expect(query).toEqual({ gt: '2', bp: '4.6', stk: '100' })
    expect(decodeLoss(query)).toMatchObject({ gt_model_id: 2, backpressure_kpa: 4.6, stack_temp_c: 100, smp_won_per_kwh: null })
  })

  it('숫자가 아닌 값은 버린다', () => {
    expect(decodeLoss({ bp: 'abc', gt: '' })).toMatchObject({ backpressure_kpa: null, gt_model_id: null })
  })

  it('압력단은 최대 3개, 빈 칸은 설계값 없음', () => {
    const stages = [
      { drum_pressure_barg: 120, evaporator_outlet_gas_temp_c: 335, economizer_outlet_water_temp_c: 318, design_pinch_c: null, design_approach_c: 8 },
    ]

    const raw = encodeStages(stages)

    expect(raw).toBe('120,335,318,,8')
    expect(decodeStages(raw)).toEqual(stages)
    expect(decodeStages('1,2,3|4,5,6|7,8,9|10,11,12')).toHaveLength(3)
    expect(decodeStages(undefined)).toBeNull()
  })
})
