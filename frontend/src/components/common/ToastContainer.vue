<script setup>
import { useToast } from '@/composables/useToast'

const { toasts, dismiss } = useToast()
</script>

<template>
  <div class="toast-container position-fixed bottom-0 end-0 p-3" style="z-index: 1080">
    <div
      v-for="toast in toasts"
      :key="toast.id"
      class="toast show align-items-center text-bg-light border-0 mb-2"
      role="alert"
      aria-live="assertive"
      aria-atomic="true"
    >
      <div class="d-flex">
        <div class="toast-body">
          <span class="badge me-2" :class="`text-bg-${toast.variant}`">알림</span>
          {{ toast.message }}
        </div>
        <button
          type="button"
          class="btn-close me-2 m-auto"
          aria-label="닫기"
          @click="dismiss(toast.id)"
        ></button>
      </div>
    </div>
  </div>
</template>
