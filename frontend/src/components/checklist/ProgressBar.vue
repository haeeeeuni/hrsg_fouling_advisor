<script setup>
/** 필수 항목 기준 진행률 (specs/07 CHK-3). 숫자를 막대 옆에 함께 적어 색에만 기대지 않는다. */
defineProps({
  progress: { type: Object, required: true }, // { received, total, percent, complete }
  label: { type: String, default: '진행률' },
})
</script>

<template>
  <div class="d-flex align-items-center gap-2">
    <div
      class="progress flex-grow-1"
      role="progressbar"
      :aria-label="label"
      :aria-valuenow="progress.percent"
      aria-valuemin="0"
      aria-valuemax="100"
      style="height: 0.6rem"
    >
      <div class="progress-bar" :class="progress.complete ? 'bg-success' : ''" :style="{ width: `${progress.percent}%` }"></div>
    </div>
    <span class="small text-nowrap" data-testid="progress-text">
      필수 {{ progress.received }}/{{ progress.total }} · {{ progress.percent }}%
    </span>
  </div>
</template>
