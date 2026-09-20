<script setup>
import { computed, onMounted, ref } from 'vue'

import * as api from '@/api/maintenance'
import { useToast } from '@/composables/useToast'
import { useUnitsStore } from '@/stores/units'

const toast = useToast()
const units = useUnitsStore()

const keywords = ref([])
const newKeyword = ref({ keyword: '', category: 'CLEANING', weight: 1.0 })
const error = ref(null)

const CATEGORIES = [
  ['CLEANING', '세정'],
  ['FOULING', '오염 징후'],
  ['INSPECTION', '점검'],
  ['EXCLUDE', '제외어'],
]

const grouped = computed(() =>
  CATEGORIES.map(([value, label]) => ({
    value,
    label,
    rows: keywords.value.filter((k) => k.category === value),
  })),
)

onMounted(async () => {
  await Promise.all([units.fetchUnits(), load()])
})

async function load() {
  const { data } = await api.fetchKeywords({ page_size: 200 })
  keywords.value = data.results ?? data
}

async function add() {
  error.value = null
  try {
    await api.createKeyword(newKeyword.value)
    newKeyword.value = { keyword: '', category: 'CLEANING', weight: 1.0 }
    await load()
    toast.push('키워드를 추가했습니다. 다음 추출부터 반영됩니다.', 'success')
  } catch (err) {
    error.value = err.parsed
  }
}

async function toggle(row) {
  await api.updateKeyword(row.id, { is_active: !row.is_active })
  await load()
}

async function save(row) {
  await api.updateKeyword(row.id, { weight: row.weight })
  toast.push('가중치를 저장했습니다.', 'success')
}

async function remove(row) {
  if (!window.confirm(`키워드 "${row.keyword}" 을(를) 삭제할까요?`)) return
  await api.deleteKeyword(row.id)
  await load()
}

async function restore() {
  const { data } = await api.restoreDefaultKeywords()
  await load()
  toast.push(`기본 키워드 ${data.restored}건을 복원했습니다.`, 'success')
}

async function reExtract() {
  if (!window.confirm('검토 대기 중인 정비 이력을 새 키워드 사전으로 다시 분류할까요?')) return
  const { data } = await api.reExtract(units.selectedUnitId)
  toast.push(`${data.updated}건 재분류, 후보 ${data.candidates}건`, 'success')
}
</script>

<template>
  <div>
    <div class="d-flex justify-content-between align-items-center mb-3">
      <h2 class="h6 mb-0">오염 키워드 사전</h2>
      <div>
        <button class="btn btn-sm btn-outline-secondary me-1" @click="restore">기본값 복원</button>
        <button class="btn btn-sm btn-outline-primary" @click="reExtract">재추출</button>
      </div>
    </div>

    <div class="card mb-3">
      <div class="card-body">
        <div class="row g-2 align-items-end">
          <div class="col-12 col-md-5">
            <label for="kwText" class="form-label small">키워드</label>
            <input id="kwText" v-model.trim="newKeyword.keyword" class="form-control form-control-sm" />
          </div>
          <div class="col-6 col-md-3">
            <label for="kwCategory" class="form-label small">분류</label>
            <select id="kwCategory" v-model="newKeyword.category" class="form-select form-select-sm">
              <option v-for="[value, label] in CATEGORIES" :key="value" :value="value">{{ label }}</option>
            </select>
          </div>
          <div class="col-4 col-md-2">
            <label for="kwWeight" class="form-label small">가중치</label>
            <input id="kwWeight" v-model.number="newKeyword.weight" type="number" step="0.1"
                   class="form-control form-control-sm" />
          </div>
          <div class="col-2">
            <button class="btn btn-sm btn-primary w-100" :disabled="!newKeyword.keyword" @click="add">
              추가
            </button>
          </div>
        </div>
        <div v-if="error" class="alert alert-danger py-2 small mt-2 mb-0">{{ error.message }}</div>
      </div>
    </div>

    <div v-for="group in grouped" :key="group.value" class="mb-4">
      <h3 class="h6">
        {{ group.label }}
        <span class="badge text-bg-light">{{ group.rows.length }}</span>
      </h3>
      <table class="table table-sm align-middle">
        <thead>
          <tr>
            <th scope="col" style="width: 45%">키워드</th>
            <th scope="col" style="width: 20%">가중치</th>
            <th scope="col" style="width: 15%">사용</th>
            <th scope="col"></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in group.rows" :key="row.id" :class="row.is_active ? '' : 'text-secondary'">
            <td class="small">{{ row.keyword }}</td>
            <td>
              <input v-model.number="row.weight" type="number" step="0.1"
                     class="form-control form-control-sm" :aria-label="`${row.keyword} 가중치`"
                     @change="save(row)" />
            </td>
            <td>
              <div class="form-check form-switch">
                <input class="form-check-input" type="checkbox" :checked="row.is_active"
                       :aria-label="`${row.keyword} 사용 여부`" @change="toggle(row)" />
              </div>
            </td>
            <td class="text-end">
              <button class="btn btn-sm btn-outline-danger" @click="remove(row)">삭제</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
