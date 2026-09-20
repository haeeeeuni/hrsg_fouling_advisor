<script setup>
/** 빈 상태는 원인과 다음 행동을 함께 안내한다 (specs/16 §6). */
defineProps({
  title: { type: String, required: true },
  description: { type: String, default: '' },
  icon: { type: String, default: 'bi-inbox' },
})
</script>

<template>
  <div class="text-center text-secondary py-5">
    <i class="bi fs-1" :class="icon" aria-hidden="true"></i>
    <p class="fw-semibold mt-3 mb-1 text-body">{{ title }}</p>
    <p v-if="description" class="mb-3 small">{{ description }}</p>
    <slot name="action" />
  </div>
</template>
