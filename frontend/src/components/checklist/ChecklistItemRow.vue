<script setup>
/** 체크리스트 항목 한 줄 — 받음/미수신/해당 없음 + 메모 (specs/07 CHK-3). */
import { ref, watch } from 'vue'

const props = defineProps({
  item: { type: Object, required: true },
  busy: { type: Boolean, default: false },
})
const emit = defineEmits(['change'])

const STATES = [
  { value: 'RECEIVED', label: '받음', icon: 'bi-check-circle-fill', variant: 'success' },
  { value: 'PENDING', label: '미수신', icon: 'bi-hourglass', variant: 'secondary' },
  { value: 'NOT_APPLICABLE', label: '해당 없음', icon: 'bi-dash-circle', variant: 'secondary' },
]

const memo = ref(props.item.memo)
watch(() => props.item.memo, (value) => (memo.value = value))

function saveMemo() {
  if (memo.value !== props.item.memo) emit('change', { memo: memo.value })
}
</script>

<template>
  <li class="ui-check-row" :data-state="item.state">
    <div class="ui-check-main">
      <p class="mb-0 fw-semibold">
        {{ item.name_ko }}
        <span v-if="item.unit" class="text-secondary fw-normal">({{ item.unit }})</span>
        <span v-if="item.is_required" class="badge text-bg-light ms-1">필수</span>
        <span v-if="item.is_calculator_input" class="badge text-bg-info ms-1" title="계산기에 넣는 값입니다">
          <i class="bi bi-calculator me-1" aria-hidden="true"></i>계산기 입력
        </span>
      </p>
      <p class="small text-secondary mb-1">{{ item.name_en }}<template v-if="item.why_needed_ko"> · {{ item.why_needed_ko }}</template></p>
      <input
        v-model="memo"
        class="form-control form-control-sm ui-check-memo"
        :aria-label="`${item.name_ko} 메모`"
        placeholder="메모 (예: 10/15 회신 예정)"
        maxlength="500"
        @change="saveMemo"
      />
    </div>
    <div class="btn-group btn-group-sm ui-check-states" role="radiogroup" :aria-label="`${item.name_ko} 수신 상태`">
      <button
        v-for="state in STATES"
        :key="state.value"
        type="button"
        role="radio"
        class="btn"
        :class="item.state === state.value ? `btn-${state.variant}` : 'btn-outline-secondary'"
        :aria-checked="item.state === state.value ? 'true' : 'false'"
        :disabled="busy"
        @click="item.state !== state.value && emit('change', { state: state.value })"
      >
        <i class="bi me-1" :class="state.icon" aria-hidden="true"></i>{{ state.label }}
      </button>
    </div>
  </li>
</template>
