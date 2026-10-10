<script setup>
/**
 * 모든 화면 공통 상단 바 (specs/11 §3, UI-2).
 * 좌: 앱 이름 / 가운데: 기능 메뉴(로그인 시) / 우: 테마 전환 + 로그인 버튼 또는 사용자 메뉴.
 * 모바일 폭에서는 기능 메뉴가 햄버거 버튼 아래로 접힌다.
 */
import Collapse from 'bootstrap/js/dist/collapse'
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import LoginPanel from '@/components/common/LoginPanel.vue'
import ThemeToggle from '@/components/common/ThemeToggle.vue'
import UserMenu from '@/components/common/UserMenu.vue'
import { useAuthStore } from '@/stores/auth'
import { FEATURES } from '@/utils/constants'

const auth = useAuthStore()
const route = useRoute()
const featureNav = ref(null)

// 모바일에서 메뉴를 고르면 접힌 메뉴를 닫는다(열린 채로 본문을 가리지 않게).
watch(
  () => route.fullPath,
  () => {
    if (featureNav.value) Collapse.getInstance(featureNav.value)?.hide()
  },
)

const brandTarget = computed(() => (auth.isAuthenticated ? { name: 'home' } : { name: 'intro' }))
</script>

<template>
  <header class="ui-header navbar navbar-expand-lg">
    <div class="container-fluid ui-header-inner">
      <RouterLink class="ui-brand" :to="brandTarget">
        <i class="bi bi-fire" aria-hidden="true"></i>
        <span>HRSG 레퍼런스 앱</span>
      </RouterLink>

      <div class="ui-header-actions order-lg-last">
        <ThemeToggle />
        <UserMenu v-if="auth.isAuthenticated" />
        <LoginPanel v-else />
        <button
          v-if="auth.isAuthenticated"
          class="navbar-toggler ui-icon-button"
          type="button"
          data-bs-toggle="collapse"
          data-bs-target="#featureNav"
          aria-controls="featureNav"
          aria-expanded="false"
          aria-label="기능 메뉴 열기"
        >
          <i class="bi bi-list" aria-hidden="true"></i>
        </button>
      </div>

      <nav v-if="auth.isAuthenticated" id="featureNav" ref="featureNav" class="collapse navbar-collapse" aria-label="기능">
        <ul class="navbar-nav ui-feature-nav">
          <li v-for="feature in FEATURES" :key="feature.key" class="nav-item">
            <RouterLink class="nav-link" :to="{ name: feature.route }" active-class="active">
              <i class="bi" :class="feature.icon" aria-hidden="true"></i>
              {{ feature.title }}
            </RouterLink>
          </li>
        </ul>
      </nav>
    </div>
  </header>
</template>
