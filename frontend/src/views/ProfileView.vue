<script setup>
/** 내 정보 — 성명·소속·이메일 수정, 비밀번호 변경 (specs/01 §8, specs/10 §2). */
import { ref } from 'vue'

import { useToast } from '@/composables/useToast'
import { useAuthStore } from '@/stores/auth'
import { ROLE } from '@/utils/constants'
import { formatDateTime } from '@/utils/format'

const auth = useAuthStore()
const toast = useToast()

const profile = ref({
  fullName: auth.user?.full_name ?? '',
  organization: auth.user?.organization ?? '',
  email: auth.user?.email ?? '',
})
const profileSaving = ref(false)
const profileError = ref(null)

const form = ref({ currentPassword: '', newPassword: '', confirmPassword: '' })
const submitting = ref(false)
const error = ref(null)

async function saveProfile() {
  if (profileSaving.value) return
  profileSaving.value = true
  profileError.value = null
  try {
    await auth.updateProfile(profile.value)
    toast.push('내 정보를 저장했습니다.', 'success')
  } catch (err) {
    profileError.value = err.parsed ?? { message: '저장에 실패했습니다.', details: {} }
  } finally {
    profileSaving.value = false
  }
}

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
  <div class="ui-container">
    <h1 class="h3 mb-4">내 정보</h1>

    <div class="row g-4">
      <div class="col-12 col-xl-6">
        <div class="card h-100">
          <div class="card-body">
            <h2 class="h6 mb-3">계정</h2>
            <dl class="row small mb-3">
              <dt class="col-4 text-secondary">ID</dt>
              <dd class="col-8">{{ auth.user?.username }}</dd>
              <dt class="col-4 text-secondary">역할</dt>
              <dd class="col-8">{{ ROLE[auth.user?.role] ?? auth.user?.role }}</dd>
              <dt class="col-4 text-secondary">최근 로그인</dt>
              <dd class="col-8 mb-0">{{ formatDateTime(auth.user?.last_login_at) }}</dd>
            </dl>

            <form novalidate @submit.prevent="saveProfile">
              <div class="mb-3">
                <label for="pfName" class="form-label">성명</label>
                <input id="pfName" v-model.trim="profile.fullName" class="form-control" autocomplete="name" />
              </div>
              <div class="mb-3">
                <label for="pfOrg" class="form-label">소속</label>
                <input
                  id="pfOrg"
                  v-model.trim="profile.organization"
                  class="form-control"
                  autocomplete="organization"
                />
              </div>
              <div class="mb-3">
                <label for="pfEmail" class="form-label">이메일</label>
                <input id="pfEmail" v-model.trim="profile.email" type="email" class="form-control" autocomplete="email" />
              </div>

              <div v-if="profileError" class="alert alert-danger py-2 small" role="alert">
                {{ profileError.message }}
                <ul v-if="Object.keys(profileError.details ?? {}).length" class="mb-0 mt-1 ps-3">
                  <li v-for="(messages, field) in profileError.details" :key="field">
                    {{ [].concat(messages).join(' ') }}
                  </li>
                </ul>
              </div>

              <button class="btn btn-primary" type="submit" :disabled="profileSaving">
                <span v-if="profileSaving" class="spinner-border spinner-border-sm me-2" aria-hidden="true"></span>
                저장
              </button>
            </form>
          </div>
        </div>
      </div>

      <div class="col-12 col-xl-6">
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
                  aria-describedby="newPasswordHelp"
                  required
                />
                <div id="newPasswordHelp" class="form-text">8자 이상, 숫자만으로는 만들 수 없습니다.</div>
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
                <span v-if="submitting" class="spinner-border spinner-border-sm me-2" aria-hidden="true"></span>
                변경
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
