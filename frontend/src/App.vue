<script setup>
import AppHeader from '@/components/common/AppHeader.vue'
import PasswordChangeBanner from '@/components/common/PasswordChangeBanner.vue'
import ToastContainer from '@/components/common/ToastContainer.vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
</script>

<template>
  <!-- 레이아웃 (specs/11 §4): 상단 바 + 본문. 관리자 모드는 본문 안에 사이드바를 둔다. -->
  <AppHeader />
  <PasswordChangeBanner />

  <main class="ui-main">
    <div v-if="!auth.initialized" class="d-flex justify-content-center py-5">
      <div class="spinner-border text-primary" role="status">
        <span class="visually-hidden">불러오는 중</span>
      </div>
    </div>
    <RouterView v-else />
  </main>

  <ToastContainer />
</template>
