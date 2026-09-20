<script setup>
import { computed, onMounted, ref, watch } from 'vue'

import ClusterBarChart from '@/components/charts/ClusterBarChart.vue'
import FoulingTrendChart from '@/components/charts/FoulingTrendChart.vue'
import ResidualChart from '@/components/charts/ResidualChart.vue'
import TornadoChart from '@/components/charts/TornadoChart.vue'
import BenefitPanel from '@/components/dashboard/BenefitPanel.vue'
import DataQualityPanel from '@/components/dashboard/DataQualityPanel.vue'
import GradeBadge from '@/components/dashboard/GradeBadge.vue'
import KpiCard from '@/components/dashboard/KpiCard.vue'
import ModelAccuracyPanel from '@/components/dashboard/ModelAccuracyPanel.vue'
import WarningBanner from '@/components/dashboard/WarningBanner.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import { fetchCleaningEvents } from '@/api/maintenance'
import * as reportsApi from '@/api/reports'
import { useToast } from '@/composables/useToast'
import { useAnalysisStore } from '@/stores/analysis'
import { useAuthStore } from '@/stores/auth'
import { useUnitsStore } from '@/stores/units'
import { formatCurrency, formatDate, formatDateTime, formatDday, formatFi } from '@/utils/format'

const auth = useAuthStore()
const units = useUnitsStore()
const analysis = useAnalysisStore()

const run = computed(() => analysis.currentRun)
const settings = computed(() => run.value?.settings_snapshot ?? {})
const trend = computed(() => analysis.trend)
const benefit = computed(() => analysis.benefit)
const cleaningEvents = ref([])
const exporting = ref(false)
const toast = useToast()

async function exportReport(format) {
  if (!run.value) return
  exporting.value = true
  try {
    const { data } = await reportsApi.exportAnalysis(run.value.id, format)
    await reportsApi.downloadReport(data.id, data.file_name)
    toast.push('리포트를 내려받았습니다.', 'success')
  } catch (err) {
    toast.push(err.parsed?.message ?? '리포트 생성에 실패했습니다.', 'danger')
  } finally {
    exporting.value = false
  }
}

/** D-day 카드의 부가 설명 — 상태별로 문구가 다르다 (specs/08 §5). */
const ddayHint = computed(() => {
  const t = trend.value
  if (!t) return ''
  if (t.status === 'ALREADY_EXCEEDED') return `${t.exceeded_days ?? 0}일째 초과 중`
  if (t.status === 'OK' && t.eta_date) {
    const band = t.eta_lower_date && t.eta_upper_date
      ? ` (${formatDate(t.eta_lower_date)} ~ ${formatDate(t.eta_upper_date)})`
      : ''
    return `${formatDate(t.eta_date)}${band}`
  }
  return t.message ?? ''
})

async function loadCleaningEvents(unitId) {
  try {
    const { data } = await fetchCleaningEvents({ unit_id: unitId, page_size: 50 })
    cleaningEvents.value = data.results ?? data
  } catch {
    cleaningEvents.value = []
  }
}

onMounted(async () => {
  await units.fetchUnits()
  if (units.selectedUnitId) {
    await Promise.all([
      analysis.fetchLatest(units.selectedUnitId),
      loadCleaningEvents(units.selectedUnitId),
    ])
  }
})

watch(
  () => units.selectedUnitId,
  async (id) => {
    if (id) {
      await Promise.all([analysis.fetchLatest(id), loadCleaningEvents(id)])
    } else {
      analysis.reset()
      cleaningEvents.value = []
    }
  },
)
</script>

<template>
  <div>
    <div class="d-flex justify-content-between align-items-center mb-3">
      <h1 class="h4 mb-0">대시보드</h1>
      <div>
        <button v-if="analysis.hasResult" class="btn btn-outline-secondary btn-sm me-1"
                :disabled="exporting" @click="exportReport('pdf')">PDF 다운로드</button>
        <button v-if="analysis.hasResult" class="btn btn-outline-secondary btn-sm me-1"
                :disabled="exporting" @click="exportReport('xlsx')">엑셀 다운로드</button>
        <RouterLink v-if="analysis.hasResult" class="btn btn-outline-primary btn-sm me-1"
                    :to="{ name: 'comparison' }">세정 전후 비교</RouterLink>
        <RouterLink class="btn btn-primary btn-sm" :to="{ name: 'analysis-run' }">분석 실행</RouterLink>
      </div>
    </div>

    <!-- specs/11 §7 — 조건부 배너 -->
    <div v-if="auth.mustChangePassword" class="alert alert-info d-flex justify-content-between align-items-center">
      <span>초기 비밀번호를 변경해 주세요.</span>
      <RouterLink class="btn btn-sm btn-outline-primary" :to="{ name: 'profile' }">비밀번호 변경</RouterLink>
    </div>
    <WarningBanner :warnings="run?.warnings ?? []" />

    <LoadingSpinner v-if="analysis.loading" label="분석 결과를 불러오는 중" />

    <div v-else-if="!analysis.hasResult" class="card">
      <div class="card-body">
        <EmptyState
          title="아직 분석 결과가 없습니다."
          description="운전 데이터를 업로드한 뒤 분석을 실행하면 오염도 지수와 세정 시점이 표시됩니다."
          icon="bi-graph-up"
        >
          <template #action>
            <RouterLink class="btn btn-outline-primary btn-sm" :to="{ name: 'analysis-run' }">
              분석 실행
            </RouterLink>
          </template>
        </EmptyState>
      </div>
    </div>

    <template v-else>
      <p class="small text-secondary">
        최근 분석 {{ formatDateTime(run.executed_at) }} / 실행자 {{ run.executed_by_name ?? '–' }}
        / 모델 차압 v{{ run.model_dp?.version }} · 스택온도 v{{ run.model_st?.version }}
      </p>

      <!-- KPI 4종 (specs/11 §3) -->
      <div class="row g-3 mb-3">
        <div class="col-12 col-md-6 col-xl-3">
          <KpiCard label="현재 오염도 지수" :value="formatFi(run.result_fi)">
            <template #hint>신뢰도 {{ run.result_confidence }}</template>
          </KpiCard>
        </div>
        <div class="col-12 col-md-6 col-xl-3">
          <KpiCard label="오염도 등급" value="">
            <template #value><GradeBadge :grade="run.result_grade" size="large" /></template>
            <template #hint>정상 &lt; 30 · 주의 30~60 · 경고 ≥ 60</template>
          </KpiCard>
        </div>
        <div class="col-12 col-md-6 col-xl-3">
          <KpiCard
            label="임계 도달 D-day"
            :value="formatDday(trend?.eta_days, trend?.status)"
            :variant="trend?.status === 'ALREADY_EXCEEDED' ? 'danger' : ''"
          >
            <template #hint>
              {{ ddayHint }}
              <span v-if="trend?.uncertain" class="badge text-bg-warning ms-1">불확실성 높음</span>
            </template>
          </KpiCard>
        </div>
        <div class="col-12 col-md-6 col-xl-3">
          <KpiCard
            label="예상 회수 편익"
            :value="formatCurrency(benefit?.net_benefit)"
            :variant="benefit && benefit.net_benefit < 0 ? 'danger' : ''"
          >
            <template #hint>
              순편익 기준 ·
              회수기간 {{ benefit?.payback_days ? `${Math.round(benefit.payback_days)}일` : '–' }} ·
              지연 비용 {{ formatCurrency(benefit?.daily_loss_cost, { withEok: false }) }}/일
            </template>
          </KpiCard>
        </div>
      </div>

      <div class="card mb-3">
        <div class="card-body">
          <h2 class="h6 mb-3">오염도 지수 시계열</h2>
          <FoulingTrendChart
            :points="analysis.foulingIndex"
            :threshold="settings.fouling_threshold ?? 60"
            :caution-min="settings.grade_caution_min ?? 30"
            :warning-min="settings.grade_warning_min ?? 60"
            :cleaning-events="cleaningEvents"
            :trend="trend"
          />
          <p v-if="trend?.status === 'OK'" class="small text-secondary mt-2 mb-0">
            {{ trend.model_type }} 모델 · 진행률 {{ trend.slope_per_day?.toFixed(3) }} FI/일
            (주간 {{ trend.weekly_increase?.toFixed(2) }}) · R² {{ trend.r2?.toFixed(3) }}
            <template v-if="trend.caution_eta_date">
              · 주의 전환 {{ formatDate(trend.caution_eta_date) }}
            </template>
            <template v-if="trend.warning_eta_date">
              · 경고 전환 {{ formatDate(trend.warning_eta_date) }}
            </template>
          </p>
        </div>
      </div>

      <div class="row g-3 mb-3">
        <div class="col-12 col-xl-6">
          <ResidualChart :points="analysis.foulingIndex" target="dp" />
        </div>
        <div class="col-12 col-xl-6">
          <ResidualChart :points="analysis.foulingIndex" target="st" />
        </div>
      </div>

      <div class="row g-3 mb-3">
        <div class="col-12 col-xl-6"><BenefitPanel :benefit="benefit" /></div>
        <div class="col-12 col-xl-6"><TornadoChart :sensitivity="benefit?.sensitivity ?? []" /></div>
      </div>

      <div class="row g-3">
        <div class="col-12 col-xl-4"><ModelAccuracyPanel :metrics="analysis.modelMetrics" /></div>
        <div class="col-12 col-xl-4"><DataQualityPanel :quality="analysis.dataQuality" /></div>
        <div class="col-12 col-xl-4"><ClusterBarChart :clusters="analysis.clusters" /></div>
      </div>
    </template>
  </div>
</template>
