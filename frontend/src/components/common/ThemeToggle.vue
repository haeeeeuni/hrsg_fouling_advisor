<script setup>
import { computed } from 'vue'

import { useUiStore } from '@/stores/ui'

const ui = useUiStore()

// 버튼은 "누르면 무엇이 되는지"를 말한다.
const label = computed(() => (ui.theme === 'dark' ? '라이트 모드로 전환' : '다크 모드로 전환'))
</script>

<template>
  <button
    type="button"
    class="ui-icon-button"
    :aria-label="label"
    :title="label"
    @click="ui.toggleTheme()"
  >
    <i class="bi" :class="ui.theme === 'dark' ? 'bi-sun' : 'bi-moon-stars'" aria-hidden="true"></i>
  </button>
</template>
