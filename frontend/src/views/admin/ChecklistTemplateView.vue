<script setup>
/**
 * 체크리스트 항목 템플릿 (specs/07 CHK-6). 지금 항목은 [임시값] — 사내 데이터 요청 양식을 받으면
 * xlsx 로 가져와 교체한다. 바꿔도 이미 만든 요청 건에는 영향이 없다(사용자가 '새 항목 추가'로 고른다).
 */
import { computed, onMounted, ref } from 'vue'

import * as api from '@/api/checklist'
import ErrorAlert from '@/components/admin/ErrorAlert.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import { useToast } from '@/composables/useToast'
import { saveBlob } from '@/utils/download'

const toast = useToast()

const CATEGORIES = [
  ['GT', '가스터빈'],
  ['FUEL', '연료'],
  ['EXHAUST', '배기가스'],
  ['FEEDWATER', '급수'],
  ['STEAM', '증기'],
  ['EMISSION', '배출가스'],
  ['MODULE', '열교환 모듈 사양'],
  ['DESIGN', '설계값'],
  ['PINCH', '핀치·어프로치'],
  ['SCHEDULE', '일정·현장 조건'],
  ['DATA_SCOPE', '데이터 범위'],
]

const rows = ref([])
const loaded = ref(false)
const loadError = ref(null)
const editing = ref(null)
const draft = ref({})
const saveError = ref(null)
const importResult = ref(null)
const importError = ref(null)
const fileInput = ref(null)

const placeholderCount = computed(() => rows.value.filter((r) => r.is_placeholder && r.is_active).length)
const groups = computed(() =>
  CATEGORIES.map(([code, label]) => ({ code, label, items: rows.value.filter((r) => r.category === code) })).filter(
    (g) => g.items.length,
  ),
)

onMounted(load)

async function load() {
  try {
    rows.value = (await api.fetchTemplateItems()).data
  } catch (err) {
    loadError.value = err.parsed
  } finally {
    loaded.value = true
  }
}

function startNew() {
  editing.value = 'new'
  saveError.value = null
  draft.value = {
    category: 'GT',
    name_ko: '',
    name_en: '',
    unit: '',
    is_required: true,
    why_needed_ko: '',
    why_needed_en: '',
    is_calculator_input: false,
    source: 'ADDED',
    is_placeholder: false,
  }
}

function startEdit(row) {
  editing.value = row.id
  saveError.value = null
  draft.value = { ...row }
}

async function save() {
  saveError.value = null
  try {
    if (editing.value === 'new') await api.createTemplateItem(draft.value)
    else await api.updateTemplateItem(editing.value, draft.value)
    editing.value = null
    toast.push('저장했습니다. 새로 만드는 요청 건부터 적용됩니다.', 'success')
    await load()
  } catch (err) {
    saveError.value = err.parsed
  }
}

async function toggleActive(row) {
  try {
    if (row.is_active) await api.deactivateTemplateItem(row.id)
    else await api.updateTemplateItem(row.id, { is_active: true, version: row.version })
    await load()
  } catch (err) {
    toast.push(err.parsed?.message ?? '처리하지 못했습니다.', 'danger')
  }
}

/** 같은 분류 안에서 한 칸 위·아래로 */
async function move(group, index, offset) {
  const target = index + offset
  if (target < 0 || target >= group.items.length) return
  const ids = rows.value.map((r) => r.id)
  const a = ids.indexOf(group.items[index].id)
  const b = ids.indexOf(group.items[target].id)
  ;[ids[a], ids[b]] = [ids[b], ids[a]]
  try {
    rows.value = (await api.reorderTemplateItems(ids)).data
  } catch (err) {
    toast.push(err.parsed?.message ?? '순서를 바꾸지 못했습니다.', 'danger')
  }
}

async function exportXlsx() {
  saveBlob((await api.exportTemplateItems()).data, 'checklist_items.xlsx')
}

async function onImport(event) {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file) return
  importResult.value = null
  importError.value = null
  try {
    importResult.value = (await api.importTemplateItems(file)).data
    await load()
  } catch (err) {
    importError.value = err.parsed
  }
}
</script>

<template>
  <div>
    <div v-if="placeholderCount" class="alert alert-warning small py-2" role="note">
      <i class="bi bi-exclamation-triangle-fill me-1" aria-hidden="true"></i>
      임시값 항목이 {{ placeholderCount }}개 있습니다. 사내 데이터 요청 양식을 받으면 xlsx 로 가져와 교체하세요
      (가져온 항목은 임시값 표시가 풀립니다). 머리글은 "내보내기" 파일과 같습니다.
    </div>

    <div class="d-flex flex-wrap gap-2 mb-3">
      <button class="btn btn-primary btn-sm" type="button" @click="startNew">
        <i class="bi bi-plus-lg me-1" aria-hidden="true"></i>항목 추가
      </button>
      <button class="btn btn-outline-secondary btn-sm" type="button" @click="exportXlsx">
        <i class="bi bi-download me-1" aria-hidden="true"></i>xlsx 내보내기
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
      <div class="card-body row g-2">
        <div class="col-12 col-md-3">
          <label for="ci-category" class="form-label small">분류</label>
          <select id="ci-category" v-model="draft.category" class="form-select form-select-sm">
            <option v-for="[code, label] in CATEGORIES" :key="code" :value="code">{{ label }}</option>
          </select>
        </div>
        <div class="col-12 col-md-4">
          <label for="ci-name" class="form-label small">항목명</label>
          <input id="ci-name" v-model.trim="draft.name_ko" class="form-control form-control-sm" />
        </div>
        <div class="col-12 col-md-3">
          <label for="ci-name-en" class="form-label small">항목명(영문)</label>
          <input id="ci-name-en" v-model.trim="draft.name_en" class="form-control form-control-sm" />
        </div>
        <div class="col-6 col-md-2">
          <label for="ci-unit" class="form-label small">단위</label>
          <input id="ci-unit" v-model.trim="draft.unit" class="form-control form-control-sm" />
        </div>
        <div class="col-12 col-md-6">
          <label for="ci-why" class="form-label small">필요한 이유</label>
          <input id="ci-why" v-model.trim="draft.why_needed_ko" class="form-control form-control-sm" />
        </div>
        <div class="col-12 col-md-6">
          <label for="ci-why-en" class="form-label small">필요한 이유(영문)</label>
          <input id="ci-why-en" v-model.trim="draft.why_needed_en" class="form-control form-control-sm" />
        </div>
        <div class="col-12 d-flex flex-wrap gap-3">
          <div class="form-check">
            <input id="ci-required" v-model="draft.is_required" class="form-check-input" type="checkbox" />
            <label for="ci-required" class="form-check-label small">필수</label>
          </div>
          <div class="form-check">
            <input id="ci-calc" v-model="draft.is_calculator_input" class="form-check-input" type="checkbox" />
            <label for="ci-calc" class="form-check-label small">계산기 입력</label>
          </div>
          <div class="form-check">
            <input id="ci-placeholder" v-model="draft.is_placeholder" class="form-check-input" type="checkbox" />
            <label for="ci-placeholder" class="form-check-label small">임시값</label>
          </div>
        </div>
        <div class="col-12">
          <ErrorAlert :error="saveError" />
          <button class="btn btn-sm btn-primary me-2" type="submit">저장</button>
          <button class="btn btn-sm btn-outline-secondary" type="button" @click="editing = null">취소</button>
        </div>
      </div>
    </form>

    <ErrorAlert :error="loadError" />
    <div v-if="!loaded" class="text-center py-4">
      <div class="spinner-border text-primary" role="status"><span class="visually-hidden">불러오는 중</span></div>
    </div>
    <EmptyState v-else-if="!rows.length" title="체크리스트 항목이 없습니다." icon="bi-ui-checks" />

    <section v-for="group in groups" v-else :key="group.code" class="card mb-3" :aria-label="group.label">
      <div class="card-body">
        <h2 class="h6">{{ group.label }} <span class="text-secondary fw-normal">({{ group.items.length }})</span></h2>
        <div class="table-responsive">
          <table class="table table-sm align-middle">
            <thead>
              <tr>
                <th scope="col">순서</th>
                <th scope="col">항목</th>
                <th scope="col">표시</th>
                <th scope="col"><span class="visually-hidden">작업</span></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, index) in group.items" :key="row.id" :class="row.is_active ? '' : 'text-secondary'">
                <td class="text-nowrap">
                  <button class="btn btn-sm btn-link px-1" type="button" :disabled="index === 0" :aria-label="`${row.name_ko} 위로`" @click="move(group, index, -1)">
                    <i class="bi bi-arrow-up" aria-hidden="true"></i>
                  </button>
                  <button
                    class="btn btn-sm btn-link px-1"
                    type="button"
                    :disabled="index === group.items.length - 1"
                    :aria-label="`${row.name_ko} 아래로`"
                    @click="move(group, index, 1)"
                  >
                    <i class="bi bi-arrow-down" aria-hidden="true"></i>
                  </button>
                </td>
                <th scope="row" class="fw-normal">
                  <span class="fw-semibold">{{ row.name_ko }}</span>
                  <span v-if="row.unit" class="text-secondary"> ({{ row.unit }})</span>
                  <div class="small text-secondary">{{ row.name_en }}</div>
                </th>
                <td>
                  <span v-if="row.is_required" class="badge text-bg-light me-1">필수</span>
                  <span v-if="row.is_calculator_input" class="badge text-bg-info me-1">계산기 입력</span>
                  <span class="badge text-bg-light me-1">{{ row.source === 'FORM' ? '양식' : '추가' }}</span>
                  <span v-if="row.is_placeholder" class="badge text-bg-warning me-1">임시값</span>
                  <span v-if="!row.is_active" class="badge text-bg-secondary">중지</span>
                </td>
                <td class="text-end text-nowrap">
                  <button class="btn btn-sm btn-outline-secondary me-1" type="button" @click="startEdit(row)">수정</button>
                  <button class="btn btn-sm" :class="row.is_active ? 'btn-outline-danger' : 'btn-outline-secondary'" type="button" @click="toggleActive(row)">
                    {{ row.is_active ? '사용 중지' : '다시 사용' }}
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>
  </div>
</template>
