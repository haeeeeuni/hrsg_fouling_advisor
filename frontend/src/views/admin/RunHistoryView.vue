<script setup>
import { onMounted, ref } from 'vue'

import * as analysisApi from '@/api/analysis'
import client from '@/api/client'
import * as reportsApi from '@/api/reports'
import EmptyState from '@/components/common/EmptyState.vue'
import GradeBadge from '@/components/dashboard/GradeBadge.vue'
import { useToast } from '@/composables/useToast'
import { useUnitsStore } from '@/stores/units'
import { formatCurrency, formatDateTime, formatDday, formatFi } from '@/utils/format'

const units = useUnitsStore()
const toast = useToast()

const runs = ref([])
const detail = ref(null)
const filters = ref({ unit_id: '', status: '', is_auto: '' })

onMounted(async () => {
  await units.fetchUnits()
  await load()
})

async function load() {
  const params = Object.fromEntries(Object.entries(filters.value).filter(([, v]) => v !== ''))
  const { data } = await analysisApi.fetchRuns({ ...params, page_size: 100 })
  runs.value = data.results ?? data
}

async function show(run) {
  const { data } = await analysisApi.fetchRun(run.id)
  detail.value = data
}

async function regenerate(run, format) {
  try {
    const { data } = await reportsApi.exportAnalysis(run.id, format)
    await reportsApi.downloadReport(data.id, data.file_name)
    toast.push('리포트를 다시 생성했습니다.', 'success')
  } catch (err) {
    toast.push(err.parsed?.message ?? '생성할 수 없습니다.', 'danger')
  }
}

/** 분석 실행 이력 엑셀 내보내기 (specs/13 §6) */
async function exportHistory() {
  const params = Object.fromEntries(Object.entries(filters.value).filter(([, v]) => v !== ''))
  const response = await client.get('/analysis-runs/export-history/', {
    params,
    responseType: 'blob',
  })
  const url = window.URL.createObjectURL(response.data)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = '분석실행이력.xlsx'
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  window.URL.revokeObjectURL(url)
}
</script>

<template>
  <div>
    <div class="row g-2 align-items-end mb-3">
      <div class="col-6 col-lg-3">
        <label for="rhUnit" class="form-label small">호기</label>
        <select id="rhUnit" v-model="filters.unit_id" class="form-select form-select-sm" @change="load">
          <option value="">전체</option>
          <option v-for="unit in units.list" :key="unit.id" :value="unit.id">{{ unit.code }}</option>
        </select>
      </div>
      <div class="col-6 col-lg-2">
        <label for="rhStatus" class="form-label small">상태</label>
        <select id="rhStatus" v-model="filters.status" class="form-select form-select-sm" @change="load">
          <option value="">전체</option>
          <option value="SUCCESS">성공</option>
          <option value="FAILED">실패</option>
          <option value="RUNNING">실행 중</option>
        </select>
      </div>
      <div class="col-6 col-lg-2">
        <label for="rhAuto" class="form-label small">실행 방식</label>
        <select id="rhAuto" v-model="filters.is_auto" class="form-select form-select-sm" @change="load">
          <option value="">전체</option>
          <option value="false">수동</option>
          <option value="true">자동</option>
        </select>
      </div>
      <div class="col-12 col-lg-5 text-lg-end">
        <button class="btn btn-outline-secondary btn-sm" @click="exportHistory">엑셀 내보내기</button>
      </div>
    </div>

    <EmptyState v-if="!runs.length" title="분석 실행 이력이 없습니다." icon="bi-clock-history" />

    <table v-else class="table table-sm align-middle">
      <thead>
        <tr>
          <th scope="col">실행 일시</th><th scope="col">호기</th><th scope="col">실행자</th>
          <th scope="col">데이터 기간</th><th scope="col" class="text-end">FI</th>
          <th scope="col">등급</th><th scope="col">D-day</th>
          <th scope="col" class="text-end">순편익</th><th scope="col" class="text-end">소요</th>
          <th scope="col">상태</th><th scope="col"></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="run in runs" :key="run.id">
          <td class="small">{{ formatDateTime(run.executed_at) }}</td>
          <td class="small">{{ run.unit_code }}</td>
          <td class="small">
            {{ run.executed_by_name ?? '–' }}
            <span v-if="run.is_auto" class="badge text-bg-light ms-1">자동</span>
          </td>
          <td class="small">
            {{ formatDateTime(run.period_start) }} ~ {{ formatDateTime(run.period_end) }}
          </td>
          <td class="small text-end">{{ formatFi(run.result_fi) }}</td>
          <td><GradeBadge :grade="run.result_grade" /></td>
          <td class="small">{{ formatDday(run.result_dday) }}</td>
          <td class="small text-end">{{ formatCurrency(run.result_net_benefit) }}</td>
          <td class="small text-end">{{ run.duration_sec?.toFixed(1) ?? '–' }}s</td>
          <td>
            <span class="badge"
                  :class="run.status === 'SUCCESS' ? 'text-bg-success' : run.status === 'FAILED' ? 'text-bg-danger' : 'text-bg-secondary'">
              {{ run.status }}
            </span>
          </td>
          <td class="text-end">
            <button class="btn btn-sm btn-outline-secondary me-1" @click="show(run)">상세</button>
            <button v-if="run.status === 'SUCCESS'" class="btn btn-sm btn-outline-secondary"
                    @click="regenerate(run, 'pdf')">리포트</button>
          </td>
        </tr>
      </tbody>
    </table>

    <div v-if="detail" class="card mt-3">
      <div class="card-body">
        <div class="d-flex justify-content-between align-items-center mb-3">
          <h3 class="h6 mb-0">실행 #{{ detail.id }} 상세</h3>
          <button class="btn btn-sm btn-outline-secondary" @click="detail = null">닫기</button>
        </div>

        <div v-if="detail.status === 'FAILED'" class="alert alert-danger py-2 small">
          <strong>실패 단계: {{ detail.failed_stage || '–' }}</strong>
          <div>{{ detail.error_message }}</div>
        </div>

        <div class="row g-3">
          <div class="col-12 col-lg-6">
            <h4 class="small fw-semibold">모델 버전</h4>
            <ul class="small mb-3">
              <li>차압 — {{ detail.model_dp?.algorithm }} v{{ detail.model_dp?.version }}
                (R² {{ detail.model_dp?.metrics?.r2?.toFixed(3) ?? '–' }})</li>
              <li>스택온도 — {{ detail.model_st?.algorithm }} v{{ detail.model_st?.version }}
                (R² {{ detail.model_st?.metrics?.r2?.toFixed(3) ?? '–' }})</li>
            </ul>

            <h4 class="small fw-semibold">데이터 통계</h4>
            <ul class="small mb-0">
              <li>총 / 유효 포인트 — {{ detail.data_stats?.row_total }} / {{ detail.data_stats?.row_valid }}</li>
              <li>청정 기준 — {{ detail.data_stats?.baseline_source }}
                ({{ detail.data_stats?.baseline_points }}점)</li>
            </ul>
          </div>

          <div class="col-12 col-lg-6">
            <h4 class="small fw-semibold">적용 설정값 스냅샷</h4>
            <div class="table-responsive" style="max-height: 260px">
              <table class="table table-sm mb-0">
                <tbody>
                  <tr v-for="(value, key) in detail.settings_snapshot" :key="key">
                    <td class="small text-secondary">{{ key }}</td>
                    <td class="small text-end">{{ JSON.stringify(value) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <div v-if="detail.warnings?.length" class="mt-3">
          <h4 class="small fw-semibold">경고</h4>
          <ul class="small mb-0">
            <li v-for="w in detail.warnings" :key="w.code">{{ w.message }}</li>
          </ul>
        </div>
      </div>
    </div>
  </div>
</template>
