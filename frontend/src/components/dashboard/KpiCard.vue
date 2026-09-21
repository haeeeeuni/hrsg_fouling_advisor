<script setup>
defineProps({
  label: { type: String, required: true },
  value: { type: String, required: true },
  hint: { type: String, default: '' },
  variant: { type: String, default: '' },
  // Spark 의 어두운 강조 카드 (specs/20). 한 화면에 하나만 쓴다.
  dark: { type: Boolean, default: false },
})
</script>

<template>
  <div class="card h-100" :class="{ 'spark-card-dark': dark }">
    <div class="card-body">
      <p class="spark-stat-label">{{ label }}</p>
      <p class="spark-stat-value" :class="variant ? `text-${variant}` : ''">
        <slot name="value">{{ value }}</slot>
      </p>
      <p v-if="hint || $slots.hint" class="small text-secondary mb-0">
        <slot name="hint">{{ hint }}</slot>
      </p>
    </div>
  </div>
</template>
