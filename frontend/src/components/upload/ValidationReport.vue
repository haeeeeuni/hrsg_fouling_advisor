<script setup>
import { computed } from 'vue'

import { formatCount, formatDateTime, formatPercent } from '@/utils/format'

const props = defineProps({
  report: { type: Object, required: true },
})

const hasBlockingErrors = computed(() => (props.report.errors ?? []).length > 0)
const validRatio = computed(() =>
  props.report.row_total ? (props.report.row_valid / props.report.row_total) * 100 : 0,
)

/** 구조 오류의 상세를 사람이 읽을 문장으로 편다. */
function describe(issue) {
  if (issue.code === 'MISSING_SOURCE_COLUMN') {
    return issue.missing
      .map((m) => `${m.standard_field} ← "${m.source_column}"`)
      .join(', ')
  }
  if (issue.fields) return issue.fields.join(', ')
  if (issue.columns) return issue.columns.join(', ')
  return ''
}
</script>

<template>
  <div>
    <div class="row g-3 mb-3">
      <div class="col-6 col-lg-3">
        <div class="border rounded p-2">
          <div class="small text-secondary">총 행수</div>
          <div class="fw-semibold">{{ formatCount(report.row_total) }}</div>
        </div>
      </div>
      <div class="col-6 col-lg-3">
        <div class="border rounded p-2">
          <div class="small text-secondary">유효 행수</div>
          <div class="fw-semibold">
            {{ formatCount(report.row_valid) }}
            <span class="text-secondary small">({{ formatPercent(validRatio) }})</span>
          </div>
        </div>
      </div>
      <div class="col-6 col-lg-3">
        <div class="border rounded p-2">
          <div class="small text-secondary">제외 행수</div>
          <div class="fw-semibold">{{ formatCount(report.row_dropped) }}</div>
        </div>
      </div>
      <div class="col-6 col-lg-3">
        <div class="border rounded p-2">
          <div class="small text-secondary">추정 주기</div>
          <div class="fw-semibold">
            {{ report.estimated_interval_min ? `${report.estimated_interval_min} 분` : '–' }}
          </div>
        </div>
      </div>
    </div>

    <p class="small text-secondary">
      데이터 기간: {{ formatDateTime(report.period?.start) }} ~ {{ formatDateTime(report.period?.end) }}
    </p>

    <!-- 구조 오류: 적재를 차단한다 (specs/03 §4.4) -->
    <div v-if="hasBlockingErrors" class="alert alert-danger" role="alert">
      <p class="fw-semibold mb-2">적재할 수 없습니다. 아래 문제를 먼저 해결하세요.</p>
      <ul class="mb-0 ps-3 small">
        <li v-for="issue in report.errors" :key="issue.code">
          <strong>{{ issue.message }}</strong>
          <span v-if="describe(issue)"> — {{ describe(issue) }}</span>
        </li>
      </ul>
    </div>

    <!-- 행 단위 오류: 해당 행만 제외하고 적재는 진행 -->
    <div v-if="report.row_errors?.length" class="alert alert-warning" role="alert">
      <p class="fw-semibold mb-2">일부 행이 제외됩니다.</p>
      <ul class="mb-0 ps-3 small">
        <li v-for="issue in report.row_errors" :key="issue.code">
          {{ issue.message }} — {{ formatCount(issue.count) }}건
          <span v-if="issue.sample_rows?.length" class="text-secondary">
            (예: {{ issue.sample_rows.slice(0, 5).join(', ') }}행)
          </span>
        </li>
      </ul>
    </div>

    <div v-if="report.warnings?.length" class="alert alert-secondary" role="alert">
      <p class="fw-semibold mb-2">경고</p>
      <ul class="mb-0 ps-3 small">
        <li v-for="issue in report.warnings" :key="issue.code">
          {{ issue.message }} — {{ formatCount(issue.count) }}건
          <span v-if="issue.sample_rows?.length" class="text-secondary">
            (예: {{ issue.sample_rows.slice(0, 5).join(', ') }}행)
          </span>
        </li>
      </ul>
    </div>

    <details v-if="Object.keys(report.missing_rate ?? {}).length" class="mt-3">
      <summary class="small text-secondary">컬럼별 결측률</summary>
      <table class="table table-sm mt-2 mb-0">
        <thead>
          <tr><th scope="col">표준 항목</th><th scope="col" class="text-end">결측률</th></tr>
        </thead>
        <tbody>
          <tr v-for="(rate, column) in report.missing_rate" :key="column">
            <td>{{ column }}</td>
            <td class="text-end">{{ formatPercent(rate) }}</td>
          </tr>
        </tbody>
      </table>
    </details>
  </div>
</template>
