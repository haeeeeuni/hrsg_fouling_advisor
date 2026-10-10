<script setup>
import { onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { fetchOverview } from '@/api/users'
import { useToast } from '@/composables/useToast'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const toast = useToast()

/** 관리자에게만 — 승인 대기 건수 배지 (specs/01 §4). 실패해도 메뉴는 동작한다. */
const pendingSignups = ref(0)

async function loadPending() {
  if (!auth.isAdmin) return
  try {
    const { data } = await fetchOverview()
    pendingSignups.value = data.pending_signups
  } catch {
    pendingSignups.value = 0
  }
}

onMounted(loadPending)
// 관리자 화면에서 승인·반려하면 배지를 갱신하도록 경로가 바뀔 때마다 다시 읽는다.
watch(() => router.currentRoute.value.fullPath, loadPending)

async function onLogout() {
  await auth.logout()
  toast.push('로그아웃되었습니다.', 'info')
  router.push({ name: 'intro' })
}
</script>

<template>
  <div class="dropdown">
    <button
      class="btn btn-sm ui-pill dropdown-toggle"
      type="button"
      data-bs-toggle="dropdown"
      aria-expanded="false"
    >
      <i class="bi bi-person-circle me-1" aria-hidden="true"></i>
      <span class="ui-user-label">{{ auth.user?.full_name }}</span>
      <span v-if="pendingSignups" class="badge text-bg-warning ms-1">
        {{ pendingSignups }}<span class="visually-hidden">건 승인 대기</span>
      </span>
    </button>
    <ul class="dropdown-menu dropdown-menu-end">
      <li class="dropdown-header small">
        {{ auth.user?.username }} · {{ auth.user?.organization }}
      </li>
      <li>
        <RouterLink class="dropdown-item" :to="{ name: 'profile' }">
          <i class="bi bi-person me-2" aria-hidden="true"></i>내 정보
        </RouterLink>
      </li>
      <li v-if="auth.isAdmin">
        <RouterLink class="dropdown-item" :to="{ name: 'admin-overview' }">
          <i class="bi bi-gear me-2" aria-hidden="true"></i>관리자 모드
          <span v-if="pendingSignups" class="badge text-bg-warning ms-1">
            승인 대기 {{ pendingSignups }}
          </span>
        </RouterLink>
      </li>
      <li><hr class="dropdown-divider" /></li>
      <li>
        <button class="dropdown-item" type="button" @click="onLogout">
          <i class="bi bi-box-arrow-right me-2" aria-hidden="true"></i>로그아웃
        </button>
      </li>
    </ul>
  </div>
</template>
