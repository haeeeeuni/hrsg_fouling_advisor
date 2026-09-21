<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import NotificationBell from '@/components/common/NotificationBell.vue'
import { useToast } from '@/composables/useToast'
import { useAuthStore } from '@/stores/auth'
import { useUnitsStore } from '@/stores/units'

const auth = useAuthStore()
const units = useUnitsStore()
const route = useRoute()
const router = useRouter()
const toast = useToast()

// 호기 선택은 전역 상태이며 페이지 이동·새로고침 후에도 유지된다 (AC-16-3).
units.fetchUnits()

// Spark 네비는 브랜드 대신 현재 화면 제목을 보여준다 — 브랜드는 사이드바로 갔다 (specs/20).
const pageTitle = computed(() => route.meta?.title ?? '')

async function onLogout() {
  await auth.logout()
  toast.push('로그아웃되었습니다.', 'info')
  router.push({ name: 'login' })
}
</script>

<template>
  <header class="spark-navbar">
    <h1 class="spark-page-title">{{ pageTitle }}</h1>

    <div class="ms-auto d-flex align-items-center gap-2">
      <div v-if="units.activeUnits.length">
        <label for="navUnit" class="visually-hidden">호기 선택</label>
        <select
          id="navUnit"
          class="form-select form-select-sm spark-pill"
          :value="units.selectedUnitId"
          @change="units.selectUnit(Number($event.target.value))"
        >
          <option v-for="unit in units.activeUnits" :key="unit.id" :value="unit.id">
            {{ unit.code }} — {{ unit.name }}
          </option>
        </select>
      </div>

      <NotificationBell />

      <div class="dropdown">
        <button
          class="btn btn-sm spark-pill dropdown-toggle"
          type="button"
          data-bs-toggle="dropdown"
          aria-expanded="false"
        >
          {{ auth.user?.full_name }} ({{ auth.user?.employee_no }})
        </button>
        <ul class="dropdown-menu dropdown-menu-end">
          <li>
            <RouterLink class="dropdown-item" :to="{ name: 'profile' }">내 정보</RouterLink>
          </li>
          <li><hr class="dropdown-divider" /></li>
          <li>
            <button class="dropdown-item" type="button" @click="onLogout">로그아웃</button>
          </li>
        </ul>
      </div>
    </div>
  </header>
</template>
