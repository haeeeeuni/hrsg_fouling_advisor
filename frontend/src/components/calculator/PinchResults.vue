<script setup>
/** 핀치·어프로치 결과 (specs/05 CALC-4). 공개 계산이라 식과 판정 기준을 함께 보여 준다. */
import HrsgDiagram from '@/components/calculator/HrsgDiagram.vue'
import ResultNotices from '@/components/calculator/ResultNotices.vue'
import StatusBadge from '@/components/common/StatusBadge.vue'
import { formatTemp } from '@/utils/format'

defineProps({
  data: { type: Object, required: true },
})
</script>

<template>
  <div>
    <!-- 임시값·SMP 출처 안내는 결과보다 먼저 보이게 위에 둔다 (specs/12 §6). -->
    <ResultNotices class="mb-3" :meta="data.meta" />
    <div class="d-flex flex-wrap align-items-center gap-2 mb-3">
      <span class="text-secondary small">종합</span>
      <StatusBadge :level="data.results.level" size="lg" data-testid="pinch-overall" />
    </div>

    <div v-for="stage in data.results.stages" :key="stage.label" class="card mb-3">
      <div class="card-body">
        <div class="d-flex flex-wrap justify-content-between gap-2 mb-2">
          <h3 class="h6 mb-0">{{ stage.label }} · 드럼 {{ stage.drum_pressure_barg }} bar(g)</h3>
          <span class="small text-secondary">포화온도 {{ formatTemp(stage.saturation_temp_c) }}</span>
        </div>
        <div class="row g-3 mb-2">
          <div class="col-6">
            <p class="ui-stat-label mb-1">핀치</p>
            <p class="ui-stat-value mb-1">{{ formatTemp(stage.pinch_c) }}</p>
            <StatusBadge :level="stage.pinch_level" />
          </div>
          <div class="col-6">
            <p class="ui-stat-label mb-1">어프로치</p>
            <p class="ui-stat-value mb-1">{{ formatTemp(stage.approach_c) }}</p>
            <StatusBadge :level="stage.approach_level" />
          </div>
        </div>
        <ul v-if="stage.notes.length" class="small mb-2 ps-3">
          <li v-for="note in stage.notes" :key="note">{{ note }}</li>
        </ul>
        <HrsgDiagram :stage="stage" />
      </div>
    </div>

    <p class="small text-secondary">
      핀치 = 증발기 출구 가스 온도 − 드럼 포화온도 · 어프로치 = 드럼 포화온도 − 절탄기 출구 급수 온도
      (포화온도는 IAPWS-IF97, 게이지압 + 1.01325 bar). 설계값이 없으면 기준 범위
      핀치 {{ data.meta.criteria.pinch_range_c.join('~') }} ℃, 어프로치 {{ data.meta.criteria.approach_range_c.join('~') }} ℃ 로 판정합니다.
    </p>
  </div>
</template>
