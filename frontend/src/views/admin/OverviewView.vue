<script setup>
/**
 * 관리자 개요 — 지금 손봐야 할 것 (specs/08 ADM-3).
 * 마일스톤마다 항목이 늘어난다(색인 실패, LLM 키, 임시값 참조 데이터 등).
 */
import { onMounted, ref } from 'vue'

import { fetchOverview } from '@/api/users'

const overview = ref(null)
const error = ref(null)

onMounted(async () => {
  try {
    const { data } = await fetchOverview()
    overview.value = data
  } catch (err) {
    error.value = err.parsed ?? { message: '개요를 불러오지 못했습니다.' }
  }
})
</script>

<template>
  <div>
    <div v-if="error" class="alert alert-danger" role="alert">{{ error.message }}</div>

    <div class="row g-3">
      <div class="col-12 col-md-6 col-xl-4">
        <RouterLink :to="{ name: 'admin-signups' }" class="card h-100 ui-feature-card text-decoration-none">
          <div class="card-body">
            <p class="ui-stat-label">승인 대기 가입 신청</p>
            <p class="ui-stat-value text-body" data-testid="pending-signups">
              {{ overview ? overview.pending_signups : '–' }}<span class="fs-6 ms-1">건</span>
            </p>
            <span v-if="overview?.pending_signups" class="badge text-bg-warning">
              <i class="bi bi-exclamation-triangle-fill me-1" aria-hidden="true"></i>처리 필요
            </span>
            <span v-else-if="overview" class="badge text-bg-success">
              <i class="bi bi-check-circle-fill me-1" aria-hidden="true"></i>대기 없음
            </span>
          </div>
        </RouterLink>
      </div>
    </div>
  </div>
</template>
