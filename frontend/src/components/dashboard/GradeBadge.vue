<script setup>
import { computed } from 'vue'

import { GRADE } from '@/utils/constants'

const props = defineProps({
  grade: { type: String, default: null },
  size: { type: String, default: 'normal' },
})

// 색상만으로 정보를 전달하지 않고 항상 텍스트 라벨을 함께 표시한다 (specs/11 §3, 접근성).
const meta = computed(() => GRADE[props.grade] ?? null)
</script>

<template>
  <span
    v-if="meta"
    class="badge"
    :class="[`text-bg-${meta.variant}`, size === 'large' ? 'fs-5 px-3 py-2' : '']"
    :title="meta.range"
  >
    {{ meta.label }}
  </span>
  <span v-else class="text-secondary">–</span>
</template>
