<script setup>
import SettingsView from '@/views/admin/SettingsView.vue'
</script>

<template>
  <div>
    <div class="alert alert-warning py-2 small" role="note">
      편익 계수의 기본값은 <strong>참고치</strong>입니다. 실적 데이터에 맞춰 보정해야
      순편익·회수기간 수치가 의미를 갖습니다 (specs/09 §3.1).
    </div>
    <SettingsView category="BENEFIT" />
  </div>
</template>
