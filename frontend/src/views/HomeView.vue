<script setup>
/** 로그인 후 첫 화면 — 세 기능 진입 카드 (specs/11 §1). */
import { useAuthStore } from '@/stores/auth'
import { FEATURES } from '@/utils/constants'

const auth = useAuthStore()
</script>

<template>
  <div class="ui-container">
    <div class="mb-4">
      <h1 class="h3 mb-1">안녕하세요, {{ auth.user?.full_name }}님</h1>
      <p class="text-secondary mb-0">무엇을 도와드릴까요?</p>
    </div>

    <div class="row g-3">
      <div v-for="feature in FEATURES" :key="feature.key" class="col-12 col-md-4">
        <RouterLink :to="{ name: feature.route }" class="card h-100 ui-feature-card text-decoration-none">
          <div class="card-body">
            <i class="bi ui-feature-icon" :class="feature.icon" aria-hidden="true"></i>
            <h2 class="h5 mt-3 mb-2">{{ feature.title }}</h2>
            <p class="mb-0 text-body">{{ feature.summary }}</p>
          </div>
          <div class="card-footer bg-transparent border-0 pt-0">
            <span class="fw-semibold">
              시작하기 <i class="bi bi-arrow-right ms-1" aria-hidden="true"></i>
            </span>
          </div>
        </RouterLink>
      </div>
    </div>
  </div>
</template>
