<script setup>
/** 공법별 비용 비교 (specs/05 CALC-3). 최고값은 '권장' 이 아니라 '순편익 최대' 로 표기한다. */
import BigNumber from '@/components/calculator/BigNumber.vue'
import MethodCompareChart from '@/components/calculator/MethodCompareChart.vue'
import ResultNotices from '@/components/calculator/ResultNotices.vue'
import { formatPayback, formatWonShort } from '@/utils/format'

defineProps({
  data: { type: Object, required: true },
})
</script>

<template>
  <div>
    <!-- 임시값·SMP 출처 안내는 결과보다 먼저 보이게 위에 둔다 (specs/12 §6). -->
    <ResultNotices class="mb-3" :meta="data.meta" />
    <div class="row g-3 mb-3">
      <div class="col-6">
        <BigNumber label="예상 손실 (일)" :value="formatWonShort(data.results.daily_loss_won)" />
      </div>
      <div class="col-6">
        <BigNumber
          label="순편익 최대 공법"
          :value="data.results.methods.find((m) => m.is_best)?.name ?? '–'"
          testid="best-method"
        />
      </div>
    </div>

    <div class="card mb-3">
      <div class="card-body">
        <h3 class="h6">공법별 순편익</h3>
        <MethodCompareChart :rows="data.results.methods" />
      </div>
    </div>

    <div class="table-responsive mb-3">
      <table class="table table-sm align-middle">
        <caption>순편익 = 평가 기간 회수액 − (세정 비용 + 정지 손실)</caption>
        <thead>
          <tr>
            <th scope="col">공법</th>
            <th scope="col" class="text-end">세정 비용</th>
            <th scope="col" class="text-end">정지 손실</th>
            <th scope="col" class="text-end">회수 (일)</th>
            <th scope="col" class="text-end">순편익</th>
            <th scope="col" class="text-end">회수 기간</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in data.results.methods" :key="row.method_id">
            <th scope="row">
              {{ row.name }}
              <span v-if="row.is_best" class="badge text-bg-success ms-1">
                <i class="bi bi-check-circle-fill me-1" aria-hidden="true"></i>순편익 최대
              </span>
            </th>
            <td class="text-end">{{ formatWonShort(row.cleaning_cost_won) }}</td>
            <td class="text-end">{{ formatWonShort(row.outage_loss_won) }}</td>
            <td class="text-end">{{ formatWonShort(row.recovered_daily_won) }}</td>
            <td class="text-end" :class="row.net_benefit_won < 0 ? 'text-danger' : ''">
              {{ formatWonShort(row.net_benefit_won) }}
            </td>
            <td class="text-end">{{ formatPayback(row.payback_days) }}</td>
          </tr>
        </tbody>
      </table>
    </div>

  </div>
</template>
