<script setup>
/** 아직 구현되지 않은 기능의 자리 (PROJECT.md §6 마일스톤). 해당 단계에서 실제 화면으로 바뀐다. */
import EmptyState from '@/components/common/EmptyState.vue'

defineProps({
  feature: { type: Object, required: true },
})
</script>

<template>
  <div class="ui-container">
    <h1 class="h3 mb-1">{{ feature.title }}</h1>
    <p class="text-secondary">{{ feature.summary }}</p>
    <div class="card">
      <EmptyState
        title="준비 중인 기능입니다"
        :description="`${feature.detail} (구현 예정 단계: ${feature.milestone})`"
        :icon="feature.icon"
      >
        <template #action>
          <RouterLink class="btn btn-outline-secondary btn-sm" :to="{ name: 'home' }">홈으로</RouterLink>
        </template>
      </EmptyState>
    </div>
  </div>
</template>
