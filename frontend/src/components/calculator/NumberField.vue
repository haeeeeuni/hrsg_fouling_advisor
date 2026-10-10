<script setup>
/**
 * 숫자 입력칸 — 라벨·단위·도움말·오류 (specs/05 CALC-6).
 * 비우면 null 을 내보낸다(0 으로 바꾸지 않는다). 서버가 그 칸을 기본값(설계값 등)으로 채운다.
 */
defineProps({
  id: { type: String, required: true },
  label: { type: String, required: true },
  unit: { type: String, default: '' },
  help: { type: String, default: '' },
  error: { type: [String, Array], default: '' },
  placeholder: { type: String, default: '' },
  step: { type: String, default: 'any' },
})
const model = defineModel({ type: [Number, null], default: null })

function onInput(event) {
  const raw = event.target.value
  model.value = raw === '' ? null : Number(raw)
}
</script>

<template>
  <div class="mb-3">
    <label :for="id" class="form-label">{{ label }}</label>
    <div class="input-group">
      <input
        :id="id"
        class="form-control"
        :class="{ 'is-invalid': error }"
        type="number"
        inputmode="decimal"
        :step="step"
        :value="model ?? ''"
        :placeholder="placeholder"
        :aria-describedby="help ? `${id}Help` : undefined"
        @input="onInput"
      />
      <span v-if="unit" class="input-group-text">{{ unit }}</span>
      <div v-if="error" class="invalid-feedback">{{ [].concat(error).join(' ') }}</div>
    </div>
    <div v-if="help" :id="`${id}Help`" class="form-text">{{ help }}</div>
  </div>
</template>
