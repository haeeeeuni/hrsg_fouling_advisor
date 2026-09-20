<script setup>
import { onMounted, reactive, ref, watch } from 'vue'

import * as maintenanceApi from '@/api/maintenance'
import EmptyState from '@/components/common/EmptyState.vue'
import { useToast } from '@/composables/useToast'
import { useUnitsStore } from '@/stores/units'
import { formatCurrency, formatDate } from '@/utils/format'

const store = useUnitsStore()
const toast = useToast()

const events = ref([])
const editing = ref(null)
const error = ref(null)

const METHODS = [
  ['CHEMICAL', '화학세정'],
  ['WATER_WASH', '수세'],
  ['DRY_ICE', '드라이아이스'],
  ['MECHANICAL', '기계적 청소'],
  ['SOOT_BLOWING', '수트 블로잉'],
  ['OTHER', '기타'],
]

const blank = {
  cleaned_at: '',
  cleaned_end_at: '',
  method: 'CHEMICAL',
  method_detail: '',
  cost: null,
  outage_days: 2,
  note: '',
}
const form = reactive({ ...blank })

onMounted(async () => {
  await store.fetchUnits()
  await load()
})
watch(() => store.selectedUnitId, load)

async function load() {
  if (!store.selectedUnitId) return
  const { data } = await maintenanceApi.fetchCleaningEvents({ unit_id: store.selectedUnitId })
  events.value = data.results ?? data
}

function startCreate() {
  editing.value = 'new'
  error.value = null
  Object.assign(form, blank)
}

function startEdit(event) {
  editing.value = event.id
  error.value = null
  Object.assign(form, {
    ...event,
    cleaned_at: event.cleaned_at?.slice(0, 16),
    cleaned_end_at: event.cleaned_end_at?.slice(0, 16) ?? '',
  })
}

async function save() {
  error.value = null
  const payload = {
    unit: store.selectedUnitId,
    ...form,
    cleaned_end_at: form.cleaned_end_at || null,
    cost: form.cost === '' ? null : form.cost,
  }
  try {
    const res =
      editing.value === 'new'
        ? await maintenanceApi.createCleaningEvent(payload)
        : await maintenanceApi.updateCleaningEvent(editing.value, payload)
    editing.value = null
    await load()
    toast.push(res.data.warning ?? '저장했습니다.', res.data.warning ? 'warning' : 'success')
  } catch (err) {
    error.value = err.parsed
  }
}

async function remove(event) {
  if (
    !window.confirm(
      `${formatDate(event.cleaned_at)} 세정 이력을 삭제할까요?\n` +
        '청정 기준 기간 산정, 추세 구간 절단, 전후 비교, 대시보드 마커에 영향을 줍니다.\n' +
        '과거 분석 결과의 수치는 그대로 유지됩니다.',
    )
  )
    return
  await maintenanceApi.deleteCleaningEvent(event.id)
  await load()
  toast.push('삭제했습니다.', 'success')
}
</script>

<template>
  <div>
    <div class="row g-3 align-items-end mb-3">
      <div class="col-12 col-md-5">
        <label for="ceUnit" class="form-label">호기</label>
        <select
          id="ceUnit"
          class="form-select"
          :value="store.selectedUnitId"
          @change="store.selectUnit(Number($event.target.value))"
        >
          <option v-for="unit in store.list" :key="unit.id" :value="unit.id">
            {{ unit.code }} — {{ unit.name }}
          </option>
        </select>
      </div>
      <div class="col-12 col-md-7 text-md-end">
        <button class="btn btn-primary btn-sm" @click="startCreate">세정 이력 추가</button>
      </div>
    </div>

    <EmptyState
      v-if="!events.length"
      title="등록된 세정 이력이 없습니다."
      description="세정 이력은 청정 기준 기간 산정과 추세 구간 절단의 기준이 됩니다."
      icon="bi-droplet"
    />

    <table v-else class="table table-sm align-middle">
      <thead>
        <tr>
          <th scope="col">세정 일자</th>
          <th scope="col">종료 일자</th>
          <th scope="col">방법</th>
          <th scope="col" class="text-end">비용</th>
          <th scope="col" class="text-end">정지 일수</th>
          <th scope="col">등록 경로</th>
          <th scope="col"></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="event in events" :key="event.id">
          <td>{{ formatDate(event.cleaned_at) }}</td>
          <td>{{ formatDate(event.cleaned_end_at) }}</td>
          <td>{{ event.method_label }}</td>
          <td class="text-end">{{ formatCurrency(event.cost, { withEok: false }) }}</td>
          <td class="text-end">{{ event.outage_days ?? '–' }}</td>
          <td class="small">{{ event.source === 'MANUAL' ? '수동 등록' : '이력 추출' }}</td>
          <td class="text-end">
            <button class="btn btn-sm btn-outline-secondary me-1" @click="startEdit(event)">수정</button>
            <button class="btn btn-sm btn-outline-danger" @click="remove(event)">삭제</button>
          </td>
        </tr>
      </tbody>
    </table>

    <div v-if="editing" class="card mt-3">
      <div class="card-body">
        <h3 class="h6 mb-3">{{ editing === 'new' ? '세정 이력 추가' : '세정 이력 수정' }}</h3>
        <div class="row g-3">
          <div class="col-6 col-lg-3">
            <label for="cleanedAt" class="form-label">세정 일시</label>
            <input id="cleanedAt" v-model="form.cleaned_at" type="datetime-local" class="form-control" />
          </div>
          <div class="col-6 col-lg-3">
            <label for="cleanedEnd" class="form-label">종료 일시</label>
            <input id="cleanedEnd" v-model="form.cleaned_end_at" type="datetime-local" class="form-control" />
          </div>
          <div class="col-6 col-lg-3">
            <label for="method" class="form-label">세정 방법</label>
            <select id="method" v-model="form.method" class="form-select">
              <option v-for="[value, label] in METHODS" :key="value" :value="value">{{ label }}</option>
            </select>
          </div>
          <div class="col-6 col-lg-3">
            <label for="detail" class="form-label">방법 상세</label>
            <input id="detail" v-model.trim="form.method_detail" class="form-control" />
          </div>
          <div class="col-6 col-lg-3">
            <label for="cost" class="form-label">비용 (원)</label>
            <input id="cost" v-model.number="form.cost" type="number" class="form-control" />
          </div>
          <div class="col-6 col-lg-3">
            <label for="outage" class="form-label">정지 일수</label>
            <input id="outage" v-model.number="form.outage_days" type="number" step="0.5" class="form-control" />
          </div>
          <div class="col-12">
            <label for="note" class="form-label">비고</label>
            <textarea id="note" v-model.trim="form.note" class="form-control" rows="2"></textarea>
          </div>
        </div>

        <div v-if="error" class="alert alert-danger py-2 small mt-3" role="alert">
          {{ error.message }}
          <ul v-if="error.details" class="mb-0 mt-1 ps-3">
            <li v-for="(messages, field) in error.details" :key="field">
              {{ field }}: {{ messages.join(', ') }}
            </li>
          </ul>
        </div>

        <div class="mt-3">
          <button class="btn btn-primary me-2" @click="save">저장</button>
          <button class="btn btn-outline-secondary" @click="editing = null">취소</button>
        </div>
      </div>
    </div>
  </div>
</template>
