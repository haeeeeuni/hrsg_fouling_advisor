<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import * as unitsApi from '@/api/units'
import EmptyState from '@/components/common/EmptyState.vue'
import { useJobPolling } from '@/composables/useJobPolling'
import { useToast } from '@/composables/useToast'
import { useAnalysisStore } from '@/stores/analysis'
import { useUnitsStore } from '@/stores/units'
import { ANALYSIS_STAGES } from '@/utils/constants'

const units = useUnitsStore()
const analysis = useAnalysisStore()
const toast = useToast()
const router = useRouter()

const job = useJobPolling({ key: 'analysis.run' })
const busy = ref(false)
const error = ref(null)
const periodStart = ref('')
const periodEnd = ref('')
// 이 호기에 실제로 적재된 기간. 기본값과 안내 문구에 쓴다.
const dataPeriod = ref(null)
const thresholdOverride = ref(null)

// 편익 파라미터 임시 변경 (specs/09 §3.2, specs/11 §8.2)
const BENEFIT_FIELDS = [
  ['electricity_price', '전력 단가', '원/kWh'],
  ['cleaning_cost', '세정 1회 비용', '원'],
  ['outage_days', '세정 정지 일수', '일'],
]
const benefitOverride = ref({})
const changedBenefit = computed(() =>
  Object.entries(benefitOverride.value)
    .filter(([, v]) => v !== null && v !== '' && v !== undefined)
    .map(([k]) => k),
)

const canRun = computed(
  () => units.selectedUnitId && periodStart.value && periodEnd.value && !busy.value,
)

onMounted(async () => {
  await units.fetchUnits()
  await applyDefaultRange()

  // 페이지를 이탈했다 돌아와도 진행 상태가 복원된다 (AC-16-4)
  const resumed = job.resume()
  if (resumed) {
    busy.value = true
    await resumed
    busy.value = false
  }
})

/**
 * 기본 분석 기간.
 *
 * "최근 12개월"(specs/04 §3)을 오늘 기준으로 잡으면, 적재된 데이터가 과거에만 있는 경우
 * 겹치는 구간이 없어 INSUFFICIENT_DATA 로 실패한다. 사용자는 이유를 알 수 없다.
 * 그래서 적재 기간을 먼저 읽고, 그 안에서 최근 12개월을 고른다.
 */
async function applyDefaultRange() {
  dataPeriod.value = null
  if (!units.selectedUnitId) return

  try {
    const { data } = await unitsApi.fetchDataSummary(units.selectedUnitId)
    const { start, end } = data?.period ?? {}
    if (start && end) {
      dataPeriod.value = { start: start.slice(0, 10), end: end.slice(0, 10) }
      const last = new Date(end)
      const from = new Date(last)
      from.setMonth(from.getMonth() - 12)
      const first = new Date(start)
      periodEnd.value = last.toISOString().slice(0, 10)
      periodStart.value = (from < first ? first : from).toISOString().slice(0, 10)
      return
    }
  } catch {
    // 요약을 못 읽어도 화면은 떠야 한다. 아래 기본값으로 떨어진다.
  }

  const end = new Date()
  const start = new Date(end)
  start.setMonth(start.getMonth() - 12)
  periodEnd.value = end.toISOString().slice(0, 10)
  periodStart.value = start.toISOString().slice(0, 10)
}

// 호기를 바꾸면 그 호기의 적재 기간으로 다시 잡는다.
watch(() => units.selectedUnitId, applyDefaultRange)

function applyQuickRange(months) {
  // 데이터가 있는 마지막 날을 기준으로 거슬러 올라간다. 오늘 기준이면
  // 과거 데이터만 있는 호기에서 빈 구간이 선택된다.
  const end = dataPeriod.value ? new Date(dataPeriod.value.end) : new Date()
  const start = new Date(end)
  start.setMonth(start.getMonth() - months)
  const first = dataPeriod.value ? new Date(dataPeriod.value.start) : null
  periodEnd.value = end.toISOString().slice(0, 10)
  periodStart.value = (first && start < first ? first : start).toISOString().slice(0, 10)
}

async function run() {
  if (!canRun.value) return
  busy.value = true
  error.value = null
  try {
    const settingsOverride = {}
    if (thresholdOverride.value) settingsOverride.fouling_threshold = thresholdOverride.value

    const benefitParams = Object.fromEntries(
      changedBenefit.value.map((key) => [key, benefitOverride.value[key]]),
    )

    const data = await analysis.start({
      unitId: units.selectedUnitId,
      periodStart: `${periodStart.value}T00:00:00+09:00`,
      periodEnd: `${periodEnd.value}T23:59:59+09:00`,
      settingsOverride,
      benefitParamsOverride: benefitParams,
    })

    const outcome = await job.start(data.job_id)
    if (outcome.status === 'SUCCESS') {
      toast.push('분석이 완료되었습니다.', 'success')
      await analysis.fetchResult(data.analysis_run_id)
      router.push({ name: 'dashboard' })
    } else {
      error.value = outcome.error
    }
  } catch (err) {
    error.value = err.parsed ?? { message: '분석을 시작할 수 없습니다.' }
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div>
    <EmptyState
      v-if="!units.activeUnits.length"
      title="분석할 호기가 없습니다."
      description="관리자가 호기를 등록하고 운전 데이터를 업로드해야 합니다."
      icon="bi-graph-up"
    />

    <div v-else class="card">
      <div class="card-body">
        <div class="row g-3">
          <div class="col-12 col-lg-4">
            <label for="runUnit" class="form-label">호기</label>
            <select
              id="runUnit"
              class="form-select"
              :value="units.selectedUnitId"
              :disabled="busy"
              @change="units.selectUnit(Number($event.target.value))"
            >
              <option v-for="unit in units.activeUnits" :key="unit.id" :value="unit.id">
                {{ unit.code }} — {{ unit.name }}
              </option>
            </select>
          </div>
          <div class="col-6 col-lg-4">
            <label for="periodStart" class="form-label">분석 시작일</label>
            <input id="periodStart" v-model="periodStart" type="date" class="form-control"
                   :min="dataPeriod?.start" :max="dataPeriod?.end" :disabled="busy" />
          </div>
          <div class="col-6 col-lg-4">
            <label for="periodEnd" class="form-label">분석 종료일</label>
            <input id="periodEnd" v-model="periodEnd" type="date" class="form-control"
                   :min="dataPeriod?.start" :max="dataPeriod?.end" :disabled="busy" />
          </div>
        </div>

        <!-- 적재 기간을 알려주지 않으면, 기본값이 데이터 밖으로 잡혀도 사용자는 이유를 모른다. -->
        <p v-if="dataPeriod" class="form-text mt-2 mb-0">
          이 호기에 적재된 기간: <strong>{{ dataPeriod.start }} ~ {{ dataPeriod.end }}</strong>
        </p>
        <p v-else-if="units.selectedUnitId" class="form-text text-warning mt-2 mb-0">
          적재된 운전 데이터가 없습니다. 먼저 데이터를 업로드하세요.
        </p>

        <div class="btn-group btn-group-sm mt-3" role="group" aria-label="기간 빠른 선택">
          <button v-for="m in [1, 3, 6, 12]" :key="m" type="button"
                  class="btn btn-outline-secondary" :disabled="busy" @click="applyQuickRange(m)">
            최근 {{ m }}개월
          </button>
        </div>

        <details class="mt-3">
          <summary class="small text-secondary">고급 설정 (이 분석에만 적용)</summary>
          <div class="row g-3 mt-1">
            <div class="col-6 col-lg-3">
              <label for="thresholdOverride" class="form-label small">오염도 임계치</label>
              <input id="thresholdOverride" v-model.number="thresholdOverride" type="number"
                     class="form-control form-control-sm" placeholder="기본값 사용" :disabled="busy" />
            </div>
            <div v-for="[key, label, unit] in BENEFIT_FIELDS" :key="key" class="col-6 col-lg-3">
              <label :for="`ov-${key}`" class="form-label small">
                {{ label }} <span class="text-secondary">({{ unit }})</span>
                <span v-if="changedBenefit.includes(key)" class="badge text-bg-warning ms-1">변경</span>
              </label>
              <input :id="`ov-${key}`" v-model.number="benefitOverride[key]" type="number" step="any"
                     class="form-control form-control-sm" placeholder="기본값 사용" :disabled="busy" />
            </div>
          </div>
          <p class="form-text mb-0">
            비워 두면 관리자 기본 설정값을 사용합니다.
            입력한 값은 <strong>이 분석에만 적용</strong>되며 기본 설정은 바뀌지 않습니다.
          </p>
        </details>

        <div v-if="busy" class="mt-3">
          <div class="progress" style="height: 0.5rem">
            <div class="progress-bar progress-bar-striped progress-bar-animated"
                 :style="{ width: `${job.progress.value}%` }"></div>
          </div>
          <p class="small text-secondary mt-1 mb-0">
            {{ job.stage.value || '시작하는 중' }}
            <span class="ms-2">({{ ANALYSIS_STAGES.join(' → ') }})</span>
          </p>
        </div>

        <div v-if="error" class="alert alert-danger mt-3 py-2 small" role="alert">
          {{ error.message }}
        </div>

        <button class="btn btn-primary mt-3" :disabled="!canRun" @click="run">
          <span v-if="busy" class="spinner-border spinner-border-sm me-2"></span>
          분석 실행
        </button>
      </div>
    </div>
  </div>
</template>
