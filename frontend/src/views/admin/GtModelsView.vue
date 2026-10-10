<script setup>
/**
 * GT 운전 한계 참조표 (specs/06 REF-1). 지금 값은 [임시값] — 실무 자료를 받으면 여기서 교체하고
 * '임시값' 표시를 해제한다. 수정할 때 version 을 함께 보내 동시 편집을 막는다(specs/08 ADM-7).
 */
import { onMounted, ref } from 'vue'

import * as api from '@/api/reference'
import ErrorAlert from '@/components/admin/ErrorAlert.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import { useToast } from '@/composables/useToast'

const toast = useToast()

const FIELDS = [
  { key: 'name', label: '모델 이름', type: 'text' },
  { key: 'manufacturer', label: '제조사', type: 'text' },
  { key: 'rated_gt_mw', label: 'GT 정격', unit: 'MW' },
  { key: 'rated_st_mw', label: 'ST 정격 (선택)', unit: 'MW' },
  { key: 'design_backpressure_kpa', label: '설계 배압', unit: 'kPa' },
  { key: 'backpressure_alarm_kpa', label: '배압 경보', unit: 'kPa' },
  { key: 'backpressure_trip_kpa', label: '배압 트립', unit: 'kPa' },
  { key: 'design_exhaust_temp_c', label: '설계 배기온도', unit: '℃' },
  { key: 'exhaust_temp_alarm_c', label: '배기온도 경보', unit: '℃' },
  { key: 'exhaust_temp_trip_c', label: '배기온도 트립', unit: '℃' },
  { key: 'design_stack_temp_c', label: '설계 굴뚝 온도', unit: '℃' },
]

const rows = ref([])
const loaded = ref(false)
const loadError = ref(null)
const editing = ref(null) // null | 'new' | id
const draft = ref({})
const saveError = ref(null)
const importResult = ref(null)
const importError = ref(null)
const fileInput = ref(null)

onMounted(load)

async function load() {
  try {
    rows.value = (await api.fetchGtModels()).data
  } catch (err) {
    loadError.value = err.parsed
  } finally {
    loaded.value = true
  }
}

function startNew() {
  editing.value = 'new'
  saveError.value = null
  draft.value = Object.fromEntries(FIELDS.map((f) => [f.key, f.type === 'text' ? '' : null]))
  draft.value.is_placeholder = false
  draft.value.note = ''
}

function startEdit(row) {
  editing.value = row.id
  saveError.value = null
  draft.value = { ...row }
}

async function save() {
  saveError.value = null
  try {
    if (editing.value === 'new') await api.createGtModel(draft.value)
    else await api.updateGtModel(editing.value, draft.value)
    editing.value = null
    toast.push('저장했습니다.', 'success')
    await load()
  } catch (err) {
    saveError.value = err.parsed
  }
}

async function deactivate(row) {
  if (!window.confirm(`"${row.name}" 을(를) 사용 중지할까요? 계산기 목록에서 빠집니다.`)) return
  try {
    await api.deactivateGtModel(row.id)
    toast.push('사용 중지했습니다.', 'success')
    await load()
  } catch (err) {
    toast.push(err.parsed?.message ?? '처리하지 못했습니다.', 'danger')
  }
}

async function downloadTemplate() {
  const { data } = await api.downloadGtTemplate()
  const url = URL.createObjectURL(data)
  const link = document.createElement('a')
  link.href = url
  link.download = 'gt_models.xlsx'
  link.click()
  URL.revokeObjectURL(url)
}

async function onImport(event) {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file) return
  importResult.value = null
  importError.value = null
  try {
    importResult.value = (await api.importGtModels(file)).data
    await load()
  } catch (err) {
    importError.value = err.parsed
  }
}
</script>

<template>
  <div>
    <div class="alert alert-warning small py-2" role="note">
      <i class="bi bi-exclamation-triangle-fill me-1" aria-hidden="true"></i>
      현재 값은 <strong>임시값</strong>입니다. 실무진에게 받은 참조표로 교체하고 '임시값' 표시를 해제하세요.
      사용자에게는 한계값 원본 대신 상태(정상·경보·트립)와 경보 대비 비율만 보입니다.
    </div>

    <div class="d-flex flex-wrap gap-2 mb-3">
      <button class="btn btn-primary btn-sm" type="button" @click="startNew">
        <i class="bi bi-plus-lg me-1" aria-hidden="true"></i>모델 추가
      </button>
      <button class="btn btn-outline-secondary btn-sm" type="button" @click="downloadTemplate">
        <i class="bi bi-download me-1" aria-hidden="true"></i>xlsx 양식 내려받기
      </button>
      <button class="btn btn-outline-secondary btn-sm" type="button" @click="fileInput.click()">
        <i class="bi bi-upload me-1" aria-hidden="true"></i>xlsx 가져오기
      </button>
      <input ref="fileInput" type="file" accept=".xlsx" class="d-none" aria-label="xlsx 파일 선택" @change="onImport" />
    </div>

    <div v-if="importResult" class="alert alert-success small py-2" role="status">
      가져오기 완료 — 새로 {{ importResult.created }}건, 수정 {{ importResult.updated }}건
    </div>
    <ErrorAlert :error="importError" />

    <form v-if="editing" class="card mb-3" novalidate @submit.prevent="save">
      <div class="card-body">
        <h2 class="h6">{{ editing === 'new' ? 'GT 모델 추가' : `${draft.name} 수정` }}</h2>
        <div class="row g-2">
          <div v-for="field in FIELDS" :key="field.key" class="col-6 col-md-4 col-xl-3">
            <label :for="`gt-${field.key}`" class="form-label small">{{ field.label }}</label>
            <div class="input-group input-group-sm">
              <input
                v-if="field.type === 'text'"
                :id="`gt-${field.key}`"
                v-model.trim="draft[field.key]"
                class="form-control"
              />
              <input
                v-else
                :id="`gt-${field.key}`"
                v-model.number="draft[field.key]"
                type="number"
                step="any"
                class="form-control"
              />
              <span v-if="field.unit" class="input-group-text">{{ field.unit }}</span>
            </div>
          </div>
          <div class="col-12 col-md-8">
            <label for="gt-note" class="form-label small">비고(출처 등)</label>
            <input id="gt-note" v-model.trim="draft.note" class="form-control form-control-sm" />
          </div>
          <div class="col-12 col-md-4 d-flex align-items-end">
            <div class="form-check">
              <input id="gt-placeholder" v-model="draft.is_placeholder" class="form-check-input" type="checkbox" />
              <label for="gt-placeholder" class="form-check-label small">임시값</label>
            </div>
          </div>
        </div>
        <ErrorAlert class="mt-3" :error="saveError" />
        <div class="mt-3">
          <button class="btn btn-sm btn-primary me-2" type="submit">저장</button>
          <button class="btn btn-sm btn-outline-secondary" type="button" @click="editing = null">취소</button>
        </div>
      </div>
    </form>

    <ErrorAlert :error="loadError" />
    <div v-if="!loaded" class="text-center py-4">
      <div class="spinner-border text-primary" role="status"><span class="visually-hidden">불러오는 중</span></div>
    </div>
    <EmptyState v-else-if="!rows.length" title="등록된 GT 모델이 없습니다." icon="bi-fan" />
    <div v-else class="table-responsive">
      <table class="table table-sm align-middle">
        <thead>
          <tr>
            <th scope="col">모델</th>
            <th scope="col" class="text-end">정격 GT/ST (MW)</th>
            <th scope="col" class="text-end">배압 설계·경보·트립 (kPa)</th>
            <th scope="col" class="text-end">배기온도 설계·경보·트립 (℃)</th>
            <th scope="col" class="text-end">설계 굴뚝 (℃)</th>
            <th scope="col">상태</th>
            <th scope="col"><span class="visually-hidden">작업</span></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="row.id" :class="row.is_active ? '' : 'text-secondary'">
            <th scope="row">
              {{ row.name }}
              <div class="small text-secondary fw-normal">{{ row.manufacturer }} · v{{ row.version }}</div>
            </th>
            <td class="text-end">{{ row.rated_gt_mw }} / {{ row.rated_st_mw ?? '–' }}</td>
            <td class="text-end">{{ row.design_backpressure_kpa }} · {{ row.backpressure_alarm_kpa }} · {{ row.backpressure_trip_kpa }}</td>
            <td class="text-end">{{ row.design_exhaust_temp_c }} · {{ row.exhaust_temp_alarm_c }} · {{ row.exhaust_temp_trip_c }}</td>
            <td class="text-end">{{ row.design_stack_temp_c }}</td>
            <td>
              <span v-if="row.is_placeholder" class="badge text-bg-warning me-1">임시값</span>
              <span class="badge" :class="row.is_active ? 'text-bg-secondary' : 'text-bg-light'">
                {{ row.is_active ? '사용' : '중지' }}
              </span>
            </td>
            <td class="text-end">
              <button class="btn btn-sm btn-outline-secondary me-1" type="button" @click="startEdit(row)">수정</button>
              <button v-if="row.is_active" class="btn btn-sm btn-outline-danger" type="button" @click="deactivate(row)">
                사용 중지
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
