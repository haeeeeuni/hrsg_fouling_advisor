<script setup>
import { ref } from 'vue'

import { useToast } from '@/composables/useToast'
import { useAuthStore } from '@/stores/auth'
import { formatDateTime } from '@/utils/format'
import { ROLE } from '@/utils/constants'

const auth = useAuthStore()
const toast = useToast()

const form = ref({ currentPassword: '', newPassword: '', confirmPassword: '' })
const submitting = ref(false)
const error = ref(null)

async function onSubmit() {
  if (submitting.value) return
  error.value = null

  if (form.value.newPassword !== form.value.confirmPassword) {
    error.value = { message: '새 비밀번호가 서로 일치하지 않습니다.', details: {} }
    return
  }

  submitting.value = true
  try {
    await auth.changePassword({
      currentPassword: form.value.currentPassword,
      newPassword: form.value.newPassword,
    })
    form.value = { currentPassword: '', newPassword: '', confirmPassword: '' }
    toast.push('비밀번호가 변경되었습니다.', 'success')
  } catch (err) {
    error.value = err.parsed ?? { message: '변경에 실패했습니다.', details: {} }
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div>
    <div class="row g-4">
      <div class="col-12 col-xl-5">
        <div class="card h-100">
          <div class="card-body">
            <h2 class="h6 mb-3">계정</h2>
            <dl class="row mb-0 small">
              <dt class="col-4 text-secondary">성명</dt>
              <dd class="col-8">{{ auth.user?.full_name }}</dd>

              <dt class="col-4 text-secondary">사번</dt>
              <dd class="col-8">{{ auth.user?.employee_no }}</dd>

              <dt class="col-4 text-secondary">역할</dt>
              <dd class="col-8">{{ ROLE[auth.user?.role] ?? auth.user?.role }}</dd>

              <dt class="col-4 text-secondary">부서</dt>
              <dd class="col-8">{{ auth.user?.department || '–' }}</dd>

              <dt class="col-4 text-secondary">최근 로그인</dt>
              <dd class="col-8">{{ formatDateTime(auth.user?.last_login_at) }}</dd>
            </dl>
          </div>
        </div>
      </div>

      <div class="col-12 col-xl-7">
        <div class="card h-100">
          <div class="card-body">
            <h2 class="h6 mb-3">비밀번호 변경</h2>

            <form novalidate @submit.prevent="onSubmit">
              <div class="mb-3">
                <label for="currentPassword" class="form-label">현재 비밀번호</label>
                <input
                  id="currentPassword"
                  v-model="form.currentPassword"
                  type="password"
                  class="form-control"
                  autocomplete="current-password"
                  required
                />
              </div>

              <div class="mb-3">
                <label for="newPassword" class="form-label">새 비밀번호</label>
                <input
                  id="newPassword"
                  v-model="form.newPassword"
                  type="password"
                  class="form-control"
                  autocomplete="new-password"
                  required
                />
                <div class="form-text">최소 4자 이상. 8자 이상을 권장합니다.</div>
              </div>

              <div class="mb-3">
                <label for="confirmPassword" class="form-label">새 비밀번호 확인</label>
                <input
                  id="confirmPassword"
                  v-model="form.confirmPassword"
                  type="password"
                  class="form-control"
                  autocomplete="new-password"
                  required
                />
              </div>

              <div v-if="error" class="alert alert-danger py-2 small" role="alert">
                {{ error.message }}
                <ul v-if="error.details?.new_password" class="mb-0 mt-1 ps-3">
                  <li v-for="msg in error.details.new_password" :key="msg">{{ msg }}</li>
                </ul>
              </div>

              <button class="btn btn-primary" type="submit" :disabled="submitting">
                <span v-if="submitting" class="spinner-border spinner-border-sm me-2"></span>
                변경
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
