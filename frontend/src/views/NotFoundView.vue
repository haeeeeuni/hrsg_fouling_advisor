<script setup>
import EmptyState from '@/components/common/EmptyState.vue'
</script>

<template>
  <div class="container py-5">
    <EmptyState title="페이지를 찾을 수 없습니다." icon="bi-question-circle">
      <template #action>
        <RouterLink class="btn btn-outline-primary btn-sm" :to="{ name: 'dashboard' }">
          대시보드로 이동
        </RouterLink>
      </template>
    </EmptyState>
  </div>
</template>
