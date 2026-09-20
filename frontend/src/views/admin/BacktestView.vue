<script setup>
import { computed, onMounted, ref, watch } from 'vue'

import {
  fetchBacktestAvailability,
  fetchBacktests,
  runBacktest,
} from '@/api/optional'
import BacktestScatterChart from '@/components/charts/BacktestScatterChart.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import { useJobPolling } from '@/composables/useJobPolling'
import { useToast } from '@/composables/useToast'
import { useUnitsStore } from '@/stores/units'
import { formatDate, formatDateTime, formatFi, formatPercent } from '@/utils/format'

const units = useUnitsStore()
const toast = useToast()
const job = useJobPolling({ key: 'backtest' })

const LOOKAHEAD_CHOICES = [
  { value: 0, label: '전체(30·60·90일) 평가' },
  { value: 30, label: '세정 30일 전' },
  { value: 60, label: '세정 60일 전' },
  { value: 90, label: '세정 90일 전' },
]

const lookahead = ref(0)
const results = ref([])
const availability = ref({})
const loading = ref(false)

const selectedUnitId = computed(() => units.selectedUnitId)
const selectedResultId = ref(null)
const current = computed(
  () => results.value.find((r) => r.id === selectedResultId.value) ?? results.value[0] ?? null,
)
const scatter = computed(() =>
  (current.value?.cases ?? [])
    .filter((c) => c.predicted_date)
    .map((c) => ({ x: c.actual_date, y: c.predicted_date })),
)
const running = computed(() => job.status.value === 'RUNNING')
const canRun = computed(() => availability.value[selectedUnitId.value]?.available ?? false)
const blockReason = computed(() => availability.value[selectedUnitId.value]?.reason ?? '')

async function loadAvailability() {
  const { data } = await fetchBacktestAvailability()
  availability.value = Object.fromEntries(data.results.map((row) => [row.unit_id, row]))
}

async function load() {
  if (!selectedUnitId.value) return
  loading.value = true
  try {
    const { data } = await fetchBacktests({ unit_id: selectedUnitId.value })
    results.value = data.results ?? []
    if (!results.value.some((r) => r.id === selectedResultId.value)) {
      selectedResultId.value = results.value[0]?.id ?? null
    }
  } finally {
    loading.value = false
  }
}

async function onRun() {
  try {
    const { data } = await runBacktest({
      unitId: selectedUnitId.value,
      // 0 이면 설정의 다중 지점을 서버가 모두 평가한다.
      lookaheadDays: lookahead.value || undefined,
    })
    const done = await job.start(data.job_id)
    if (done.status !== 'SUCCESS') {
      toast.push(done.error?.message ?? '백테스트가 실패했습니다.', 'danger')
      return
    }
    toast.push('백테스트가 완료되었습니다.', 'success')
    await load()
  } catch (err) {
    toast.push(err.response?.data?.error?.message ?? '백테스트 실행에 실패했습니다.', 'danger')
  }
}

onMounted(async () => {
  await units.fetchUnits()
  await loadAvailability()
  await load()
  // 페이지를 떠났다 돌아와도 진행 중인 실행을 이어서 감시한다 (AC-16-4).
  const resumed = job.resume()
  if (resumed) {
    await resumed
    await load()
  }
})

watch(selectedUnitId, load)
</script>

<template>
  <section>
    <div class="mb-3">
      <h2 class="h5 mb-1">예측 정확도 백테스트</h2>
      <p class="text-muted small mb-0">
        과거 세정 시점을 정답으로 두고, 컷오프 이전 데이터만으로 예측했을 때의 오차를 계산합니다.
        컷오프 이후의 데이터와 세정 이력은 사용하지 않습니다.
      </p>
    </div>

    <div class="card mb-4">
      <div class="card-body d-flex flex-wrap align-items-end gap-3">
        <div>
          <label for="lookahead" class="form-label small mb-1">컷오프 선행 일수</label>
          <select id="lookahead" v-model.number="lookahead" class="form-select form-select-sm">
            <option v-for="item in LOOKAHEAD_CHOICES" :key="item.value" :value="item.value">
              {{ item.label }}
            </option>
          </select>
        </div>
        <button
          class="btn btn-sm btn-primary"
          type="button"
          :disabled="!canRun || running"
          @click="onRun"
        >
          {{ running ? '실행 중…' : '백테스트 실행' }}
        </button>
        <p v-if="!canRun && blockReason" class="text-muted small mb-0 align-self-center">
          {{ blockReason }}
        </p>
      </div>
    </div>

    <LoadingSpinner v-if="loading" />
    <EmptyState
      v-else-if="!current"
      title="백테스트 결과가 없습니다."
      description="컷오프 선행 일수를 고르고 백테스트를 실행하면 예측 오차가 표시됩니다."
      icon="bi-bullseye"
    />

    <template v-else>
      <div class="row g-3 mb-4">
        <div class="col-6 col-lg-3">
          <div class="card h-100">
            <div class="card-body">
              <p class="text-muted small mb-1">평균 절대 오차</p>
              <p class="h4 mb-0">{{ current.summary.mae_days ?? '-' }} 일</p>
            </div>
          </div>
        </div>
        <div class="col-6 col-lg-3">
          <div class="card h-100">
            <div class="card-body">
              <p class="text-muted small mb-1">편향</p>
              <p class="h4 mb-0">{{ current.summary.bias_days ?? '-' }} 일</p>
              <p class="text-muted small mb-0">양수면 실제보다 늦게 예측</p>
            </div>
          </div>
        </div>
        <div class="col-6 col-lg-3">
          <div class="card h-100">
            <div class="card-body">
              <p class="text-muted small mb-1">
                ±{{ current.summary.hit_window_days }}일 적중률
              </p>
              <p class="h4 mb-0">{{ formatPercent((current.summary.hit_rate ?? 0) * 100) }}</p>
            </div>
          </div>
        </div>
        <div class="col-6 col-lg-3">
          <div class="card h-100">
            <div class="card-body">
              <p class="text-muted small mb-1">검증 세정</p>
              <p class="h4 mb-0">
                {{ current.summary.evaluated_count }} / {{ current.summary.case_count }} 건
              </p>
            </div>
          </div>
        </div>
      </div>

      <div v-if="results.length > 1" class="mb-3">
        <label for="resultPick" class="form-label small mb-1">평가 지점</label>
        <select id="resultPick" v-model.number="selectedResultId" class="form-select form-select-sm w-auto">
          <option v-for="item in results" :key="item.id" :value="item.id">
            세정 {{ item.lookahead_days }}일 전 · {{ formatDateTime(item.created_at) }}
          </option>
        </select>
      </div>

      <div v-if="current.warnings?.length" class="alert alert-warning small">
        <p v-for="(item, index) in current.warnings" :key="index" class="mb-0">
          {{ item.message }}
        </p>
      </div>

      <div class="table-responsive">
        <table class="table table-sm align-middle">
          <thead>
            <tr>
              <th scope="col">실제 세정일</th>
              <th scope="col">컷오프</th>
              <th scope="col" class="text-end">컷오프 시점 FI</th>
              <th scope="col">예측 도달일</th>
              <th scope="col" class="text-end">오차(일)</th>
              <th scope="col" class="text-end">실제 세정 시 FI</th>
              <th scope="col">비고</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in current.cases" :key="item.cleaning_event_id">
              <td>{{ formatDate(item.actual_date) }}</td>
              <td>{{ formatDate(item.cutoff_date) }}</td>
              <td class="text-end">{{ formatFi(item.fi_at_cutoff) }}</td>
              <td>{{ item.predicted_date ? formatDate(item.predicted_date) : '예측 불가' }}</td>
              <td class="text-end" :class="{ 'text-danger': Math.abs(item.error_days ?? 0) > 30 }">
                {{ item.error_days ?? '-' }}
              </td>
              <td class="text-end">{{ formatFi(item.fi_at_actual) }}</td>
              <td class="small text-muted">{{ item.note }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-if="scatter.length" class="card mt-4">
        <div class="card-header py-2">
          <strong class="small">예측 도달일 vs 실제 세정일</strong>
        </div>
        <div class="card-body">
          <BacktestScatterChart :points="scatter" />
        </div>
      </div>

      <p v-if="current.coefficient_suggestion?.available" class="alert alert-info small mt-3">
        예측 편익이 실제 대비 {{ current.coefficient_suggestion.tendency }} 경향입니다. 손실 계수에
        {{ current.coefficient_suggestion.median_actual_over_predicted }} 배를 적용하는 보정을
        검토하세요. 적용 여부는 관리자가 판단합니다.
      </p>
    </template>
  </section>
</template>
