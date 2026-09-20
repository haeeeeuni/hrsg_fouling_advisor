<script setup>
defineProps({
  label: { type: String, required: true },
  value: { type: String, required: true },
  hint: { type: String, default: '' },
  variant: { type: String, default: '' },
})
</script>

<template>
  <div class="card h-100">
    <div class="card-body">
      <p class="small text-secondary mb-1">{{ label }}</p>
      <p class="h3 mb-1" :class="variant ? `text-${variant}` : ''">
        <slot name="value">{{ value }}</slot>
      </p>
      <p v-if="hint || $slots.hint" class="small text-secondary mb-0">
        <slot name="hint">{{ hint }}</slot>
      </p>
    </div>
  </div>
</template>
