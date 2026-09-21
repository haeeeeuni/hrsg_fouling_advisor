<script setup>
// specs/13 §3 관리자 메뉴 구성
const items = [
  { to: { name: 'admin-users' }, label: '사용자', icon: 'bi-people' },
  { to: { name: 'admin-units' }, label: '호기', icon: 'bi-hdd-stack' },
  { to: { name: 'admin-column-mapping' }, label: '컬럼 매핑', icon: 'bi-diagram-3' },
  { to: { name: 'admin-settings' }, label: '분석 설정', icon: 'bi-sliders' },
  { to: { name: 'admin-benefit-settings' }, label: '편익 기본값', icon: 'bi-cash-coin' },
  { to: { name: 'admin-cleaning-events' }, label: '세정 이력', icon: 'bi-droplet' },
  { to: { name: 'admin-keywords' }, label: '오염 키워드', icon: 'bi-tags' },
  { to: { name: 'admin-models' }, label: '모델 관리', icon: 'bi-cpu' },
  { to: { name: 'admin-run-history' }, label: '분석 이력', icon: 'bi-clock-history' },
  { to: { name: 'admin-audit-logs' }, label: '감사 로그', icon: 'bi-journal-text' },
  // specs/19 옵션 기능
  { to: { name: 'admin-unit-comparison' }, label: '호기 간 비교', icon: 'bi-bar-chart-steps' },
  { to: { name: 'admin-backtest' }, label: '예측 정확도', icon: 'bi-bullseye' },
]
</script>

<template>
  <div>
    <p class="spark-menu-title text-body-secondary px-0 mb-2">관리자 콘솔</p>
    <ul class="nav nav-tabs mb-3 flex-wrap">
      <li v-for="item in items" :key="item.label" class="nav-item">
        <RouterLink class="nav-link" :to="item.to" active-class="active">
          <i class="bi" :class="item.icon" aria-hidden="true"></i>
          <span class="ms-2">{{ item.label }}</span>
        </RouterLink>
      </li>
    </ul>
    <RouterView />
  </div>
</template>
