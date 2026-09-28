<script setup>
import { ref, watch } from 'vue'

import { fetchNotifications, markNotificationRead } from '@/api/optional'
import { formatDateTime } from '@/utils/format'

// specs/19 §1.4 — 알림 센터(벨)와 함께 대시보드 배너로도 보여준다.
// 벨은 전체 호기를 모아 보고, 이 배너는 **지금 보고 있는 호기**의 미확인 알림만 띄운다.
const props = defineProps({ unitId: { type: [Number, String], default: null } })

const items = ref([])

async function load() {
  if (!props.unitId) {
    items.value = []
    return
  }
  try {
    const { data } = await fetchNotifications({
      unit_id: props.unitId,
      unread: 'true',
      page_size: 3,
    })
    items.value = data.results ?? []
  } catch {
    // 알림은 부가 기능이다 — 실패해도 대시보드를 막지 않는다.
    items.value = []
  }
}

async function dismiss(item) {
  try {
    await markNotificationRead(item.id)
  } finally {
    items.value = items.value.filter((n) => n.id !== item.id)
  }
}

watch(() => props.unitId, load, { immediate: true })
</script>

<template>
  <div
    v-for="item in items"
    :key="item.id"
    class="alert alert-danger d-flex justify-content-between align-items-start mb-2"
    role="alert"
  >
    <div class="me-3">
      <strong>{{ item.title }}</strong>
      <div class="small mt-1">{{ item.message }}</div>
      <div class="small text-muted mt-1">{{ formatDateTime(item.created_at) }}</div>
    </div>
    <button
      type="button"
      class="btn-close flex-shrink-0"
      aria-label="알림 확인"
      @click="dismiss(item)"
    ></button>
  </div>
</template>
