<script setup>
import { computed } from 'vue'

import HelpHint from '@/components/common/HelpHint.vue'

/**
 * 차압·스택온도 두 채널이 같은 이야기를 하는지 (specs/07 §8).
 *
 * 최종 FI 는 두 점수의 가중 평균이라, 둘이 얼마나 엇갈렸는지는 사라진다.
 * 그 차이가 "세정할 일인가, 정비팀을 부를 일인가" 를 가른다.
 */
const props = defineProps({
  diagnosis: { type: Object, default: null },
})

// 색만으로 구분하지 않도록 아이콘과 문구를 함께 바꾼다 (specs/16 §8).
const VERDICT = {
  CONSISTENT: {
    label: '두 신호 일치',
    variant: 'success',
    icon: 'bi-check-circle',
    text: '차압과 스택온도가 함께 올랐습니다. 가스측 오염으로 설명되는 전형적인 형태입니다.',
  },
  DP_DOMINANT: {
    label: '차압만 상승',
    variant: 'warning',
    icon: 'bi-exclamation-triangle',
    text:
      '가스측 막힘일 수 있지만, 차압 트랜스미터 드리프트나 댐퍼 고착도 같은 신호를 만듭니다. ' +
      '세정 전에 계측기 점검을 함께 검토하세요.',
  },
  ST_DOMINANT: {
    label: '스택온도만 상승',
    variant: 'warning',
    icon: 'bi-exclamation-triangle',
    text:
      '열전달 저하일 수 있지만, 급수온도·부하 패턴 변화로도 같은 신호가 납니다. ' +
      '기준 기간이 현재 운전 영역(계절·부하)을 대표하지 못할 때도 이렇게 나옵니다.',
  },
  QUIET: {
    label: '신호 미미',
    variant: 'secondary',
    icon: 'bi-dash-circle',
    text: '두 신호 모두 낮습니다. 뚜렷한 오염 징후가 없습니다.',
  },
  SATURATED: {
    label: '상한 도달 — 비교 불가',
    variant: 'secondary',
    icon: 'bi-slash-circle',
    text:
      '한쪽 신호가 상한에 고정돼 두 채널 비교가 성립하지 않습니다. 오염이 상당히 진행됐거나, ' +
      '정규화 기준(sigma_ref)이 이 호기에 비해 낮게 잡혀 있을 수 있습니다.',
  },
}

const meta = computed(() => VERDICT[props.diagnosis?.verdict] ?? null)
const pct = (v) => (v == null ? 0 : Math.max(0, Math.min(100, v)))
const satPct = (v) => Math.round((v ?? 0) * 100)
</script>

<template>
  <div class="card h-100">
    <div class="card-body">
      <h2 class="h6 mb-3 d-flex align-items-center gap-2">
        <span>신호 진단</span>
        <HelpHint label="신호 진단">
          오염이 원인이라면 <strong>차압과 스택온도가 함께 올라야 합니다</strong> — 원인이
          하나이기 때문입니다. 한쪽만 오르면 계측 이상이나 운전 변화를 의심할 근거가 됩니다.
          <br /><br />
          최종 오염도 지수는 두 점수의 가중 평균이라 이 차이가 사라집니다. 그래서 따로 보여줍니다.
          <br /><br />
          한쪽이 <strong>상한(100)에 고정</strong>되면 "얼마나 더 나쁜지"를 담지 못하므로
          우세 판정을 하지 않습니다.
        </HelpHint>
      </h2>

      <div v-if="!meta" class="text-secondary small">진단 결과가 없습니다.</div>

      <template v-else>
        <p class="mb-2">
          <span class="badge" :class="`text-bg-${meta.variant}`">
            <i class="bi me-1" :class="meta.icon" aria-hidden="true"></i>{{ meta.label }}
          </span>
        </p>

        <div class="mb-2">
          <div class="d-flex justify-content-between small">
            <span>차압</span>
            <span>
              {{ diagnosis.dp?.toFixed(1) ?? '–' }}
              <span v-if="satPct(diagnosis.dp_saturated_ratio) > 0" class="text-secondary">
                · 상한 {{ satPct(diagnosis.dp_saturated_ratio) }}%
              </span>
            </span>
          </div>
          <div class="progress" style="height: 0.5rem">
            <div class="progress-bar" :style="{ width: `${pct(diagnosis.dp)}%` }"></div>
          </div>
        </div>

        <div class="mb-3">
          <div class="d-flex justify-content-between small">
            <span>스택온도</span>
            <span>
              {{ diagnosis.st?.toFixed(1) ?? '–' }}
              <span v-if="satPct(diagnosis.st_saturated_ratio) > 0" class="text-secondary">
                · 상한 {{ satPct(diagnosis.st_saturated_ratio) }}%
              </span>
            </span>
          </div>
          <div class="progress" style="height: 0.5rem">
            <div class="progress-bar bg-secondary" :style="{ width: `${pct(diagnosis.st)}%` }"></div>
          </div>
        </div>

        <p class="small text-secondary mb-0">{{ meta.text }}</p>

        <p v-if="diagnosis.window_days" class="small text-secondary mb-0 mt-2">
          최근 {{ diagnosis.window_days }}일 평균 (현재 오염도 지수와 같은 기간)
        </p>

        <p v-if="diagnosis.weights?.dp != null" class="small text-secondary mb-0 mt-2">
          최종 지수 가중치 — 차압 {{ diagnosis.weights.dp }} · 스택온도
          {{ diagnosis.weights.stack_temp }}
        </p>
      </template>
    </div>
  </div>
</template>
