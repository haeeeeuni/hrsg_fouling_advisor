<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'

import AppNavbar from '@/components/common/AppNavbar.vue'
import AppSidebar from '@/components/common/AppSidebar.vue'
import ToastContainer from '@/components/common/ToastContainer.vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const route = useRoute()

// 로그인 화면과 부팅 전에는 셸(사이드바·네비)을 감춘다.
const showShell = computed(() => auth.isAuthenticated && route.name !== 'login')
</script>

<template>
  <div v-if="!auth.initialized" class="d-flex justify-content-center align-items-center vh-100">
    <div class="spinner-border text-primary" role="status">
      <span class="visually-hidden">불러오는 중</span>
    </div>
  </div>

  <!--
    Spark 레이아웃 (specs/20): 전체 높이 고정 사이드바(좌) + 메인 영역 상단 네비.
    사이드바가 fixed 라서 메인이 .spark-main 의 margin-left 로 자리를 비운다.
  -->
  <template v-else>
    <AppSidebar v-if="showShell" />
    <div class="app-main" :class="showShell ? 'spark-main' : 'spark-main spark-main--bare'">
      <AppNavbar v-if="showShell" />
      <main :class="showShell ? 'spark-content' : ''">
        <RouterView />
      </main>
    </div>
  </template>

  <ToastContainer />
</template>
