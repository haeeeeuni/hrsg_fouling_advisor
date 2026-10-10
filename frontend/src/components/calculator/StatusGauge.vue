<script setup>
/**
 * 운전 상태 게이지 (specs/05 CALC-5). 반원 눈금: 정상(경보 전) · 경보 구간 · 트립 구간.
 * 한계값 원본은 받지 않는다 — 서버가 준 '경보 대비 %'·'트립 대비 %' 로 위치만 그린다.
 * 같은 정보를 글자로도 둔다(스크린리더·색각 이상, specs/12 §4).
 */
import { computed } from 'vue'

import StatusBadge from '@/components/common/StatusBadge.vue'

const props = defineProps({
  variable: { type: Object, required: true },
})

const STATE_LABEL = { NORMAL: '정상', ALARM: '주의 — 경보 구간', TRIP: '위험 — 트립 구간' }
// 눈금 끝 = 트립 위치보다 조금 더. 경보 위치를 100 으로 둔 상대 눈금이다.
const SCALE_HEADROOM = 1.15

const geometry = computed(() => {
  const toAlarm = props.variable.ratio_to_alarm_pct
  const toTrip = props.variable.ratio_to_trip_pct
  const tripAt = toTrip > 0 ? (toAlarm / toTrip) * 100 : 120 // 경보=100 기준 트립 위치
  const max = tripAt * SCALE_HEADROOM
  const clamp = (v) => Math.max(0, Math.min(1, v / max))
  return { alarm: clamp(100), trip: clamp(tripAt), needle: clamp(toAlarm) }
})

// 반원: 왼쪽(0) → 오른쪽(1). 중심 (60, 60), 반지름 48
function point(fraction, radius = 48) {
  const angle = Math.PI * (1 - fraction)
  return [60 + radius * Math.cos(angle), 60 - radius * Math.sin(angle)]
}

function arc(from, to) {
  const [x1, y1] = point(from)
  const [x2, y2] = point(to)
  return `M ${x1.toFixed(2)} ${y1.toFixed(2)} A 48 48 0 0 1 ${x2.toFixed(2)} ${y2.toFixed(2)}`
}

const needleEnd = computed(() => point(geometry.value.needle, 40))
const description = computed(
  () =>
    `${props.variable.label} ${props.variable.value} ${props.variable.unit}, ` +
    `경보 한계 대비 ${props.variable.ratio_to_alarm_pct}%, ${STATE_LABEL[props.variable.state]}`,
)
</script>

<template>
  <figure class="ui-gauge mb-0" :aria-label="description" role="img">
    <svg viewBox="0 0 120 70" class="ui-gauge-svg" aria-hidden="true">
      <path :d="arc(0, geometry.alarm)" class="ui-gauge-arc ui-gauge-arc--normal" />
      <path :d="arc(geometry.alarm, geometry.trip)" class="ui-gauge-arc ui-gauge-arc--caution" />
      <path :d="arc(geometry.trip, 1)" class="ui-gauge-arc ui-gauge-arc--danger" />
      <line x1="60" y1="60" :x2="needleEnd[0]" :y2="needleEnd[1]" class="ui-gauge-needle" />
      <circle cx="60" cy="60" r="3.5" class="ui-gauge-hub" />
    </svg>
    <figcaption class="text-center">
      <div class="small text-secondary">{{ variable.label }}</div>
      <div class="fs-4 fw-bold lh-sm">
        {{ variable.value }}<span class="fs-6 fw-normal ms-1">{{ variable.unit }}</span>
      </div>
      <div class="small text-secondary mb-1">경보 한계 대비 {{ variable.ratio_to_alarm_pct }}%</div>
      <StatusBadge :level="variable.level" :label="STATE_LABEL[variable.state]" />
    </figcaption>
  </figure>
</template>
