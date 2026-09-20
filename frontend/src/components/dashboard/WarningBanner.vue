<script setup>
import { computed } from 'vue'

const props = defineProps({ warnings: { type: Array, default: () => [] } })

// specs/11 §7 — 조건부 경고 배너. 코드별 심각도와 문구를 고정한다.
const SEVERITY = {
  BASELINE_NOT_CONFIRMED: 'warning',
  INSUFFICIENT_BASELINE: 'warning',
  MODEL_METRICS_POOR: 'warning',
  LOW_VALID_RATIO: 'warning',
  FI_SATURATED: 'warning',
  STEP_CHANGE_SUSPECTED: 'info',
  DUCT_BURNER_ALWAYS_ON: 'info',
  SINGLE_CLUSTER: 'info',
  SPARSE_CLUSTERS: 'info',
  SINGLE_SIGNAL: 'info',
  HIGH_MISSING_RATE: 'info',
  WEIGHTS_NORMALIZED: 'info',
  KMEANS_FALLBACK: 'info',
  ALGORITHM_FALLBACK: 'info',
}

const visible = computed(() =>
  props.warnings.map((w) => ({ ...w, severity: SEVERITY[w.code] ?? 'info' })),
)
</script>

<template>
  <div v-if="visible.length" class="mb-3">
    <div
      v-for="warning in visible"
      :key="warning.code"
      class="alert py-2 small mb-2"
      :class="`alert-${warning.severity}`"
      role="alert"
    >
      {{ warning.message }}
    </div>
  </div>
</template>
