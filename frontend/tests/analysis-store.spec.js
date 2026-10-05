import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/api/analysis', () => ({
  runAnalysis: vi.fn(),
  fetchRuns: vi.fn(),
  fetchRun: vi.fn(),
  fetchFoulingIndex: vi.fn(),
  fetchResiduals: vi.fn(),
  fetchClusters: vi.fn(),
  fetchModelMetrics: vi.fn(),
  fetchDataQuality: vi.fn(),
  fetchSignalDiagnosis: vi.fn(),
  fetchTrend: vi.fn(),
  fetchBenefit: vi.fn(),
  recalculateBenefit: vi.fn(),
}))

import * as api from '@/api/analysis'
import { useAnalysisStore } from '@/stores/analysis'

const RUN = {
  id: 7,
  status: 'SUCCESS',
  result_fi: 62.4,
  result_grade: 'WARNING',
  result_confidence: 'HIGH',
  settings_snapshot: { fouling_threshold: 60 },
}

function mockAll() {
  api.fetchRun.mockResolvedValue({ data: RUN })
  api.fetchFoulingIndex.mockResolvedValue({ data: [{ date: '2024-01-01', fi_value: 10 }] })
  api.fetchClusters.mockResolvedValue({ data: [{ cluster_key: 'L3-SU' }] })
  api.fetchModelMetrics.mockResolvedValue({ data: { dp: {}, stack_temp: {} } })
  api.fetchDataQuality.mockResolvedValue({ data: { row_valid: 100 } })
  api.fetchSignalDiagnosis.mockResolvedValue({
    data: { verdict: 'CONSISTENT', dp: 70.1, st: 65.3, gap: 4.8 },
  })
}

describe('analysis store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    mockAll()
  })

  it('분석 실행은 job_id 와 run id 를 돌려준다', async () => {
    api.runAnalysis.mockResolvedValue({ data: { job_id: 'j1', analysis_run_id: 7 } })
    const store = useAnalysisStore()

    const result = await store.start({
      unitId: 1,
      periodStart: '2024-01-01T00:00:00+09:00',
      periodEnd: '2024-12-31T23:59:59+09:00',
    })

    expect(result.job_id).toBe('j1')
    expect(api.runAnalysis).toHaveBeenCalledWith(
      expect.objectContaining({ unitId: 1 }),
    )
  })

  it('결과 조회는 여섯 엔드포인트를 병렬로 부른다', async () => {
    const store = useAnalysisStore()

    await store.fetchResult(7)

    expect(store.currentRun.id).toBe(7)
    expect(store.foulingIndex).toHaveLength(1)
    expect(store.clusters).toHaveLength(1)
    expect(store.dataQuality.row_valid).toBe(100)
    expect(store.signalDiagnosis.verdict).toBe('CONSISTENT')
    expect(store.hasResult).toBe(true)
    expect(store.grade).toBe('WARNING')
  })

  it('신호 진단이 실패해도 대시보드는 열린다', async () => {
    // 부가 정보이므로 여기서 던지면 나머지 패널까지 못 그린다.
    api.fetchSignalDiagnosis.mockRejectedValue(new Error('404'))
    const store = useAnalysisStore()

    await store.fetchResult(7)

    expect(store.hasResult).toBe(true)
    expect(store.signalDiagnosis).toBeNull()
  })

  it('최근 성공 분석을 불러온다', async () => {
    api.fetchRuns.mockResolvedValue({ data: { results: [{ id: 7 }] } })
    const store = useAnalysisStore()

    await store.fetchLatest(1)

    expect(api.fetchRuns).toHaveBeenCalledWith(
      expect.objectContaining({ unit_id: 1, status: 'SUCCESS' }),
    )
    expect(store.currentRun.id).toBe(7)
  })

  it('성공 분석이 없으면 상태를 비운다', async () => {
    api.fetchRuns.mockResolvedValue({ data: { results: [] } })
    const store = useAnalysisStore()
    await store.fetchResult(7)

    const result = await store.fetchLatest(99)

    expect(result).toBeNull()
    expect(store.currentRun).toBeNull()
    expect(store.hasResult).toBe(false)
  })

  it('결과가 없으면 hasResult 는 false', () => {
    expect(useAnalysisStore().hasResult).toBe(false)
  })

  it('실패한 분석은 결과로 치지 않는다', async () => {
    api.fetchRun.mockResolvedValue({ data: { ...RUN, status: 'FAILED' } })
    const store = useAnalysisStore()

    await store.fetchResult(7)

    expect(store.hasResult).toBe(false)
  })
})

describe('analysis store — Phase 4', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    mockAll()
  })

  it('run 응답의 추세·편익을 추가 왕복 없이 꺼낸다', async () => {
    api.fetchRun.mockResolvedValue({
      data: { ...RUN, trend: { status: 'OK', eta_days: 84 }, benefit: { net_benefit: 7.68e8 } },
    })
    const store = useAnalysisStore()

    await store.fetchResult(7)

    expect(store.trend.eta_days).toBe(84)
    expect(store.benefit.net_benefit).toBe(7.68e8)
    expect(api.fetchTrend).not.toHaveBeenCalled()
  })

  it('편익 재계산은 편익만 갱신하고 요약 순편익을 맞춘다', async () => {
    api.fetchRun.mockResolvedValue({ data: { ...RUN, trend: null, benefit: { net_benefit: 100 } } })
    api.recalculateBenefit.mockResolvedValue({ data: { net_benefit: 250.4, daily_loss_cost: 9 } })
    const store = useAnalysisStore()
    await store.fetchResult(7)

    await store.recalculateBenefit({ electricity_price: 240 })

    expect(api.recalculateBenefit).toHaveBeenCalledWith(7, { electricity_price: 240 })
    expect(store.benefit.net_benefit).toBe(250.4)
    expect(store.currentRun.result_net_benefit).toBe(250)
  })

  it('분석이 없으면 재계산은 아무것도 하지 않는다', async () => {
    const store = useAnalysisStore()

    expect(await store.recalculateBenefit({})).toBeNull()
    expect(api.recalculateBenefit).not.toHaveBeenCalled()
  })

  it('분석 실행에 편익 임시값을 함께 보낸다', async () => {
    api.runAnalysis.mockResolvedValue({ data: { job_id: 'j1', analysis_run_id: 7 } })
    const store = useAnalysisStore()

    await store.start({
      unitId: 1,
      periodStart: 'a',
      periodEnd: 'b',
      benefitParamsOverride: { cleaning_cost: 25000000 },
    })

    expect(api.runAnalysis).toHaveBeenCalledWith(
      expect.objectContaining({ benefitParamsOverride: { cleaning_cost: 25000000 } }),
    )
  })

  it('reset 은 추세·편익도 비운다', async () => {
    api.fetchRun.mockResolvedValue({ data: { ...RUN, trend: { status: 'OK' }, benefit: {} } })
    const store = useAnalysisStore()
    await store.fetchResult(7)

    store.reset()

    expect(store.trend).toBeNull()
    expect(store.benefit).toBeNull()
  })

  it('최근 분석 조회가 실패하면 결과를 비우고 오류를 담는다(던지지 않는다)', async () => {
    const store = useAnalysisStore()
    api.fetchRuns.mockResolvedValue({ data: { results: [{ id: 7 }] } })
    await store.fetchLatest(1)
    expect(store.hasResult).toBe(true)

    const failure = Object.assign(new Error('500'), { parsed: { code: 'INTERNAL_ERROR', message: '서버 오류' } })
    api.fetchRuns.mockRejectedValue(failure)
    await expect(store.fetchLatest(2)).resolves.toBeNull()

    // 이전 호기(1)의 결과가 호기 2 화면에 남으면 안 된다.
    expect(store.hasResult).toBe(false)
    expect(store.error).toEqual({ code: 'INTERNAL_ERROR', message: '서버 오류' })
    expect(store.loading).toBe(false)
  })

  it('호기를 빠르게 바꾸면 늦게 도착한 이전 호기의 응답을 버린다', async () => {
    const store = useAnalysisStore()
    let releaseFirst
    api.fetchRuns
      .mockImplementationOnce(() => new Promise((resolve) => (releaseFirst = resolve)))
      .mockResolvedValueOnce({ data: { results: [{ id: 8 }] } })
    api.fetchRun.mockImplementation(async (id) => ({ data: { ...RUN, id } }))

    const first = store.fetchLatest(1) // 호기 1 — 응답이 늦다
    await store.fetchLatest(2) // 호기 2 — 먼저 끝난다
    releaseFirst({ data: { results: [{ id: 7 }] } })
    await first

    expect(store.currentRun.id).toBe(8)
  })
})
