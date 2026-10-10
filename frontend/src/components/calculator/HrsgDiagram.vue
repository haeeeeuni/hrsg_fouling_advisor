<script setup>
/**
 * HRSG 도식 (specs/05 CALC-5). 가스 흐름: GT 배기 → 과열기 → 증발기 → 절탄기 → 굴뚝.
 * 색은 CSS 변수를 따라 라이트/다크에 맞는다(specs/12 §2.1). 같은 정보를 목록 글자로도 둔다.
 */
import { computed, useId } from 'vue'

const props = defineProps({
  exhaustTempC: { type: Number, default: null },
  stackTempC: { type: Number, default: null },
  stackLevel: { type: String, default: 'NORMAL' },
  exhaustLevel: { type: String, default: 'NORMAL' },
  /** 핀치 탭에서 — { evaporator_outlet_gas_temp_c, economizer_outlet_water_temp_c, pinch_c, approach_c, pinch_level, approach_level } */
  stage: { type: Object, default: null },
})

const fmt = (v) => (v === null || v === undefined ? '–' : `${Number(v).toFixed(1)} ℃`)

const boxes = computed(() => [
  { key: 'gt', title: 'GT 배기', value: fmt(props.exhaustTempC), level: props.exhaustLevel },
  { key: 'sh', title: '과열기', value: '', level: 'NORMAL' },
  {
    key: 'eva',
    title: '증발기',
    value: props.stage ? `출구 가스 ${fmt(props.stage.evaporator_outlet_gas_temp_c)}` : '',
    level: props.stage?.pinch_level ?? 'NORMAL',
  },
  {
    key: 'eco',
    title: '절탄기',
    value: props.stage ? `출구 급수 ${fmt(props.stage.economizer_outlet_water_temp_c)}` : '',
    level: props.stage?.approach_level ?? 'NORMAL',
  },
  { key: 'stack', title: '굴뚝', value: fmt(props.stackTempC), level: props.stackLevel },
])

// 압력단마다 도식이 여러 개 그려지므로 SVG 안의 id 를 고유하게 만든다.
const uid = useId()

const BOX_W = 108
const GAP = 22
const X = (i) => 6 + i * (BOX_W + GAP)
const WIDTH = X(5) - GAP + 6
</script>

<template>
  <!-- 좁은 화면에서 글자가 읽히도록 도식만 가로로 스크롤한다(페이지 전체는 스크롤하지 않는다). -->
  <figure class="mb-0 ui-hrsg-scroll" tabindex="0" aria-label="HRSG 도식 (좌우로 밀어 볼 수 있음)">
    <svg :viewBox="`0 0 ${WIDTH} 112`" class="ui-hrsg-svg" role="img" :aria-labelledby="`${uid}-desc`">
      <desc :id="`${uid}-desc`">
        HRSG 가스 흐름 도식: {{ boxes.map((b) => `${b.title} ${b.value}`).join(', ') }}
        <template v-if="stage">, 핀치 {{ fmt(stage.pinch_c) }}, 어프로치 {{ fmt(stage.approach_c) }}</template>
      </desc>
      <defs>
        <marker :id="`${uid}-arrow`" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto">
          <path d="M 0 0 L 10 5 L 0 10 z" class="ui-hrsg-arrowhead" />
        </marker>
      </defs>
      <g v-for="(box, index) in boxes" :key="box.key">
        <rect :x="X(index)" y="14" :width="BOX_W" height="60" rx="8" class="ui-hrsg-box" :data-level="box.level" />
        <text :x="X(index) + BOX_W / 2" y="38" text-anchor="middle" class="ui-hrsg-title">{{ box.title }}</text>
        <text :x="X(index) + BOX_W / 2" y="58" text-anchor="middle" class="ui-hrsg-value">{{ box.value }}</text>
        <line
          v-if="index < boxes.length - 1"
          :x1="X(index) + BOX_W + 2"
          y1="44"
          :x2="X(index + 1) - 2"
          y2="44"
          class="ui-hrsg-flow"
          :marker-end="`url(#${uid}-arrow)`"
        />
      </g>
      <template v-if="stage">
        <text :x="X(2) + BOX_W / 2" y="96" text-anchor="middle" class="ui-hrsg-note">핀치 {{ fmt(stage.pinch_c) }}</text>
        <text :x="X(3) + BOX_W / 2" y="96" text-anchor="middle" class="ui-hrsg-note">
          어프로치 {{ fmt(stage.approach_c) }}
        </text>
      </template>
      <text v-else :x="WIDTH / 2" y="100" text-anchor="middle" class="ui-hrsg-note">배기가스 흐름 →</text>
    </svg>
  </figure>
</template>
