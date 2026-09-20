<script setup>
import { computed } from 'vue'

import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()

// Phase가 진행되며 분석 실행·리포트 항목이 추가된다 (specs/16 §4).
const items = computed(() => {
  const base = [
    { to: { name: 'dashboard' }, label: '대시보드', icon: 'bi-speedometer2' },
    { to: { name: 'upload' }, label: '데이터 업로드', icon: 'bi-cloud-arrow-up' },
    { to: { name: 'analysis-run' }, label: '분석 실행', icon: 'bi-play-circle' },
    { to: { name: 'comparison' }, label: '세정 전후 비교', icon: 'bi-arrow-left-right' },
    { to: { name: 'maintenance' }, label: '정비 이력', icon: 'bi-wrench' },
    { to: { name: 'reports' }, label: '리포트', icon: 'bi-file-earmark-text' },
  ]
  // 관리자 메뉴는 일반 사용자에게 보이지 않는다 (AC-16-2).
  if (auth.isAdmin) {
    base.push({ to: { name: 'admin-users' }, label: '관리자 콘솔', icon: 'bi-gear' })
  }
  return base
})
</script>

<template>
  <aside class="app-sidebar bg-body-tertiary border-end p-3">
    <ul class="nav nav-pills flex-column gap-1">
      <li v-for="item in items" :key="item.label" class="nav-item">
        <RouterLink class="nav-link" :to="item.to" active-class="active">
          <i class="bi" :class="item.icon" aria-hidden="true"></i>
          <span class="ms-2">{{ item.label }}</span>
        </RouterLink>
      </li>
    </ul>
  </aside>
</template>
