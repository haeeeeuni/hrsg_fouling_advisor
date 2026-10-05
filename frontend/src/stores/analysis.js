/** 분석 실행 / 결과 캐시 (specs/16 §5). */
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import * as analysisApi from '@/api/analysis'

export const useAnalysisStore = defineStore('analysis', () => {
  const currentRun = ref(null)
  const foulingIndex = ref([])
  const clusters = ref([])
  const modelMetrics = ref(null)
  const dataQuality = ref(null)
  const signalDiagnosis = ref(null)
  const trend = ref(null)
  const benefit = ref(null)
  const loading = ref(false)
  // 결과를 읽지 못했을 때의 오류. 비워 두면 화면이 "분석 결과 없음" 으로 보여 장애를 데이터 부재로 오인한다.
  const error = ref(null)
  // 호기를 빠르게 바꾸면 요청이 겹친다. 늦게 도착한 이전 호기의 응답이 새 호기 화면을
  // 덮어쓰지 않도록 마지막 요청의 응답만 반영한다.
  let requestSeq = 0

  const hasResult = computed(() => currentRun.value?.status === 'SUCCESS')
  const grade = computed(() => currentRun.value?.result_grade ?? null)

  async function start({ unitId, periodStart, periodEnd, settingsOverride, benefitParamsOverride }) {
    const { data } = await analysisApi.runAnalysis({
      unitId,
      periodStart,
      periodEnd,
      settingsOverride,
      benefitParamsOverride,
    })
    return data
  }

  /** 분석 결과 일괄 조회. 호기·분석이 바뀌면 호출부가 다시 부른다. 실패하면 호출부로 던진다. */
  async function fetchResult(runId) {
    return load(runId, ++requestSeq)
  }

  async function load(runId, seq) {
    loading.value = true
    try {
      const { data } = await analysisApi.fetchRun(runId)
      const [fi, cl, metrics, quality, signals] = await Promise.all([
        analysisApi.fetchFoulingIndex(runId),
        analysisApi.fetchClusters(runId),
        analysisApi.fetchModelMetrics(runId),
        analysisApi.fetchDataQuality(runId),
        // 신호 진단은 부가 정보다 — 실패해도 대시보드 전체를 막지 않는다.
        analysisApi.fetchSignalDiagnosis(runId).catch(() => ({ data: null })),
      ])
      if (seq !== requestSeq) return null

      currentRun.value = data
      // 상세 결과는 run 응답에 중첩돼 있어 추가 왕복이 필요 없다.
      trend.value = data.trend ?? null
      benefit.value = data.benefit ?? null
      foulingIndex.value = fi.data
      clusters.value = cl.data
      modelMetrics.value = metrics.data
      dataQuality.value = quality.data
      signalDiagnosis.value = signals.data
      error.value = null
    } finally {
      if (seq === requestSeq) loading.value = false
    }
    return currentRun.value
  }

  /**
   * 해당 호기의 가장 최근 성공 분석을 불러온다.
   * 실패하면 던지지 않고 error 에 담는다 — 이전 호기의 결과를 남겨 두면 다른 호기 이름 아래에 보이게 된다.
   */
  async function fetchLatest(unitId) {
    const seq = ++requestSeq
    loading.value = true
    error.value = null
    try {
      const { data } = await analysisApi.fetchRuns({
        unit_id: unitId,
        status: 'SUCCESS',
        page_size: 1,
        ordering: '-executed_at',
      })
      if (seq !== requestSeq) return null
      const rows = data.results ?? data
      if (!rows.length) {
        reset()
        return null
      }
      return await load(rows[0].id, seq)
    } catch (err) {
      if (seq !== requestSeq) return null
      reset()
      error.value = err.parsed ?? { code: 'REQUEST_ERROR', message: '분석 결과를 불러오지 못했습니다.' }
      return null
    } finally {
      if (seq === requestSeq) loading.value = false
    }
  }

  /** 편익 파라미터만 바꿔 재계산한다. 관리자 기본값은 바뀌지 않는다. */
  async function recalculateBenefit(benefitParams) {
    if (!currentRun.value) return null
    const { data } = await analysisApi.recalculateBenefit(currentRun.value.id, benefitParams)
    benefit.value = data
    currentRun.value = { ...currentRun.value, result_net_benefit: Math.round(data.net_benefit) }
    return data
  }

  function reset() {
    error.value = null
    currentRun.value = null
    trend.value = null
    benefit.value = null
    foulingIndex.value = []
    clusters.value = []
    modelMetrics.value = null
    dataQuality.value = null
    signalDiagnosis.value = null
  }

  return {
    currentRun,
    foulingIndex,
    clusters,
    modelMetrics,
    dataQuality,
    signalDiagnosis,
    trend,
    benefit,
    loading,
    error,
    hasResult,
    grade,
    start,
    fetchResult,
    fetchLatest,
    recalculateBenefit,
    reset,
  }
})
