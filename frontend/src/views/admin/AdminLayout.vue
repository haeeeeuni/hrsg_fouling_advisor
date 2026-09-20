<script setup>
const items = [
  { to: { name: 'admin-units' }, label: '호기 관리', icon: 'bi-hdd-stack' },
  { to: { name: 'admin-column-mapping' }, label: '컬럼 매핑', icon: 'bi-diagram-3' },
  { to: { name: 'admin-cleaning-events' }, label: '세정 이력', icon: 'bi-droplet' },
  { to: { name: 'admin-keywords' }, label: '오염 키워드', icon: 'bi-tags' },
]
</script>

<template>
  <div>
    <h1 class="h4 mb-3">관리자 콘솔</h1>
    <ul class="nav nav-tabs mb-3">
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
