<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import {
  fetchNotifications,
  markAllNotificationsRead,
  markNotificationRead,
} from '@/api/optional'
import { formatDateTime } from '@/utils/format'

// 등급 상승 알림은 자동 재계산이 만들기 때문에 주기적으로 확인한다 (specs/19 §1.4).
const POLL_INTERVAL_MS = 60000

const items = ref([])
const unreadCount = ref(0)
const loading = ref(false)
let timer = null

const hasUnread = computed(() => unreadCount.value > 0)

async function load() {
  loading.value = true
  try {
    const { data } = await fetchNotifications({ page_size: 10 })
    items.value = data.results ?? []
    unreadCount.value = data.unread_count ?? 0
  } catch {
    // 알림은 부가 기능이므로 실패해도 화면을 막지 않는다.
    items.value = []
  } finally {
    loading.value = false
  }
}

async function onRead(item) {
  if (item.is_read) return
  await markNotificationRead(item.id)
  item.is_read = true
  unreadCount.value = Math.max(0, unreadCount.value - 1)
}

async function onReadAll() {
  await markAllNotificationsRead()
  items.value.forEach((item) => {
    item.is_read = true
  })
  unreadCount.value = 0
}

onMounted(() => {
  load()
  timer = setInterval(load, POLL_INTERVAL_MS)
})

onBeforeUnmount(() => {
  if (timer) clearInterval(timer)
})
</script>

<template>
  <div class="dropdown">
    <button
      class="btn btn-sm spark-pill position-relative"
      type="button"
      data-bs-toggle="dropdown"
      aria-expanded="false"
      :aria-label="`알림 ${unreadCount}건`"
      @click="load"
    >
      알림
      <span
        v-if="hasUnread"
        class="position-absolute top-0 start-100 translate-middle badge rounded-pill bg-danger"
      >
        {{ unreadCount }}
      </span>
    </button>

    <div class="dropdown-menu dropdown-menu-end p-0" style="min-width: 22rem">
      <div class="d-flex align-items-center justify-content-between px-3 py-2 border-bottom">
        <strong class="small">알림</strong>
        <button
          v-if="hasUnread"
          class="btn btn-link btn-sm p-0"
          type="button"
          @click.stop="onReadAll"
        >
          모두 읽음
        </button>
      </div>

      <p v-if="loading" class="text-muted small m-0 px-3 py-3">불러오는 중…</p>
      <p v-else-if="!items.length" class="text-muted small m-0 px-3 py-3">새 알림이 없습니다.</p>

      <ul v-else class="list-unstyled m-0 overflow-auto" style="max-height: 20rem">
        <li
          v-for="item in items"
          :key="item.id"
          class="px-3 py-2 border-bottom"
          :class="{ 'bg-body-secondary': !item.is_read }"
          @click="onRead(item)"
        >
          <div class="d-flex align-items-start gap-2">
            <span
              class="badge"
              :class="item.level === 'WARNING' ? 'text-bg-danger' : 'text-bg-secondary'"
            >
              {{ item.level === 'WARNING' ? '경고' : '정보' }}
            </span>
            <div class="flex-grow-1">
              <div class="small fw-semibold">{{ item.title }}</div>
              <div class="small text-muted">{{ item.message }}</div>
              <div class="small text-muted">{{ formatDateTime(item.created_at) }}</div>
            </div>
          </div>
        </li>
      </ul>
    </div>
  </div>
</template>
