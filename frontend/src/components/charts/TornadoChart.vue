<script setup>
/** 민감도 토네이도 차트 (specs/09 §5). ±30% 변동 시 순편익 변화. */
import { computed } from 'vue'

import { formatCurrency } from '@/utils/format'

const props = defineProps({ sensitivity: { type: Array, default: () => [] } })

const LABELS = {
  electricity_price: '전력 단가',
  cleaning_cost: '세정 비용',
  dp_power_loss_coeff: '배압 손실 계수',
  outage_days: '정지 일수',
}

const maxSwing = computed(() => Math.max(1, ...props.sensitivity.map((r) => r.swing)))
</script>

<template>
  <div class="card h-100">
    <div class="card-body">
      <h2 class="h6 mb-3">민감도 (±30%)</h2>

      <template v-if="sensitivity.length">
        <div v-for="row in sensitivity" :key="row.param" class="mb-3">
          <div class="d-flex justify-content-between small">
            <span>{{ LABELS[row.param] ?? row.param }}</span>
            <span class="text-secondary">{{ formatCurrency(row.swing) }}</span>
          </div>
          <div class="progress mt-1" style="height: 0.5rem">
            <div class="progress-bar bg-info" :style="{ width: `${(row.swing / maxSwing) * 100}%` }"></div>
          </div>
          <div class="d-flex justify-content-between small text-secondary">
            <span>−30%: {{ formatCurrency(row.net_benefit_low) }}</span>
            <span>+30%: {{ formatCurrency(row.net_benefit_high) }}</span>
          </div>
        </div>
        <p class="small text-secondary mb-0">변동폭이 큰 항목일수록 결과가 그 가정에 민감합니다.</p>
      </template>

      <p v-else class="text-secondary small mb-0">분석을 실행하면 표시됩니다.</p>
    </div>
  </div>
</template>
