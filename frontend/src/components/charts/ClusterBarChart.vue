<script setup>
/** 군집별 FI 분해 (specs/11 §5.3). 희소 군집은 회색 + 배지. */
import { formatCount, formatPercent } from '@/utils/format'

defineProps({ clusters: { type: Array, default: () => [] } })
</script>

<template>
  <div class="card h-100">
    <div class="card-body">
      <h2 class="h6 mb-3">군집별 분포</h2>

      <table v-if="clusters.length" class="table table-sm align-middle mb-0">
        <thead>
          <tr>
            <th scope="col">군집</th>
            <th scope="col" class="text-end">표본</th>
            <th scope="col" class="text-end">비중</th>
            <th scope="col" class="text-end">평균 부하율</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in clusters" :key="row.cluster_key" :class="row.is_sparse ? 'text-secondary' : ''">
            <td class="small">
              {{ row.label }}
              <code class="ms-1">{{ row.cluster_key }}</code>
              <span v-if="row.is_sparse" class="badge text-bg-light ms-1">표본 부족</span>
            </td>
            <td class="small text-end">{{ formatCount(row.sample_count) }}</td>
            <td class="small text-end">{{ formatPercent(row.share_pct) }}</td>
            <td class="small text-end">{{ formatPercent(row.avg_load_ratio_pct) }}</td>
          </tr>
        </tbody>
      </table>

      <p v-else class="text-secondary small mb-0">분석을 실행하면 표시됩니다.</p>
    </div>
  </div>
</template>
