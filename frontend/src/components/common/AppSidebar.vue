<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'

import { useAuthStore } from '@/stores/auth'
import { ROLE } from '@/utils/constants'

const auth = useAuthStore()
const route = useRoute()

/**
 * 관리자 콘솔의 하위 항목 (specs/13 §3).
 * 콘솔 안에 있을 때만 사이드바에 펼친다 — 12개를 항상 띄우면 사이드바가 너무 길어진다.
 */
const ADMIN_ITEMS = [
  { to: { name: 'admin-users' }, label: '사용자' },
  { to: { name: 'admin-units' }, label: '호기' },
  { to: { name: 'admin-column-mapping' }, label: '컬럼 매핑' },
  { to: { name: 'admin-settings' }, label: '분석 설정' },
  { to: { name: 'admin-benefit-settings' }, label: '편익 기본값' },
  { to: { name: 'admin-cleaning-events' }, label: '세정 이력' },
  { to: { name: 'admin-keywords' }, label: '오염 키워드' },
  { to: { name: 'admin-models' }, label: '모델 관리' },
  { to: { name: 'admin-run-history' }, label: '분석 이력' },
  { to: { name: 'admin-audit-logs' }, label: '감사 로그' },
  // specs/19 옵션 기능
  { to: { name: 'admin-unit-comparison' }, label: '호기 간 비교' },
  { to: { name: 'admin-backtest' }, label: '예측 정확도' },
]

/**
 * 관리자 콘솔 안에 있는가.
 *
 * RouterLink 의 active-class 는 링크가 가리키는 경로 기준이라, '관리자 콘솔' 이
 * /admin/users 를 가리키면 /admin/settings 에서는 활성이 풀린다. 부모 항목은
 * 경로 접두로 직접 판정한다.
 */
const inAdmin = computed(() => route.path.startsWith('/admin'))

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
      items: [
        {
          to: { name: 'admin-users' },
          label: '관리자 콘솔',
          icon: 'bi-gear',
          children: ADMIN_ITEMS,
        },
      ],
    })
  }
  return groups
})
</script>

<template>
  <aside class="ui-sidebar">
    <RouterLink class="ui-brand" :to="{ name: 'dashboard' }">
      <i class="bi bi-fire" aria-hidden="true"></i>
      <span>HRSG 오염도 진단</span>
    </RouterLink>

    <nav class="flex-grow-1">
      <div v-for="section in sections" :key="section.title" class="mb-3">
        <p class="ui-menu-title">{{ section.title }}</p>
        <ul class="list-unstyled m-0">
          <li v-for="item in section.items" :key="item.label">
            <!--
              하위 항목이 있는 부모는 경로 접두로 활성을 판정한다. RouterLink 의
              active-class 에 맡기면 첫 하위 화면에서만 활성이 된다.
            -->
            <RouterLink
              class="ui-menu-link"
              :class="{ active: item.children && inAdmin }"
              :to="item.to"
              :active-class="item.children ? '' : 'active'"
              :aria-current="item.children && inAdmin ? 'true' : undefined"
            >
              <i class="bi" :class="item.icon" aria-hidden="true"></i>
              <span>{{ item.label }}</span>
            </RouterLink>

            <ul v-if="item.children && inAdmin" class="list-unstyled ui-menu-sub">
              <li v-for="child in item.children" :key="child.label">
                <RouterLink class="ui-menu-link ui-menu-link--sub" :to="child.to" active-class="active">
                  <span>{{ child.label }}</span>
                </RouterLink>
              </li>
            </ul>
          </li>
        </ul>
      </div>
    </nav>

    <div class="ui-sidebar-footer">
      <p class="ui-user-name mb-0">{{ auth.user?.full_name }}</p>
      <p class="mb-0">{{ ROLE[auth.user?.role] ?? '' }} · {{ auth.user?.employee_no }}</p>
    </div>
  </aside>
</template>
