<script setup>
import { useRouter } from 'vue-router'

import { useToast } from '@/composables/useToast'
import { useAuthStore } from '@/stores/auth'
import { useUnitsStore } from '@/stores/units'

const auth = useAuthStore()
const units = useUnitsStore()
const router = useRouter()
const toast = useToast()

// 호기 선택은 전역 상태이며 페이지 이동·새로고침 후에도 유지된다 (AC-16-3).
units.fetchUnits()

async function onLogout() {
  await auth.logout()
  toast.push('로그아웃되었습니다.', 'info')
  router.push({ name: 'login' })
}
</script>

<template>
  <nav class="navbar navbar-expand navbar-dark bg-dark px-3">
    <RouterLink class="navbar-brand fw-semibold" :to="{ name: 'dashboard' }">
      HRSG 오염도 진단
    </RouterLink>

    <div v-if="units.activeUnits.length" class="ms-3">
      <label for="navUnit" class="visually-hidden">호기 선택</label>
      <select
        id="navUnit"
        class="form-select form-select-sm"
        :value="units.selectedUnitId"
        @change="units.selectUnit(Number($event.target.value))"
      >
        <option v-for="unit in units.activeUnits" :key="unit.id" :value="unit.id">
          {{ unit.code }} — {{ unit.name }}
        </option>
      </select>
    </div>

    <div class="ms-auto dropdown">
      <button
        class="btn btn-sm btn-outline-light dropdown-toggle"
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
  </nav>
</template>
