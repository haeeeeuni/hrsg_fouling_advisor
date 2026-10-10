<script setup>
/** 정상·주의·위험 공통 배지 — 색 + 아이콘 + 문구 (specs/12 UI-6). 색만으로 구분하지 않는다. */
import { computed } from 'vue'

import { STATUS } from '@/utils/constants'

const props = defineProps({
  level: { type: String, required: true },
  /** 기본 문구 대신 쓸 말(예: '주의 — 경보 구간') */
  label: { type: String, default: '' },
  size: { type: String, default: 'md' }, // md | lg
})

const meta = computed(() => STATUS[props.level] ?? STATUS.NORMAL)
</script>

<template>
  <span
    class="badge ui-status-badge"
    :class="[`text-bg-${meta.variant}`, size === 'lg' ? 'ui-status-badge--lg' : '']"
    :data-level="level"
  >
    <i class="bi me-1" :class="meta.icon" aria-hidden="true"></i>{{ label || meta.label }}
  </span>
</template>
