<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const form = ref({ fullName: '', employeeNo: '', password: '' })
const submitting = ref(false)
const error = ref(null)

async function onSubmit() {
  if (submitting.value) return // 중복 클릭 방지 (specs/16 §6)
  submitting.value = true
  error.value = null
  try {
    await auth.login(form.value)
    // 원래 가려던 경로로 복귀한다 (AC-16-1).
    const redirect = route.query.redirect
    await router.replace(typeof redirect === 'string' ? redirect : { name: 'dashboard' })
  } catch (err) {
    error.value = err.parsed ?? { message: '로그인에 실패했습니다.', details: {} }
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="spark-auth">
    <div class="card">
      <div class="card-body p-4">
        <h1 class="h5 mb-1">HRSG 오염도 진단</h1>
        <p class="text-secondary small mb-4">사내 담당자 전용 시스템입니다.</p>

        <form novalidate @submit.prevent="onSubmit">
          <div class="mb-3">
            <label for="fullName" class="form-label">성명</label>
            <input
              id="fullName"
              v-model.trim="form.fullName"
              type="text"
              class="form-control"
              autocomplete="name"
              required
            />
          </div>

          <div class="mb-3">
            <label for="employeeNo" class="form-label">사번</label>
            <input
              id="employeeNo"
              v-model.trim="form.employeeNo"
              type="text"
              class="form-control"
              autocomplete="username"
              required
            />
          </div>

          <div class="mb-3">
            <label for="password" class="form-label">비밀번호</label>
            <input
              id="password"
              v-model="form.password"
              type="password"
              class="form-control"
              autocomplete="current-password"
              required
            />
          </div>

          <div v-if="error" class="alert alert-danger py-2 small" role="alert">
            {{ error.message }}
            <div v-if="error.details?.retry_after_sec" class="mt-1">
              {{ Math.ceil(error.details.retry_after_sec / 60) }}분 후 다시 시도할 수 있습니다.
            </div>
          </div>

          <button class="btn btn-primary w-100" type="submit" :disabled="submitting">
            <span v-if="submitting" class="spinner-border spinner-border-sm me-2"></span>
            로그인
          </button>
        </form>
      </div>
    </div>
  </div>
</template>
