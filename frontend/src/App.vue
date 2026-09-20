<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'

import AppNavbar from '@/components/common/AppNavbar.vue'
import AppSidebar from '@/components/common/AppSidebar.vue'
import ToastContainer from '@/components/common/ToastContainer.vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const route = useRoute()

// 로그인 화면과 부팅 전에는 셸(네비/사이드바)을 감춘다.
const showShell = computed(() => auth.isAuthenticated && route.name !== 'login')
</script>

<template>
  <div v-if="!auth.initialized" class="d-flex justify-content-center align-items-center vh-100">
    <div class="spinner-border text-primary" role="status">
      <span class="visually-hidden">불러오는 중</span>
    </div>
  </div>

  <template v-else>
    <AppNavbar v-if="showShell" />
    <div class="d-flex" :class="{ 'pt-0': !showShell }">
      <AppSidebar v-if="showShell" />
      <main class="app-main flex-grow-1" :class="showShell ? 'p-4' : ''">
        <RouterView />
      </main>
    </div>
  </template>

  <ToastContainer />
</template>
