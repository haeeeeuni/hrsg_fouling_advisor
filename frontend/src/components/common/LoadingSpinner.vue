<script setup>
defineProps({
  label: { type: String, default: '불러오는 중' },
})
</script>

<template>
  <div class="d-flex justify-content-center align-items-center py-5">
    <div class="spinner-border text-primary" role="status">
      <span class="visually-hidden">{{ label }}</span>
    </div>
    <span class="ms-3 text-secondary">{{ label }}</span>
  </div>
</template>
