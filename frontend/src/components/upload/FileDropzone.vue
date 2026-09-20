<script setup>
import { ref } from 'vue'

const props = defineProps({
  accept: { type: String, default: '.csv' },
  disabled: { type: Boolean, default: false },
})
const emit = defineEmits(['select'])

const dragging = ref(false)
const inputRef = ref(null)

function pick(fileList) {
  const file = fileList?.[0]
  if (file) emit('select', file)
}

function onDrop(event) {
  dragging.value = false
  if (props.disabled) return
  pick(event.dataTransfer?.files)
}
</script>

<template>
  <div
    class="border border-2 border-dashed rounded p-4 text-center"
    :class="[dragging ? 'border-primary bg-body-tertiary' : 'border-secondary-subtle', disabled ? 'opacity-50' : '']"
    @dragover.prevent="dragging = !disabled"
    @dragleave.prevent="dragging = false"
    @drop.prevent="onDrop"
  >
    <i class="bi bi-cloud-arrow-up fs-2 text-secondary" aria-hidden="true"></i>
    <p class="mb-2 mt-2 small text-secondary">
      CSV 파일을 여기에 끌어다 놓거나 아래 버튼으로 선택하세요.
    </p>
    <button
      type="button"
      class="btn btn-outline-primary btn-sm"
      :disabled="disabled"
      @click="inputRef?.click()"
    >
      파일 선택
    </button>
    <input
      ref="inputRef"
      type="file"
      class="d-none"
      :accept="accept"
      :disabled="disabled"
      @change="pick($event.target.files)"
    />
  </div>
</template>
