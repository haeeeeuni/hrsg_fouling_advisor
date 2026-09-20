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
  const trend = ref(null)
  const benefit = ref(null)
  const loading = ref(false)

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

  /** 분석 결과 일괄 조회. 호기·분석이 바뀌면 호출부가 다시 부른다. */
  async function fetchResult(runId) {
    loading.value = true
    try {
      const { data } = await analysisApi.fetchRun(runId)
      currentRun.value = data
      // 상세 결과는 run 응답에 중첩돼 있어 추가 왕복이 필요 없다.
      trend.value = data.trend ?? null
      benefit.value = data.benefit ?? null

      const [fi, cl, metrics, quality] = await Promise.all([
        analysisApi.fetchFoulingIndex(runId),
        analysisApi.fetchClusters(runId),
        analysisApi.fetchModelMetrics(runId),
        analysisApi.fetchDataQuality(runId),
      ])
      foulingIndex.value = fi.data
      clusters.value = cl.data
      modelMetrics.value = metrics.data
      dataQuality.value = quality.data
    } finally {
      loading.value = false
    }
    return currentRun.value
  }

  /** 해당 호기의 가장 최근 성공 분석을 불러온다. */
  async function fetchLatest(unitId) {
    const { data } = await analysisApi.fetchRuns({
      unit_id: unitId,
      status: 'SUCCESS',
      page_size: 1,
      ordering: '-executed_at',
    })
    const rows = data.results ?? data
    if (!rows.length) {
      reset()
      return null
    }
    return fetchResult(rows[0].id)
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
    currentRun.value = null
    trend.value = null
    benefit.value = null
    foulingIndex.value = []
    clusters.value = []
    modelMetrics.value = null
    dataQuality.value = null
  }

  return {
    currentRun,
    foulingIndex,
    clusters,
    modelMetrics,
    dataQuality,
    trend,
    benefit,
    loading,
    hasResult,
    grade,
    start,
    fetchResult,
    fetchLatest,
    recalculateBenefit,
    reset,
  }
})
