<script setup>
import { computed } from 'vue'

import { useAuthStore } from '@/stores/auth'
import { ROLE } from '@/utils/constants'

const auth = useAuthStore()

// Spark 사이드바는 메뉴를 섹션으로 묶는다 (specs/20).
const sections = computed(() => {
  const groups = [
    {
      title: '분석',
      items: [
        { to: { name: 'dashboard' }, label: '대시보드', icon: 'bi-speedometer2' },
        { to: { name: 'upload' }, label: '데이터 업로드', icon: 'bi-cloud-arrow-up' },
        { to: { name: 'analysis-run' }, label: '분석 실행', icon: 'bi-play-circle' },
      ],
    },
    {
      title: '이력 · 보고',
      items: [
        { to: { name: 'comparison' }, label: '세정 전후 비교', icon: 'bi-arrow-left-right' },
        { to: { name: 'maintenance' }, label: '정비 이력', icon: 'bi-wrench' },
        { to: { name: 'reports' }, label: '리포트', icon: 'bi-file-earmark-text' },
      ],
    },
  ]
  // 관리자 메뉴는 일반 사용자에게 보이지 않는다 (AC-16-2).
  if (auth.isAdmin) {
    groups.push({
      title: '관리',
      items: [{ to: { name: 'admin-users' }, label: '관리자 콘솔', icon: 'bi-gear' }],
    })
  }
  return groups
})
</script>

<template>
  <aside class="spark-sidebar">
    <RouterLink class="spark-brand" :to="{ name: 'dashboard' }">
      <i class="bi bi-fire" aria-hidden="true"></i>
      <span>HRSG 오염도 진단</span>
    </RouterLink>

    <nav class="flex-grow-1">
      <div v-for="section in sections" :key="section.title" class="mb-3">
        <p class="spark-menu-title">{{ section.title }}</p>
        <ul class="list-unstyled m-0">
          <li v-for="item in section.items" :key="item.label">
            <RouterLink class="spark-menu-link" :to="item.to" active-class="active">
              <i class="bi" :class="item.icon" aria-hidden="true"></i>
              <span>{{ item.label }}</span>
            </RouterLink>
          </li>
        </ul>
      </div>
    </nav>

    <div class="spark-sidebar-footer">
      <p class="spark-user-name mb-0">{{ auth.user?.full_name }}</p>
      <p class="mb-0">{{ ROLE[auth.user?.role] ?? '' }} · {{ auth.user?.employee_no }}</p>
    </div>
  </aside>
</template>
