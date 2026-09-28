<script setup>
import HelpHint from '@/components/common/HelpHint.vue'
import { formatTemp } from '@/utils/format'

defineProps({ metrics: { type: Object, default: null } })

const BADGE = {
  GOOD: { label: '양호', variant: 'success' },
  FAIR: { label: '주의', variant: 'warning' },
  POOR: { label: '불량', variant: 'danger' },
}

/** specs/06 §5 — R² 와 MAE 각각의 밴드 중 나쁜 쪽을 배지로 삼는다. */
function badgeFor(model, isStack) {
  if (!model?.metrics) return null
  const { r2, mae } = model.metrics
  const maeGood = isStack ? 3 : Number.POSITIVE_INFINITY
  const maeWarn = isStack ? 6 : Number.POSITIVE_INFINITY
  if (r2 >= 0.85 && mae <= maeGood) return BADGE.GOOD
  if (r2 >= 0.7 && mae <= maeWarn) return BADGE.FAIR
  return BADGE.POOR
}

function fmt(value, digits = 3) {
  return value === null || value === undefined || Number.isNaN(value) ? '–' : value.toFixed(digits)
}
</script>

<template>
  <div class="card h-100">
    <div class="card-body">
      <h2 class="h6 mb-3 d-flex align-items-center gap-2">
        <span>예측 모델 정확도</span>
        <HelpHint label="예측 모델 정확도">
          오염도 지수는 <strong>기대값 모델이 예측한 값과 실측의 차이</strong>로
          계산합니다. 이 패널은 그 모델이 얼마나 잘 맞는지 보여줍니다.
          <br /><br />
          <strong>MAE</strong> 는 평균 오차입니다(차압 kPa, 스택온도 ℃). 작을수록 좋습니다.
          <br />
          <strong>R²</strong> 는 설명력인데, 청정 기준 기간처럼 값이 거의 변하지 않는
          구간에서는 오차가 작아도 낮게 나옵니다. 그래서 변동폭이 작으면 R² 판정을
          보류하고 MAE 만으로 등급을 매깁니다.
        </HelpHint>
      </h2>

      <template v-if="metrics">
        <div
          v-for="(item, key) in { dp: metrics.dp, stack_temp: metrics.stack_temp }"
          :key="key"
          class="mb-3"
        >
          <div class="d-flex justify-content-between align-items-center">
            <span class="small fw-semibold">{{ key === 'dp' ? '차압' : '스택온도' }}</span>
            <span
              v-if="badgeFor(item, key !== 'dp')"
              class="badge"
              :class="`text-bg-${badgeFor(item, key !== 'dp').variant}`"
            >
              {{ badgeFor(item, key !== 'dp').label }}
            </span>
          </div>
          <dl v-if="item" class="row small mb-0 mt-1">
            <dt class="col-4 text-secondary fw-normal">R²</dt>
            <dd class="col-8 mb-0">{{ fmt(item.metrics?.r2) }}</dd>
            <dt class="col-4 text-secondary fw-normal">MAE</dt>
            <dd class="col-8 mb-0">
              {{ key === 'dp' ? `${fmt(item.metrics?.mae)} kPa` : formatTemp(item.metrics?.mae) }}
            </dd>
            <dt class="col-4 text-secondary fw-normal">알고리즘</dt>
            <dd class="col-8 mb-0">{{ item.algorithm }} v{{ item.version }}</dd>
            <dt class="col-4 text-secondary fw-normal">학습 표본</dt>
            <dd class="col-8 mb-0">{{ item.training_rows?.toLocaleString('ko-KR') }}</dd>
          </dl>
        </div>
      </template>

      <p v-else class="text-secondary small mb-0">분석을 실행하면 표시됩니다.</p>
    </div>
  </div>
</template>
