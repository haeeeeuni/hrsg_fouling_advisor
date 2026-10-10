<script setup>
/** 결과의 핵심 숫자 — 화면에서 가장 큰 글자 (specs/12 UI-3). */
defineProps({
  label: { type: String, required: true },
  value: { type: String, required: true },
  /** 정확한 값(작은 글자) */
  detail: { type: String, default: '' },
  testid: { type: String, default: '' },
})
</script>

<template>
  <div class="ui-big-number">
    <p class="ui-stat-label mb-1">{{ label }}</p>
    <p class="ui-stat-value mb-0" :data-testid="testid || undefined">{{ value }}</p>
    <p v-if="detail" class="small text-secondary mb-0">{{ detail }}</p>
  </div>
</template>
