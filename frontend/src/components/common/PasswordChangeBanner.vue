<script setup>
/** 기본 관리자·비밀번호 초기화 직후에는 변경을 요구한다 (specs/01 AUTH-9, specs/11 §3). */
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
</script>

<template>
  <!-- 화면마다 떠 있는 안내라 경고(alert)로 읽히게 하지 않는다. 영역 이름으로 찾을 수 있게만 한다. -->
  <div
    v-if="auth.mustChangePassword"
    class="ui-banner alert alert-warning rounded-0 mb-0"
    role="region"
    aria-label="비밀번호 변경 안내"
  >
    <div class="container-fluid ui-container d-flex flex-wrap align-items-center gap-2">
      <i class="bi bi-shield-exclamation" aria-hidden="true"></i>
      <span>초기 비밀번호를 사용하고 있습니다. 보안을 위해 비밀번호를 변경해 주세요.</span>
      <RouterLink class="alert-link ms-auto" :to="{ name: 'profile' }">비밀번호 변경</RouterLink>
    </div>
  </div>
</template>
