<script setup>
import EmptyState from '@/components/common/EmptyState.vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
</script>

<template>
  <div class="ui-container">
    <EmptyState title="페이지를 찾을 수 없습니다." icon="bi-question-circle">
      <template #action>
        <RouterLink
          class="btn btn-outline-primary btn-sm"
          :to="auth.isAuthenticated ? { name: 'home' } : { name: 'intro' }"
        >
          {{ auth.isAuthenticated ? '홈으로 이동' : '소개 화면으로 이동' }}
        </RouterLink>
      </template>
    </EmptyState>
  </div>
</template>
