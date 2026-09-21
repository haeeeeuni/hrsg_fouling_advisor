<script setup>
import { onMounted, ref } from 'vue'

import * as analysisApi from '@/api/analysis'
import * as reportsApi from '@/api/reports'
import EmptyState from '@/components/common/EmptyState.vue'
import { useToast } from '@/composables/useToast'
import { formatCount, formatDateTime } from '@/utils/format'

const toast = useToast()
const reports = ref([])
const runs = ref([])
const busy = ref(false)

onMounted(async () => {
  await Promise.all([loadReports(), loadRuns()])
})

async function loadReports() {
  const { data } = await reportsApi.fetchReports({ page_size: 50 })
  reports.value = data.results ?? data
}

async function loadRuns() {
  const { data } = await analysisApi.fetchRuns({ status: 'SUCCESS', page_size: 20 })
  runs.value = data.results ?? data
}

async function generate(runId, format) {
  busy.value = true
  try {
    const { data } = await reportsApi.exportAnalysis(runId, format)
    await reportsApi.downloadReport(data.id, data.file_name)
    toast.push('리포트를 생성해 내려받았습니다.', 'success')
    await loadReports()
  } catch (err) {
    toast.push(err.parsed?.message ?? '리포트 생성에 실패했습니다.', 'danger')
  } finally {
    busy.value = false
  }
}

async function download(report) {
  try {
    await reportsApi.downloadReport(report.id, report.file_name)
  } catch (err) {
    toast.push(err.parsed?.message ?? '내려받을 수 없습니다.', 'danger')
  }
}
</script>

<template>
  <div>
    <div class="card mb-3">
      <div class="card-body">
        <h2 class="h6 mb-3">분석 결과에서 생성</h2>
        <EmptyState
          v-if="!runs.length"
          title="성공한 분석이 없습니다."
          description="분석을 실행하면 여기서 PDF·엑셀 리포트를 만들 수 있습니다."
          icon="bi-file-earmark-text"
        />
        <table v-else class="table table-sm align-middle mb-0">
          <thead>
            <tr>
              <th scope="col">분석 일시</th>
              <th scope="col">호기</th>
              <th scope="col">데이터 기간</th>
              <th scope="col" class="text-end">FI</th>
              <th scope="col"></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="run in runs" :key="run.id">
              <td class="small">{{ formatDateTime(run.executed_at) }}</td>
              <td class="small">{{ run.unit_code }}</td>
              <td class="small">
                {{ formatDateTime(run.period_start) }} ~ {{ formatDateTime(run.period_end) }}
              </td>
              <td class="small text-end">{{ run.result_fi?.toFixed(1) ?? '–' }}</td>
              <td class="text-end">
                <button class="btn btn-sm btn-outline-secondary me-1" :disabled="busy"
                        @click="generate(run.id, 'pdf')">PDF</button>
                <button class="btn btn-sm btn-outline-secondary" :disabled="busy"
                        @click="generate(run.id, 'xlsx')">엑셀</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div class="card">
      <div class="card-body">
        <h2 class="h6 mb-3">생성 이력</h2>
        <EmptyState v-if="!reports.length" title="생성된 리포트가 없습니다." icon="bi-clock-history" />
        <table v-else class="table table-sm align-middle mb-0">
          <thead>
            <tr>
              <th scope="col">생성 일시</th>
              <th scope="col">파일명</th>
              <th scope="col">형식</th>
              <th scope="col" class="text-end">크기</th>
              <th scope="col">생성자</th>
              <th scope="col"></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="report in reports" :key="report.id">
              <td class="small">{{ formatDateTime(report.created_at) }}</td>
              <td class="small">{{ report.file_name }}</td>
              <td><span class="badge text-bg-light">{{ report.format }}</span></td>
              <td class="small text-end">{{ formatCount(Math.round(report.file_size_bytes / 1024)) }} KB</td>
              <td class="small">{{ report.created_by_name ?? '–' }}</td>
              <td class="text-end">
                <button class="btn btn-sm btn-outline-primary" @click="download(report)">다운로드</button>
              </td>
            </tr>
          </tbody>
        </table>
        <p class="small text-secondary mt-2 mb-0">생성된 파일은 보존 기간이 지나면 정리됩니다.</p>
      </div>
    </div>
  </div>
</template>
