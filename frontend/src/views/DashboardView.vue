<script setup>
import { computed, onMounted, ref, watch } from 'vue'

import ClusterBarChart from '@/components/charts/ClusterBarChart.vue'
import FoulingTrendChart from '@/components/charts/FoulingTrendChart.vue'
import ResidualChart from '@/components/charts/ResidualChart.vue'
import TornadoChart from '@/components/charts/TornadoChart.vue'
import BenefitPanel from '@/components/dashboard/BenefitPanel.vue'
import DataQualityPanel from '@/components/dashboard/DataQualityPanel.vue'
import GradeAlertBanner from '@/components/dashboard/GradeAlertBanner.vue'
import GradeBadge from '@/components/dashboard/GradeBadge.vue'
import KpiCard from '@/components/dashboard/KpiCard.vue'
import ModelAccuracyPanel from '@/components/dashboard/ModelAccuracyPanel.vue'
import WarningBanner from '@/components/dashboard/WarningBanner.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import HelpHint from '@/components/common/HelpHint.vue'
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
    <div class="d-flex justify-content-end align-items-center mb-3">
      <div>
        <button v-if="analysis.hasResult" class="btn btn-outline-secondary btn-sm me-1"
                :disabled="exporting" @click="exportReport('pdf')">PDF 다운로드</button>
        <button v-if="analysis.hasResult" class="btn btn-outline-secondary btn-sm me-1"
                :disabled="exporting" @click="exportReport('xlsx')">엑셀 다운로드</button>
        <RouterLink v-if="analysis.hasResult" class="btn btn-outline-primary btn-sm me-1"
                    :to="{ name: 'comparison' }">세정 전후 비교</RouterLink>
        <RouterLink class="btn btn-accent btn-sm" :to="{ name: 'analysis-run' }">분석 실행</RouterLink>
      </div>
    </div>

    <!-- specs/11 §7 — 조건부 배너 -->
    <div v-if="auth.mustChangePassword" class="alert alert-info d-flex justify-content-between align-items-center">
      <span>초기 비밀번호를 변경해 주세요.</span>
      <RouterLink class="btn btn-sm btn-outline-primary" :to="{ name: 'profile' }">비밀번호 변경</RouterLink>
    </div>
    <GradeAlertBanner :unit-id="units.selectedUnitId" />
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
          <KpiCard label="현재 오염도 지수" :value="formatFi(run.result_fi)" dark>
            <template #help>
              <HelpHint label="현재 오염도 지수">
                0~100 사이의 값으로, <strong>절대 오염량이 아니라 청정 기준 기간 대비</strong>
                얼마나 나빠졌는지를 나타냅니다. 세정 직후를 기준점으로 두고, 가스측 차압과
                스택온도가 그때보다 얼마나 벗어났는지를 합산합니다.
                <br /><br />
                기준점이 호기마다 다르므로 <strong>호기끼리 값을 직접 비교하지 않습니다.</strong>
                최근 7일 중앙값을 현재 값으로 씁니다.
              </HelpHint>
            </template>
            <template #hint>신뢰도 {{ run.result_confidence }}</template>
          </KpiCard>
        </div>
        <div class="col-12 col-md-6 col-xl-3">
          <KpiCard label="오염도 등급" value="">
            <template #help>
              <HelpHint label="오염도 등급">
                오염도 지수를 구간으로 나눈 것입니다. 경계값(기본 30 · 60)은
                <strong>관리자 설정에서 바꿀 수 있고, 바꾸면 다음 분석부터 적용</strong>됩니다.
                이미 저장된 결과는 그대로 남습니다.
              </HelpHint>
            </template>
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
            <template #help>
              <HelpHint label="임계 도달 D-day">
                오염도 지수가 임계치(기본 60)에 닿을 것으로 예상되는 날까지 남은 일수입니다.
                <strong>D-0 은 이미 임계치를 넘었다는 뜻</strong>입니다.
                <br /><br />
                추세는 <strong>가장 최근 세정 이후 구간만</strong>으로 잡습니다 — 세정 전후를
                섞으면 기울기가 뒤틀립니다. 유효 일자가 부족하거나 추세가 감소하면
                "예측 불가" 로 나옵니다.
              </HelpHint>
            </template>
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
            <template #help>
              <HelpHint label="예상 회수 편익" align="end">
                지금 세정했을 때의 순편익입니다.
                <br /><br />
                (오염으로 잃고 있는 출력 × 남은 기간) − (세정 비용 + 정지 손실)
                <br /><br />
                <strong>음수면 아직 세정할 때가 아니라는 뜻</strong>입니다. 등급이 경고여도
                남은 기간이 짧거나 세정 비용이 크면 음수가 나올 수 있습니다.
                전력단가·세정비 같은 계수는 관리자 설정에서 바꿉니다.
              </HelpHint>
            </template>
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
          <h2 class="h6 mb-3 d-flex align-items-center gap-2">
            <span>오염도 지수 시계열</span>
            <HelpHint label="오염도 지수 시계열">
              세로선은 세정 시점입니다. <strong>세정 때마다 값이 급락하고 다시 오르는
              톱니 모양이 정상</strong>입니다 — 그렇지 않다면 세정 이력이나 청정 기준 기간을
              확인해 보세요.
              <br /><br />
              가로 점선은 임계치, 배경 띠는 등급 구간입니다. 추세선과 예측 밴드는
              최근 세정 이후 데이터로만 그립니다.
            </HelpHint>
          </h2>
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
