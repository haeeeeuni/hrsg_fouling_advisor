<script setup>
import { computed, onMounted, ref, watch } from 'vue'

import * as maintenanceApi from '@/api/maintenance'
import * as reportsApi from '@/api/reports'
import EmptyState from '@/components/common/EmptyState.vue'
import { useToast } from '@/composables/useToast'
import { useUnitsStore } from '@/stores/units'
import { formatCount, formatDate, formatPercent } from '@/utils/format'

const units = useUnitsStore()
const toast = useToast()

const events = ref([])
const history = ref([])
const result = ref(null)
const form = ref({ cleaningEventId: null, windowDays: 30, beforeOffsetDays: 0, afterOffsetDays: 1 })
const busy = ref(false)
const error = ref(null)

const canRun = computed(() => form.value.cleaningEventId && !busy.value)

onMounted(async () => {
  await units.fetchUnits()
  await load()
})
watch(() => units.selectedUnitId, load)

async function load() {
  if (!units.selectedUnitId) return
  result.value = null
  const [eventsRes, historyRes] = await Promise.all([
    maintenanceApi.fetchCleaningEvents({ unit_id: units.selectedUnitId }),
    maintenanceApi.fetchComparisons({ unit_id: units.selectedUnitId }),
  ])
  events.value = eventsRes.data.results ?? eventsRes.data
  history.value = historyRes.data.results ?? historyRes.data
  form.value.cleaningEventId = events.value[0]?.id ?? null
}

async function run() {
  if (!canRun.value) return
  busy.value = true
  error.value = null
  try {
    const { data } = await maintenanceApi.createComparison({
      cleaning_event_id: form.value.cleaningEventId,
      window_days: form.value.windowDays,
      before_offset_days: form.value.beforeOffsetDays,
      after_offset_days: form.value.afterOffsetDays,
    })
    result.value = data
    await load()
    result.value = data
    toast.push('세정 전후 비교를 생성했습니다.', 'success')
  } catch (err) {
    error.value = err.parsed ?? { message: '비교를 생성할 수 없습니다.' }
  } finally {
    busy.value = false
  }
}

async function show(id) {
  const { data } = await maintenanceApi.fetchComparison(id)
  result.value = data
}

async function exportReport(format) {
  if (!result.value) return
  const { data } = await reportsApi.exportComparison(result.value.id, format)
  await reportsApi.downloadReport(data.id, data.file_name)
  toast.push('리포트를 내려받았습니다.', 'success')
}
</script>

<template>
  <div>
    <div class="alert alert-secondary py-2 small" role="note">
      부하·외기 조건이 다르면 차압과 스택온도가 자연히 달라집니다.
      비교는 <strong>양쪽 모두 표본이 있는 공통 군집</strong>에서만 수행합니다.
    </div>

    <EmptyState
      v-if="!events.length"
      title="등록된 세정 이력이 없습니다."
      description="정비 이력에서 세정 후보를 승인하거나 관리자 콘솔에서 직접 등록하세요."
      icon="bi-droplet"
    />

    <template v-else>
      <div class="card mb-3">
        <div class="card-body">
          <div class="row g-3 align-items-end">
            <div class="col-12 col-lg-5">
              <label for="cmpEvent" class="form-label">세정 이력</label>
              <select id="cmpEvent" v-model.number="form.cleaningEventId" class="form-select" :disabled="busy">
                <option v-for="event in events" :key="event.id" :value="event.id">
                  {{ formatDate(event.cleaned_at) }} — {{ event.method_label }}
                </option>
              </select>
            </div>
            <div class="col-4 col-lg-2">
              <label for="cmpWindow" class="form-label">비교 윈도(일)</label>
              <input id="cmpWindow" v-model.number="form.windowDays" type="number" class="form-control" :disabled="busy" />
            </div>
            <div class="col-4 col-lg-2">
              <label for="cmpBefore" class="form-label">전 오프셋</label>
              <input id="cmpBefore" v-model.number="form.beforeOffsetDays" type="number" class="form-control" :disabled="busy" />
            </div>
            <div class="col-4 col-lg-2">
              <label for="cmpAfter" class="form-label">후 오프셋</label>
              <input id="cmpAfter" v-model.number="form.afterOffsetDays" type="number" class="form-control" :disabled="busy" />
            </div>
          </div>

          <div v-if="error" class="alert alert-danger mt-3 py-2 small" role="alert">{{ error.message }}</div>

          <button class="btn btn-primary mt-3" :disabled="!canRun" @click="run">
            <span v-if="busy" class="spinner-border spinner-border-sm me-2"></span>
            비교 생성
          </button>
        </div>
      </div>

      <div v-if="result" class="card mb-3">
        <div class="card-body">
          <div class="d-flex justify-content-between align-items-center mb-3">
            <h2 class="h6 mb-0">비교 결과</h2>
            <div>
              <button class="btn btn-sm btn-outline-secondary me-1" @click="exportReport('pdf')">PDF</button>
              <button class="btn btn-sm btn-outline-secondary" @click="exportReport('xlsx')">엑셀</button>
            </div>
          </div>

          <p class="small text-secondary">
            세정 전 {{ formatDate(result.before_start) }} ~ {{ formatDate(result.before_end) }} /
            세정 후 {{ formatDate(result.after_start) }} ~ {{ formatDate(result.after_end) }}
          </p>

          <div v-if="!result.is_comparable" class="alert alert-warning py-2 small">
            <p v-for="w in result.warnings" :key="w.code" class="mb-0">{{ w.message }}</p>
          </div>

          <template v-else>
            <p class="small">
              공통 군집 <code>{{ result.common_clusters.join(', ') }}</code> ·
              표본 전 {{ formatCount(result.metrics.n_before) }} / 후 {{ formatCount(result.metrics.n_after) }} ·
              회복률 <strong>{{ formatPercent((result.recovery_ratio ?? 0) * 100) }}</strong>
            </p>

            <table class="table table-sm align-middle">
              <thead>
                <tr>
                  <th scope="col">지표</th>
                  <th scope="col" class="text-end">세정 전</th>
                  <th scope="col" class="text-end">세정 후</th>
                  <th scope="col" class="text-end">개선량</th>
                  <th scope="col" class="text-end">개선율</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in result.metrics.rows" :key="row.key" :class="row.is_primary ? 'fw-semibold' : ''">
                  <td class="small">
                    {{ row.label }}
                    <span v-if="row.is_primary" class="badge text-bg-primary ms-1">주 지표</span>
                  </td>
                  <td class="small text-end">{{ row.before ?? '–' }}</td>
                  <td class="small text-end">{{ row.after ?? '–' }}</td>
                  <td class="small text-end">{{ row.delta ?? '–' }}</td>
                  <td class="small text-end">
                    {{ row.delta_pct !== null ? `${row.delta_pct > 0 ? '+' : ''}${row.delta_pct}%` : '–' }}
                  </td>
                </tr>
              </tbody>
            </table>
            <p class="small text-secondary">
              잔차 기반 지표가 주 지표입니다(운전 조건 차이를 보정). 원시 평균은 참고 지표입니다.
            </p>

            <details v-if="result.p_values?.residual_dp">
              <summary class="small text-secondary">통계적 유의성</summary>
              <ul class="small mt-2 mb-0 ps-3">
                <li v-for="(pv, key) in result.p_values" :key="key">
                  {{ key }} — t-검정 p={{ pv.t_p_value?.toExponential(2) ?? '–' }},
                  Mann-Whitney p={{ pv.u_p_value?.toExponential(2) ?? '–' }}
                </li>
              </ul>
            </details>
          </template>
        </div>
      </div>

      <div v-if="history.length" class="card">
        <div class="card-body">
          <h2 class="h6 mb-3">비교 이력</h2>
          <table class="table table-sm align-middle mb-0">
            <thead>
              <tr>
                <th scope="col">생성 일시</th>
                <th scope="col">세정 일자</th>
                <th scope="col">공통 군집</th>
                <th scope="col" class="text-end">회복률</th>
                <th scope="col"></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in history" :key="row.id">
                <td class="small">{{ formatDate(row.created_at) }}</td>
                <td class="small">{{ formatDate(row.cleaned_at) }}</td>
                <td class="small">{{ row.common_clusters.join(', ') || '–' }}</td>
                <td class="small text-end">{{ formatPercent((row.recovery_ratio ?? 0) * 100) }}</td>
                <td class="text-end">
                  <button class="btn btn-sm btn-outline-secondary" @click="show(row.id)">보기</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </div>
</template>
