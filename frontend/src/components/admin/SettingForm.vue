<script setup>
/** 설정 항목 한 줄 — 타입에 맞는 입력, 허용 범위, 기본값, 되돌리기 (specs/08 ADM-4). */
import { computed, ref, watch } from 'vue'

const props = defineProps({
  row: { type: Object, required: true },
  modelValue: { type: [String, Number, Boolean, Object, Array], default: null },
})
const emit = defineEmits(['update:modelValue', 'reset'])

const local = ref(props.modelValue)
watch(() => props.modelValue, (v) => (local.value = v))

const isJson = computed(() => props.row.value_type === 'JSON')
const isBool = computed(() => props.row.value_type === 'BOOL')
const isText = computed(() => props.row.value_type === 'TEXT')
const isNumber = computed(() => ['INT', 'FLOAT'].includes(props.row.value_type))
const jsonText = ref(JSON.stringify(props.modelValue ?? null))
const jsonError = ref(null)

watch(() => props.modelValue, (v) => {
  if (isJson.value) jsonText.value = JSON.stringify(v ?? null)
})

function emitValue(value) {
  local.value = value
  emit('update:modelValue', value)
}

function onNumberInput(raw) {
  // 빈칸을 0 으로 바꾸지 않는다 — 서버가 형식 오류로 알려 준다.
  emitValue(raw === '' ? raw : Number(raw))
}

function onJsonInput(text) {
  jsonText.value = text
  try {
    emitValue(JSON.parse(text))
    jsonError.value = null
  } catch {
    jsonError.value = 'JSON 형식이 올바르지 않습니다.'
  }
}

const hasRange = computed(() => props.row.min_value !== null || props.row.max_value !== null)
</script>

<template>
  <div class="row g-2 align-items-start py-3 border-bottom">
    <div class="col-12 col-lg-5">
      <label :for="`set-${row.key}`" class="form-label small mb-0 fw-semibold">
        {{ row.label }}
        <span v-if="row.unit_label" class="text-secondary fw-normal">({{ row.unit_label }})</span>
        <span v-if="row.is_modified" class="badge text-bg-warning ms-1">기본값과 다름</span>
      </label>
      <div class="small text-secondary">
        <code>{{ row.key }}</code>
        <span v-if="row.description"> — {{ row.description }}</span>
      </div>
    </div>

    <div class="col-12 col-sm-8 col-lg-4">
      <div v-if="isBool" class="form-check form-switch">
        <input
          :id="`set-${row.key}`"
          class="form-check-input"
          type="checkbox"
          :checked="local"
          @change="emitValue($event.target.checked)"
        />
      </div>
      <textarea
        v-else-if="isJson || isText"
        :id="`set-${row.key}`"
        class="form-control form-control-sm"
        :class="{ 'font-monospace': isJson }"
        :rows="isText ? 6 : 2"
        :value="isJson ? jsonText : local"
        @input="isJson ? onJsonInput($event.target.value) : emitValue($event.target.value)"
      ></textarea>
      <input
        v-else-if="isNumber"
        :id="`set-${row.key}`"
        class="form-control form-control-sm"
        type="number"
        :step="row.value_type === 'INT' ? 1 : 'any'"
        :min="row.min_value ?? undefined"
        :max="row.max_value ?? undefined"
        :value="local"
        @input="onNumberInput($event.target.value)"
      />
      <input
        v-else
        :id="`set-${row.key}`"
        class="form-control form-control-sm"
        :value="local"
        @input="emitValue($event.target.value)"
      />
      <div v-if="jsonError" class="form-text text-danger">{{ jsonError }}</div>
      <div v-else-if="hasRange" class="form-text">
        허용 범위 {{ row.min_value ?? '–' }} ~ {{ row.max_value ?? '–' }}
      </div>
    </div>

    <div class="col-12 col-sm-4 col-lg-3 small text-secondary">
      <div>기본값 <code>{{ isText ? '(긴 문안)' : JSON.stringify(row.default) }}</code></div>
      <button
        v-if="row.is_modified"
        type="button"
        class="btn btn-link btn-sm p-0"
        @click="emit('reset')"
      >
        기본값으로 되돌리기
      </button>
    </div>
  </div>
</template>
