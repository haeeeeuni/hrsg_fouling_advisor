<script setup>
import { computed, ref, watch } from 'vue'

const props = defineProps({
  row: { type: Object, required: true },
  modelValue: { type: [String, Number, Boolean, Object, Array], default: null },
})
const emit = defineEmits(['update:modelValue'])

const local = ref(props.modelValue)
watch(() => props.modelValue, (v) => (local.value = v))

const isJson = computed(() => props.row.value_type === 'JSON')
const isBool = computed(() => props.row.value_type === 'BOOL')
const isNumber = computed(() => ['INT', 'FLOAT'].includes(props.row.value_type))
const jsonText = ref(JSON.stringify(props.modelValue ?? null, null, 0))
const jsonError = ref(null)

watch(() => props.modelValue, (v) => {
  if (isJson.value) jsonText.value = JSON.stringify(v ?? null)
})

function emitValue(value) {
  local.value = value
  emit('update:modelValue', value)
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

const isModified = computed(() => JSON.stringify(local.value) !== JSON.stringify(props.row.default))
</script>

<template>
  <div class="row g-2 align-items-start py-2 border-bottom">
    <div class="col-12 col-lg-5">
      <label :for="`set-${row.key}`" class="form-label small mb-0 fw-semibold">
        {{ row.label }}
        <span v-if="row.unit_label" class="text-secondary fw-normal">({{ row.unit_label }})</span>
        <span v-if="isModified" class="badge text-bg-warning ms-1">변경됨</span>
      </label>
      <div class="small text-secondary">
        <code>{{ row.key }}</code>
        <span v-if="row.description"> — {{ row.description }}</span>
      </div>
    </div>

    <div class="col-8 col-lg-4">
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
        v-else-if="isJson"
        :id="`set-${row.key}`"
        class="form-control form-control-sm font-monospace"
        rows="2"
        :value="jsonText"
        @input="onJsonInput($event.target.value)"
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
        @input="emitValue(Number($event.target.value))"
      />
      <input
        v-else
        :id="`set-${row.key}`"
        class="form-control form-control-sm"
        :value="local"
        @input="emitValue($event.target.value)"
      />
      <div v-if="jsonError" class="form-text text-danger">{{ jsonError }}</div>
      <div v-else-if="row.min_value !== null || row.max_value !== null" class="form-text">
        허용 범위 {{ row.min_value ?? '–' }} ~ {{ row.max_value ?? '–' }}
      </div>
    </div>

    <div class="col-4 col-lg-3 small text-secondary">
      기본값 <code>{{ JSON.stringify(row.default) }}</code>
    </div>
  </div>
</template>
