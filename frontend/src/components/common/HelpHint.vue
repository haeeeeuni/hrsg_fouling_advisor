<script setup>
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'

/**
 * 항목 옆의 `?` 설명 (specs/16 §8).
 *
 * Bootstrap 의 popover 는 별도 JS 모듈과 요소별 초기화가 필요하다. 여기서 쓰는 건
 * 짧은 설명 하나뿐이라 Vue 상태로 직접 다룬다.
 *
 * 마우스오버가 아니라 **클릭**으로 연다 — 터치 기기에는 hover 가 없고,
 * hover 로만 열리면 키보드 사용자가 읽을 방법이 없다.
 */
const props = defineProps({
  /** 무엇에 대한 설명인지. 스크린리더가 읽는 버튼 이름에 쓴다. */
  label: { type: String, required: true },
  /** 화면 오른쪽 끝 카드에서는 'end' 로 둬야 설명창이 잘리지 않는다. */
  align: { type: String, default: 'center' },
})

const open = ref(false)
const root = ref(null)

function toggle() {
  open.value = !open.value
}

function onDocumentClick(event) {
  if (root.value && !root.value.contains(event.target)) open.value = false
}

function onKeydown(event) {
  if (event.key === 'Escape') open.value = false
}

watch(open, async (value) => {
  if (value) {
    await nextTick()
    document.addEventListener('click', onDocumentClick)
    document.addEventListener('keydown', onKeydown)
  } else {
    document.removeEventListener('click', onDocumentClick)
    document.removeEventListener('keydown', onKeydown)
  }
})

onBeforeUnmount(() => {
  document.removeEventListener('click', onDocumentClick)
  document.removeEventListener('keydown', onKeydown)
})
</script>

<template>
  <span ref="root" class="ui-help-wrap">
    <button
      type="button"
      class="ui-help"
      :aria-expanded="open"
      :aria-label="`${props.label} 설명 ${open ? '닫기' : '열기'}`"
      @click.stop="toggle"
    >
      <span aria-hidden="true">?</span>
    </button>
    <span
      v-if="open"
      class="ui-help-pop"
      :class="{ 'ui-help-pop--end': props.align === 'end' }"
      role="note"
    >
      <slot />
    </span>
  </span>
</template>
