<script setup>
import { computed, onMounted, ref, watch } from 'vue'

import * as api from '@/api/maintenance'
import EmptyState from '@/components/common/EmptyState.vue'
import FileDropzone from '@/components/upload/FileDropzone.vue'
import { useJobPolling } from '@/composables/useJobPolling'
import { useToast } from '@/composables/useToast'
import { useUnitsStore } from '@/stores/units'
import { formatCount, formatCurrency, formatDate } from '@/utils/format'

const units = useUnitsStore()
const toast = useToast()
const job = useJobPolling({ key: 'maintenance.import' })

const records = ref([])
const filter = ref('PENDING_CANDIDATES')
const busy = ref(false)
const error = ref(null)
const importReport = ref(null)

const FILTERS = [
  ['PENDING_CANDIDATES', '검토 대기 후보'],
  ['ALL', '전체'],
  ['ACCEPTED', '승인됨'],
  ['IGNORED', '무시됨'],
]

const candidateCount = computed(
  () => records.value.filter((r) => r.is_fouling_related && r.review_status === 'PENDING').length,
)

onMounted(async () => {
  await units.fetchUnits()
  await load()
})
watch(() => units.selectedUnitId, load)
watch(filter, load)

async function load() {
  if (!units.selectedUnitId) return
  const params = { unit_id: units.selectedUnitId, page_size: 200 }
  if (filter.value === 'PENDING_CANDIDATES') {
    params.is_fouling_related = true
    params.review_status = 'PENDING'
  } else if (filter.value !== 'ALL') {
    params.review_status = filter.value
  }
  const { data } = await api.fetchMaintenanceRecords(params)
  records.value = data.results ?? data
}

async function onFile(file) {
  if (!units.selectedUnitId) return
  busy.value = true
  error.value = null
  importReport.value = null
  try {
    const { data } = await api.uploadMaintenance({ unitId: units.selectedUnitId, file })
    const outcome = await job.start(data.job_id)
    if (outcome.status === 'SUCCESS') {
      importReport.value = outcome.result
      if (outcome.result.is_loadable) {
        toast.push(
          `${formatCount(outcome.result.row_loaded)}건을 읽어 ` +
            `${formatCount(outcome.result.cleaning_candidates)}건의 세정 후보를 찾았습니다.`,
          'success',
        )
        await load()
      }
    } else {
      error.value = outcome.error
    }
  } catch (err) {
    error.value = err.parsed ?? { message: '업로드에 실패했습니다.' }
  } finally {
    busy.value = false
  }
}

async function accept(record) {
  if (!window.confirm(`"${record.title}" 을(를) 세정 이력으로 등록할까요?`)) return
  await api.acceptRecord(record.id)
  toast.push('세정 이력으로 등록했습니다.', 'success')
  await load()
}

async function ignore(record) {
  await api.ignoreRecord(record.id)
  toast.push('무시 처리했습니다.', 'info')
  await load()
}

async function acceptAll() {
  const targets = records.value.filter(
    (r) => r.is_fouling_related && r.review_status === 'PENDING' && r.match_category === 'CLEANING',
  )
  if (!targets.length) return
  if (!window.confirm(`세정 후보 ${targets.length}건을 모두 등록할까요?`)) return
  for (const record of targets) await api.acceptRecord(record.id)
  toast.push(`${targets.length}건을 등록했습니다.`, 'success')
  await load()
}

/** 업로드 파일에서 온 문자열이므로 반드시 이스케이프한 뒤에만 마크업을 넣는다. */
function escapeHtml(text) {
  return String(text ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;')
}

/** 매칭된 키워드를 제목에서 강조 표시한다 (specs/10 §3.3). */
function highlight(record) {
  let text = escapeHtml(record.title)
  for (const match of record.matched_keywords ?? []) {
    const keyword = escapeHtml(match.keyword)
    if (keyword) text = text.replaceAll(keyword, `<mark>${keyword}</mark>`)
  }
  return text
}

const CATEGORY_LABELS = {
  CLEANING: ['세정', 'success'],
  FOULING: ['오염 징후', 'warning'],
  INSPECTION: ['점검', 'secondary'],
}
</script>

<template>
  <div>
    <div class="card mb-3">
      <div class="card-body">
        <div class="row g-3 align-items-end">
          <div class="col-12 col-md-4">
            <label for="mUnit" class="form-label">호기</label>
            <select
              id="mUnit"
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
          <div class="col-12 col-md-8">
            <FileDropzone accept=".csv,.xlsx,.xls" :disabled="busy" @select="onFile" />
            <p class="form-text mb-0">CSV 또는 엑셀(.xlsx, .xls) 파일을 올리면 오염 관련 이력을 자동 추출합니다.</p>
          </div>
        </div>

        <div v-if="busy" class="progress mt-3" style="height: 0.5rem">
          <div class="progress-bar progress-bar-striped progress-bar-animated"
               :style="{ width: `${job.progress.value}%` }"></div>
        </div>

        <div v-if="error" class="alert alert-danger mt-3 py-2 small" role="alert">{{ error.message }}</div>

        <div v-if="importReport && !importReport.is_loadable" class="alert alert-danger mt-3 py-2 small">
          <p class="fw-semibold mb-1">파일을 읽을 수 없습니다.</p>
          <ul class="mb-0 ps-3">
            <li v-for="e in importReport.errors" :key="e.code">
              {{ e.message }}
              <span v-if="e.fields">— 찾지 못한 항목: {{ e.fields.join(', ') }}</span>
              <span v-if="e.header" class="text-secondary"> (파일 헤더: {{ e.header.join(', ') }})</span>
            </li>
          </ul>
        </div>
      </div>
    </div>

    <div class="d-flex justify-content-between align-items-center mb-2">
      <ul class="nav nav-pills">
        <li v-for="[value, label] in FILTERS" :key="value" class="nav-item">
          <button class="nav-link" :class="{ active: filter === value }" @click="filter = value">
            {{ label }}
            <span v-if="value === 'PENDING_CANDIDATES' && candidateCount" class="badge text-bg-light ms-1">
              {{ candidateCount }}
            </span>
          </button>
        </li>
      </ul>
      <button v-if="candidateCount" class="btn btn-sm btn-primary" @click="acceptAll">
        세정 후보 일괄 등록
      </button>
    </div>

    <EmptyState
      v-if="!records.length"
      title="표시할 정비 이력이 없습니다."
      description="정비 이력 파일을 업로드하면 오염 관련 이력이 자동으로 추출됩니다."
      icon="bi-wrench"
    />

    <table v-else class="table table-sm align-middle">
      <thead>
        <tr>
          <th scope="col">작업일</th>
          <th scope="col">제목</th>
          <th scope="col">분류</th>
          <th scope="col" class="text-end">점수</th>
          <th scope="col" class="text-end">비용</th>
          <th scope="col">상태</th>
          <th scope="col"></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="record in records" :key="record.id">
          <td class="small">{{ formatDate(record.work_date) }}</td>
          <td class="small">
            <!-- highlight() 가 이스케이프 후 <mark> 만 넣는다 -->
            <span v-html="highlight(record)"></span>
            <div v-if="record.description" class="text-secondary" style="font-size: 0.75rem">
              {{ record.description }}
            </div>
          </td>
          <td>
            <span
              v-if="CATEGORY_LABELS[record.match_category]"
              class="badge"
              :class="`text-bg-${CATEGORY_LABELS[record.match_category][1]}`"
            >
              {{ CATEGORY_LABELS[record.match_category][0] }}
            </span>
            <span v-else class="text-secondary">–</span>
          </td>
          <td class="small text-end">{{ record.match_score?.toFixed(1) ?? '–' }}</td>
          <td class="small text-end">{{ formatCurrency(record.cost, { withEok: false }) }}</td>
          <td>
            <span class="badge text-bg-light">{{ record.review_status }}</span>
          </td>
          <td class="text-end">
            <template v-if="record.review_status === 'PENDING'">
              <button
                v-if="record.match_category === 'CLEANING'"
                class="btn btn-sm btn-outline-primary me-1"
                @click="accept(record)"
              >
                세정으로 등록
              </button>
              <button class="btn btn-sm btn-outline-secondary" @click="ignore(record)">무시</button>
            </template>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
