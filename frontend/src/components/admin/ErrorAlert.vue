<script setup>
/** 서버 공통 에러(message + 필드·행별 details)를 그대로 보여 준다. */
defineProps({
  error: { type: Object, default: null },
})
</script>

<template>
  <div v-if="error" class="alert alert-danger py-2 small" role="alert">
    {{ error.message }}
    <ul v-if="Object.keys(error.details ?? {}).length" class="mb-0 mt-1 ps-3">
      <li v-for="(messages, field) in error.details" :key="field">
        <strong>{{ field }}</strong>: {{ [].concat(messages).join(' ') }}
      </li>
    </ul>
  </div>
</template>
