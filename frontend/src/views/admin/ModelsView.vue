<script setup>
import { computed, onMounted, ref, watch } from 'vue'

import * as api from '@/api/models'
import EmptyState from '@/components/common/EmptyState.vue'
import { useJobPolling } from '@/composables/useJobPolling'
import { useToast } from '@/composables/useToast'
import { useUnitsStore } from '@/stores/units'
import { formatCount, formatDate, formatDateTime } from '@/utils/format'

const units = useUnitsStore()
const toast = useToast()
const job = useJobPolling({ key: 'models.train' })

const versions = ref([])
const periods = ref([])
const comparison = ref(null)
const busy = ref(false)
const error = ref(null)
const trainForm = ref({ targets: ['DP', 'STACK_TEMP'], algorithm: '', baselinePeriodIds: [] })
const newPeriod = ref({ start_at: '', end_at: '', note: '' })

const TARGET_LABELS = { DP: '차압', STACK_TEMP: '스택온도' }

const byTarget = computed(() => ({
  DP: versions.value.filter((v) => v.target === 'DP'),
  STACK_TEMP: versions.value.filter((v) => v.target === 'STACK_TEMP'),
}))

onMounted(async () => {
  await units.fetchUnits()
  await load()
})
watch(() => units.selectedUnitId, load)

async function load() {
  if (!units.selectedUnitId) return
  const [v, p] = await Promise.all([
    api.fetchModelVersions({ unit_id: units.selectedUnitId, page_size: 50 }),
    api.fetchBaselinePeriods({ unit_id: units.selectedUnitId }),
  ])
  versions.value = v.data.results ?? v.data
  periods.value = p.data.results ?? p.data
}

async function train() {
  busy.value = true
  error.value = null
  try {
    const { data } = await api.trainModels({
      unitId: units.selectedUnitId,
      targets: trainForm.value.targets,
      algorithm: trainForm.value.algorithm,
      baselinePeriodIds: trainForm.value.baselinePeriodIds.length
        ? trainForm.value.baselinePeriodIds
        : null,
    })
    const outcome = await job.start(data.job_id)
    if (outcome.status === 'SUCCESS') {
      toast.push(
        `재학습 완료. ${outcome.result.notice}`,
        'success',
      )
      await load()
    } else {
      error.value = outcome.error
    }
  } catch (err) {
    error.value = err.parsed ?? { message: '재학습을 시작할 수 없습니다.' }
  } finally {
    busy.value = false
  }
}

async function compare(version) {
  const { data } = await api.compareModel(version.id)
  comparison.value = data
}

async function activate(version) {
  if (!window.confirm(`${TARGET_LABELS[version.target]} 모델 v${version.version} 을 활성화할까요?\n이후 분석부터 이 모델이 사용됩니다.`)) return
  try {
    await api.activateModel(version.id)
    comparison.value = null
    await load()
    toast.push('활성 모델을 교체했습니다.', 'success')
  } catch (err) {
    toast.push(err.parsed?.message ?? '활성화할 수 없습니다.', 'danger')
  }
}

async function addPeriod() {
  error.value = null
  try {
    await api.createBaselinePeriod({
      unit: units.selectedUnitId,
      start_at: newPeriod.value.start_at,
      end_at: newPeriod.value.end_at,
      source: 'MANUAL',
      is_active: true,
      note: newPeriod.value.note,
    })
    newPeriod.value = { start_at: '', end_at: '', note: '' }
    await load()
    toast.push('청정 기준 기간을 추가했습니다.', 'success')
  } catch (err) {
    error.value = err.parsed
  }
}

async function preview(period) {
  const { data } = await api.previewBaselinePeriod(period.id)
  toast.push(
    `유효 포인트 ${formatCount(data.count)} · 평균 차압 ${data.avg_dp?.toFixed(2) ?? '–'} kPa · ` +
      `평균 스택온도 ${data.avg_stack?.toFixed(1) ?? '–'} ℃`,
    'info',
    8000,
  )
}

async function removePeriod(period) {
  if (!window.confirm('청정 기준 기간을 삭제할까요?')) return
  await api.deleteBaselinePeriod(period.id)
  await load()
}

function fmt(value, digits = 3) {
  return value === null || value === undefined || Number.isNaN(value) ? '–' : value.toFixed(digits)
}
</script>

<template>
  <div>
    <div class="mb-3" style="max-width: 24rem">
      <label for="mdUnit" class="form-label">호기</label>
      <select id="mdUnit" class="form-select" :value="units.selectedUnitId"
              @change="units.selectUnit(Number($event.target.value))">
        <option v-for="unit in units.list" :key="unit.id" :value="unit.id">
          {{ unit.code }} — {{ unit.name }}
        </option>
      </select>
    </div>

    <!-- 청정 기준 기간 -->
    <div class="card mb-3">
      <div class="card-body">
        <h3 class="h6 mb-3">청정 기준 기간</h3>
        <p class="small text-secondary">
          기대값 모델은 이 구간으로만 학습합니다. 지정하지 않으면 세정 이력에서 자동 산정합니다.
        </p>

        <table v-if="periods.length" class="table table-sm align-middle">
          <thead>
            <tr>
              <th scope="col">시작</th><th scope="col">종료</th><th scope="col">경로</th>
              <th scope="col">활성</th><th scope="col"></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="period in periods" :key="period.id">
              <td class="small">{{ formatDate(period.start_at) }}</td>
              <td class="small">{{ formatDate(period.end_at) }}</td>
              <td class="small">{{ period.source }}</td>
              <td>
                <span class="badge" :class="period.is_active ? 'text-bg-success' : 'text-bg-light'">
                  {{ period.is_active ? '활성' : '비활성' }}
                </span>
              </td>
              <td class="text-end">
                <button class="btn btn-sm btn-outline-secondary me-1" @click="preview(period)">
                  미리보기
                </button>
                <button class="btn btn-sm btn-outline-danger" @click="removePeriod(period)">삭제</button>
              </td>
            </tr>
          </tbody>
        </table>

        <div class="row g-2 align-items-end">
          <div class="col-6 col-lg-3">
            <label for="bpStart" class="form-label small">시작</label>
            <input id="bpStart" v-model="newPeriod.start_at" type="datetime-local"
                   class="form-control form-control-sm" />
          </div>
          <div class="col-6 col-lg-3">
            <label for="bpEnd" class="form-label small">종료</label>
            <input id="bpEnd" v-model="newPeriod.end_at" type="datetime-local"
                   class="form-control form-control-sm" />
          </div>
          <div class="col-8 col-lg-4">
            <label for="bpNote" class="form-label small">비고</label>
            <input id="bpNote" v-model.trim="newPeriod.note" class="form-control form-control-sm" />
          </div>
          <div class="col-4 col-lg-2">
            <button class="btn btn-sm btn-outline-primary w-100"
                    :disabled="!newPeriod.start_at || !newPeriod.end_at" @click="addPeriod">
              추가
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 재학습 -->
    <div class="card mb-3">
      <div class="card-body">
        <h3 class="h6 mb-3">재학습</h3>
        <div class="row g-3 align-items-end">
          <div class="col-12 col-lg-4">
            <span class="form-label small d-block">대상</span>
            <div v-for="[value, label] in Object.entries(TARGET_LABELS)" :key="value"
                 class="form-check form-check-inline">
              <input :id="`t-${value}`" v-model="trainForm.targets" :value="value" type="checkbox"
                     class="form-check-input" />
              <label :for="`t-${value}`" class="form-check-label small">{{ label }}</label>
            </div>
          </div>
          <div class="col-6 col-lg-3">
            <label for="mdAlgo" class="form-label small">알고리즘</label>
            <select id="mdAlgo" v-model="trainForm.algorithm" class="form-select form-select-sm">
              <option value="">설정값 사용</option>
              <option value="GBR">GBR</option>
              <option value="RIDGE">RIDGE</option>
            </select>
          </div>
          <div class="col-6 col-lg-3">
            <button class="btn btn-primary btn-sm w-100"
                    :disabled="busy || !trainForm.targets.length" @click="train">
              <span v-if="busy" class="spinner-border spinner-border-sm me-1"></span>
              재학습 실행
            </button>
          </div>
        </div>

        <div v-if="busy" class="progress mt-3" style="height: 0.5rem">
          <div class="progress-bar progress-bar-striped progress-bar-animated"
               :style="{ width: `${job.progress.value}%` }"></div>
        </div>
        <p v-if="busy" class="small text-secondary mt-1 mb-0">{{ job.stage.value }}</p>

        <div v-if="error" class="alert alert-danger py-2 small mt-3">{{ error.message }}</div>

        <p class="small text-secondary mt-2 mb-0">
          재학습 결과는 <strong>비활성 상태로 저장</strong>됩니다. 지표를 비교하고 승인해야
          활성화되며, 그 전까지 기존 활성 모델이 그대로 쓰입니다.
        </p>
      </div>
    </div>

    <!-- 버전 목록 -->
    <div v-for="[target, label] in Object.entries(TARGET_LABELS)" :key="target" class="mb-4">
      <h3 class="h6">{{ label }} 모델</h3>
      <EmptyState v-if="!byTarget[target].length" title="학습된 모델이 없습니다." icon="bi-cpu" />
      <table v-else class="table table-sm align-middle">
        <thead>
          <tr>
            <th scope="col">버전</th><th scope="col">알고리즘</th><th scope="col">학습 기간</th>
            <th scope="col" class="text-end">표본</th><th scope="col" class="text-end">R²</th>
            <th scope="col" class="text-end">MAE</th><th scope="col">상태</th>
            <th scope="col">학습 일시</th><th scope="col"></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="version in byTarget[target]" :key="version.id">
            <td class="small">v{{ version.version }}</td>
            <td class="small">{{ version.algorithm }}</td>
            <td class="small">
              {{ formatDate(version.baseline_start) }} ~ {{ formatDate(version.baseline_end) }}
            </td>
            <td class="small text-end">{{ formatCount(version.training_rows) }}</td>
            <td class="small text-end">{{ fmt(version.metrics?.r2) }}</td>
            <td class="small text-end">{{ fmt(version.metrics?.mae) }}</td>
            <td>
              <span class="badge" :class="version.is_active ? 'text-bg-success' : 'text-bg-light'">
                {{ version.is_active ? '활성' : '대기' }}
              </span>
            </td>
            <td class="small">{{ formatDateTime(version.trained_at) }}</td>
            <td class="text-end">
              <button class="btn btn-sm btn-outline-secondary me-1" @click="compare(version)">
                비교
              </button>
              <button v-if="!version.is_active" class="btn btn-sm btn-outline-primary"
                      @click="activate(version)">활성화</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 신·구 비교 -->
    <div v-if="comparison" class="card">
      <div class="card-body">
        <h3 class="h6 mb-3">신·구 모델 비교</h3>
        <table class="table table-sm mb-3">
          <thead>
            <tr>
              <th scope="col">구분</th><th scope="col">버전</th><th scope="col">알고리즘</th>
              <th scope="col" class="text-end">R²</th><th scope="col" class="text-end">MAE</th>
              <th scope="col" class="text-end">RMSE</th><th scope="col" class="text-end">학습 표본</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="[key, row] in [['후보', comparison.candidate], ['현재 활성', comparison.current]]"
                :key="key">
              <td class="small">{{ key }}</td>
              <template v-if="row">
                <td class="small">v{{ row.version }}</td>
                <td class="small">{{ row.algorithm }}</td>
                <td class="small text-end">{{ fmt(row.metrics?.r2) }}</td>
                <td class="small text-end">{{ fmt(row.metrics?.mae) }}</td>
                <td class="small text-end">{{ fmt(row.metrics?.rmse) }}</td>
                <td class="small text-end">{{ formatCount(row.training_rows) }}</td>
              </template>
              <td v-else colspan="6" class="small text-secondary">없음</td>
            </tr>
          </tbody>
        </table>
        <button v-if="!comparison.candidate.is_active" class="btn btn-primary btn-sm me-2"
                @click="activate(comparison.candidate)">이 모델로 교체</button>
        <button class="btn btn-outline-secondary btn-sm" @click="comparison = null">닫기</button>
      </div>
    </div>
  </div>
</template>
