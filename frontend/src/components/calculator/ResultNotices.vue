<script setup>
/**
 * 결과 안내 — 임시 참조값(specs/06 REF-6), SMP 기준일·출처(REF-4), 가정 안내.
 * 확인되지 않은 가격을 공식 가격처럼 보이지 않게 SMP 에는 항상 기준일·출처를 붙인다.
 */
import { computed } from 'vue'

import { formatDate } from '@/utils/format'

const props = defineProps({
  meta: { type: Object, required: true },
})

const smp = computed(() => props.meta.smp)
</script>

<template>
  <div>
    <div
      v-for="notice in meta.notices"
      :key="notice"
      class="alert alert-info py-2 small mb-2 d-flex gap-2"
      role="note"
    >
      <i class="bi bi-info-circle" aria-hidden="true"></i>
      <span>{{ notice }}</span>
    </div>
    <p v-if="smp" class="small text-secondary mb-0" data-testid="smp-source">
      SMP {{ smp.value }} 원/kWh ·
      <template v-if="smp.user_input">
        <span class="badge text-bg-secondary">사용자 입력</span>
      </template>
      <template v-else>
        기준일 {{ formatDate(smp.as_of) }} · 출처 {{ smp.source }}
        <span v-if="smp.is_estimate" class="badge text-bg-warning ms-1">추정</span>
      </template>
    </p>
    <p class="small text-secondary mb-0">
      계산 파라미터 {{ meta.param_version }} · 계산식 {{ meta.formula_version }}
    </p>
  </div>
</template>
