<script setup>
/** 세정 공법 표 (specs/06 REF-2). 공법별 비용·정지 일수·회복률은 [임시값] 이다. */
import { onMounted, ref } from 'vue'

import * as api from '@/api/reference'
import ErrorAlert from '@/components/admin/ErrorAlert.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import { useToast } from '@/composables/useToast'
import { formatCurrency } from '@/utils/format'

const toast = useToast()

const rows = ref([])
const loaded = ref(false)
const loadError = ref(null)
const editing = ref(null)
const draft = ref({})
const saveError = ref(null)

onMounted(load)

async function load() {
  try {
    rows.value = (await api.fetchMethods()).data
  } catch (err) {
    loadError.value = err.parsed
  } finally {
    loaded.value = true
  }
}

function startNew() {
  editing.value = 'new'
  saveError.value = null
  draft.value = { name: '', cleaning_cost_won: null, outage_days: null, recovery_ratio: null, is_placeholder: false, note: '' }
}

function startEdit(row) {
  editing.value = row.id
  saveError.value = null
  draft.value = { ...row }
}

async function save() {
  saveError.value = null
  try {
    if (editing.value === 'new') await api.createMethod(draft.value)
    else await api.updateMethod(editing.value, draft.value)
    editing.value = null
    toast.push('저장했습니다.', 'success')
    await load()
  } catch (err) {
    saveError.value = err.parsed
  }
}

async function deactivate(row) {
  if (!window.confirm(`"${row.name}" 을(를) 사용 중지할까요?`)) return
  try {
    await api.deactivateMethod(row.id)
    toast.push('사용 중지했습니다.', 'success')
    await load()
  } catch (err) {
    toast.push(err.parsed?.message ?? '처리하지 못했습니다.', 'danger')
  }
}
</script>

<template>
  <div>
    <div class="alert alert-warning small py-2" role="note">
      현재 값은 <strong>임시값</strong>입니다. 실적 기반 공법별 값을 받으면 교체하세요.
    </div>
    <button class="btn btn-primary btn-sm mb-3" type="button" @click="startNew">
      <i class="bi bi-plus-lg me-1" aria-hidden="true"></i>공법 추가
    </button>

    <form v-if="editing" class="card mb-3" novalidate @submit.prevent="save">
      <div class="card-body row g-2">
        <div class="col-12 col-md-4">
          <label for="m-name" class="form-label small">공법</label>
          <input id="m-name" v-model.trim="draft.name" class="form-control form-control-sm" />
        </div>
        <div class="col-6 col-md-3">
          <label for="m-cost" class="form-label small">세정 비용 (원)</label>
          <input id="m-cost" v-model.number="draft.cleaning_cost_won" type="number" step="any" class="form-control form-control-sm" />
        </div>
        <div class="col-6 col-md-2">
          <label for="m-outage" class="form-label small">정지 일수</label>
          <input id="m-outage" v-model.number="draft.outage_days" type="number" step="any" class="form-control form-control-sm" />
        </div>
        <div class="col-6 col-md-2">
          <label for="m-recovery" class="form-label small">회복률 (0~1)</label>
          <input id="m-recovery" v-model.number="draft.recovery_ratio" type="number" step="0.01" class="form-control form-control-sm" />
        </div>
        <div class="col-6 col-md-1 d-flex align-items-end">
          <div class="form-check">
            <input id="m-placeholder" v-model="draft.is_placeholder" class="form-check-input" type="checkbox" />
            <label for="m-placeholder" class="form-check-label small">임시값</label>
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
    <EmptyState v-else-if="!rows.length" title="등록된 공법이 없습니다." icon="bi-droplet" />
    <div v-else class="table-responsive">
      <table class="table table-sm align-middle">
        <thead>
          <tr>
            <th scope="col">공법</th>
            <th scope="col" class="text-end">세정 비용</th>
            <th scope="col" class="text-end">정지 일수</th>
            <th scope="col" class="text-end">회복률</th>
            <th scope="col">상태</th>
            <th scope="col"><span class="visually-hidden">작업</span></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="row.id" :class="row.is_active ? '' : 'text-secondary'">
            <th scope="row">{{ row.name }} <span class="small text-secondary fw-normal">v{{ row.version }}</span></th>
            <td class="text-end">{{ formatCurrency(row.cleaning_cost_won) }}</td>
            <td class="text-end">{{ row.outage_days }}일</td>
            <td class="text-end">{{ row.recovery_ratio }}</td>
            <td>
              <span v-if="row.is_placeholder" class="badge text-bg-warning me-1">임시값</span>
              <span class="badge" :class="row.is_active ? 'text-bg-secondary' : 'text-bg-light'">{{ row.is_active ? '사용' : '중지' }}</span>
            </td>
            <td class="text-end">
              <button class="btn btn-sm btn-outline-secondary me-1" type="button" @click="startEdit(row)">수정</button>
              <button v-if="row.is_active" class="btn btn-sm btn-outline-danger" type="button" @click="deactivate(row)">사용 중지</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
