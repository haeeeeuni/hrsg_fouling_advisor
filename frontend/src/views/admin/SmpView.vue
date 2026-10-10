<script setup>
/**
 * SMP 등록·이력 (specs/06 REF-3·REF-4). 최신 기준일 값이 계산기 기본값이다.
 * 확인되지 않은 값은 '추정' 으로 표시해 공식 가격처럼 보이지 않게 한다.
 */
import { onMounted, ref } from 'vue'

import * as api from '@/api/reference'
import ErrorAlert from '@/components/admin/ErrorAlert.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import { useToast } from '@/composables/useToast'
import { formatDate, formatDateTime } from '@/utils/format'

const toast = useToast()

const rows = ref([])
const loaded = ref(false)
const loadError = ref(null)
const form = ref(blank())
const saveError = ref(null)

function blank() {
  return { value_won_per_kwh: null, as_of_date: '', period_label: '', source: 'KPX 공개 자료', is_estimate: false }
}

onMounted(load)

async function load() {
  try {
    const { data } = await api.fetchSmpPrices()
    rows.value = data.results ?? data
  } catch (err) {
    loadError.value = err.parsed
  } finally {
    loaded.value = true
  }
}

async function save() {
  saveError.value = null
  try {
    await api.createSmpPrice(form.value)
    form.value = blank()
    toast.push('SMP 를 등록했습니다. 다음 계산부터 기본값이 됩니다.', 'success')
    await load()
  } catch (err) {
    saveError.value = err.parsed
  }
}

async function remove(row) {
  if (!window.confirm(`${formatDate(row.as_of_date)} SMP ${row.value_won_per_kwh} 원/kWh 를 삭제할까요?`)) return
  try {
    await api.deleteSmpPrice(row.id)
    await load()
  } catch (err) {
    toast.push(err.parsed?.message ?? '삭제하지 못했습니다.', 'danger')
  }
}
</script>

<template>
  <div>
    <form class="card mb-3" novalidate @submit.prevent="save">
      <div class="card-body row g-2 align-items-end">
        <div class="col-6 col-md-2">
          <label for="smp-value" class="form-label small">SMP (원/kWh)</label>
          <input id="smp-value" v-model.number="form.value_won_per_kwh" type="number" step="any" class="form-control form-control-sm" />
        </div>
        <div class="col-6 col-md-2">
          <label for="smp-date" class="form-label small">기준일</label>
          <input id="smp-date" v-model="form.as_of_date" type="date" class="form-control form-control-sm" />
        </div>
        <div class="col-6 col-md-2">
          <label for="smp-period" class="form-label small">기간 표기 (선택)</label>
          <input id="smp-period" v-model.trim="form.period_label" class="form-control form-control-sm" placeholder="예: 2026년 9월 평균" />
        </div>
        <div class="col-6 col-md-3">
          <label for="smp-source" class="form-label small">출처</label>
          <input id="smp-source" v-model.trim="form.source" class="form-control form-control-sm" />
        </div>
        <div class="col-6 col-md-1">
          <div class="form-check mb-1">
            <input id="smp-estimate" v-model="form.is_estimate" class="form-check-input" type="checkbox" />
            <label for="smp-estimate" class="form-check-label small">추정값</label>
          </div>
        </div>
        <div class="col-6 col-md-2">
          <button class="btn btn-sm btn-primary w-100" type="submit">등록</button>
        </div>
        <div class="col-12"><ErrorAlert :error="saveError" /></div>
      </div>
    </form>

    <ErrorAlert :error="loadError" />
    <div v-if="!loaded" class="text-center py-4">
      <div class="spinner-border text-primary" role="status"><span class="visually-hidden">불러오는 중</span></div>
    </div>
    <EmptyState
      v-else-if="!rows.length"
      title="등록된 SMP 가 없습니다."
      description="등록 전에는 사용자가 계산할 때마다 SMP 를 직접 입력해야 합니다."
      icon="bi-currency-exchange"
    />
    <div v-else class="table-responsive">
      <table class="table table-sm align-middle">
        <thead>
          <tr>
            <th scope="col">기준일</th>
            <th scope="col" class="text-end">SMP (원/kWh)</th>
            <th scope="col">출처</th>
            <th scope="col">등록</th>
            <th scope="col"><span class="visually-hidden">작업</span></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, index) in rows" :key="row.id">
            <td>
              {{ formatDate(row.as_of_date) }} <span v-if="row.period_label" class="small text-secondary">({{ row.period_label }})</span>
              <span v-if="index === 0" class="badge text-bg-primary ms-1">계산기 기본값</span>
            </td>
            <td class="text-end">{{ row.value_won_per_kwh }}</td>
            <td>
              {{ row.source }}
              <span v-if="row.is_estimate" class="badge text-bg-warning ms-1">추정</span>
            </td>
            <td class="small text-secondary">{{ row.created_by_name || '시드' }} · {{ formatDateTime(row.created_at) }}</td>
            <td class="text-end">
              <button class="btn btn-sm btn-outline-danger" type="button" @click="remove(row)">삭제</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
