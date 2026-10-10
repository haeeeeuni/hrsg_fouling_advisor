<script setup>
/** 회원가입 (specs/01 AUTH-1 ~ AUTH-3). 가입 후에는 관리자 승인을 기다린다 — 자동 로그인하지 않는다. */
import { computed, ref } from 'vue'

import { checkUsername } from '@/api/auth'
import { useAuthStore } from '@/stores/auth'
import { useUiStore } from '@/stores/ui'

const auth = useAuthStore()
const ui = useUiStore()

const form = ref({
  username: '',
  password: '',
  passwordConfirm: '',
  fullName: '',
  organization: '',
  email: '',
  signupReason: '',
})
const submitting = ref(false)
const error = ref(null)
const done = ref(null)
const usernameCheck = ref(null) // { available, reason } | null
let checkSeq = 0

/** 서버 필드명 → 화면 필드 */
const FIELD_MAP = {
  username: 'username',
  password: 'password',
  password_confirm: 'passwordConfirm',
  full_name: 'fullName',
  organization: 'organization',
  email: 'email',
  signup_reason: 'signupReason',
}

const fieldErrors = computed(() => {
  const details = error.value?.details ?? {}
  return Object.fromEntries(
    Object.entries(details)
      .filter(([key]) => FIELD_MAP[key])
      .map(([key, messages]) => [FIELD_MAP[key], [].concat(messages)]),
  )
})

const passwordMismatch = computed(
  () => form.value.passwordConfirm !== '' && form.value.password !== form.value.passwordConfirm,
)

async function onUsernameBlur() {
  const username = form.value.username.trim()
  if (!username) {
    usernameCheck.value = null
    return
  }
  // 늦게 도착한 응답이 최신 입력의 결과를 덮지 않게 한다.
  const seq = ++checkSeq
  try {
    const { data } = await checkUsername(username)
    if (seq === checkSeq) usernameCheck.value = data
  } catch {
    if (seq === checkSeq) usernameCheck.value = null
  }
}

async function onSubmit() {
  if (submitting.value || passwordMismatch.value) return
  submitting.value = true
  error.value = null
  try {
    done.value = await auth.signup(form.value)
  } catch (err) {
    error.value = err.parsed ?? { message: '가입 신청에 실패했습니다.', details: {} }
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="ui-container ui-narrow">
    <div v-if="done" class="card">
      <div class="card-body text-center py-5">
        <i class="bi bi-hourglass-split ui-feature-icon" aria-hidden="true"></i>
        <h1 class="h4 mt-3">가입 신청이 접수되었습니다</h1>
        <p class="mb-1">
          ID <strong>{{ done.username }}</strong> 은(는) 관리자 승인 대기 중입니다.
        </p>
        <p class="text-secondary">승인되면 화면 오른쪽 위에서 로그인할 수 있습니다.</p>
        <RouterLink class="btn btn-outline-secondary" :to="{ name: 'intro' }">소개 화면으로</RouterLink>
      </div>
    </div>

    <div v-else class="card">
      <div class="card-body p-4">
        <h1 class="h4 mb-1">회원가입</h1>
        <p class="text-secondary small mb-4">
          가입 신청 후 관리자가 승인해야 로그인할 수 있습니다. <span class="text-danger" aria-hidden="true">*</span> 는 필수 항목입니다.
        </p>

        <form novalidate @submit.prevent="onSubmit">
          <div class="mb-3">
            <label for="suUsername" class="form-label">ID <span class="text-danger" aria-hidden="true">*</span></label>
            <input
              id="suUsername"
              v-model.trim="form.username"
              type="text"
              class="form-control"
              :class="{
                'is-invalid': fieldErrors.username || usernameCheck?.available === false,
                'is-valid': usernameCheck?.available === true && !fieldErrors.username,
              }"
              autocomplete="username"
              autocapitalize="off"
              spellcheck="false"
              aria-describedby="suUsernameHelp"
              required
              @blur="onUsernameBlur"
              @input="usernameCheck = null"
            />
            <div id="suUsernameHelp" class="form-text">
              영문 소문자·숫자·마침표(.)·밑줄(_)·하이픈(-) 4~30자. 대문자는 소문자로 저장됩니다.
            </div>
            <div v-if="fieldErrors.username" class="invalid-feedback">
              {{ fieldErrors.username.join(' ') }}
            </div>
            <div v-else-if="usernameCheck?.available === false" class="invalid-feedback">
              {{ usernameCheck.reason }}
            </div>
            <div v-else-if="usernameCheck?.available" class="valid-feedback">사용할 수 있는 ID 입니다.</div>
          </div>

          <div class="row g-3 mb-3">
            <div class="col-12 col-md-6">
              <label for="suPassword" class="form-label">비밀번호 <span class="text-danger" aria-hidden="true">*</span></label>
              <input
                id="suPassword"
                v-model="form.password"
                type="password"
                class="form-control"
                :class="{ 'is-invalid': fieldErrors.password }"
                autocomplete="new-password"
                aria-describedby="suPasswordHelp"
                required
              />
              <div id="suPasswordHelp" class="form-text">8자 이상, 숫자만으로는 만들 수 없습니다.</div>
              <div v-if="fieldErrors.password" class="invalid-feedback">
                {{ fieldErrors.password.join(' ') }}
              </div>
            </div>
            <div class="col-12 col-md-6">
              <label for="suPasswordConfirm" class="form-label">
                비밀번호 확인 <span class="text-danger" aria-hidden="true">*</span>
              </label>
              <input
                id="suPasswordConfirm"
                v-model="form.passwordConfirm"
                type="password"
                class="form-control"
                :class="{ 'is-invalid': passwordMismatch || fieldErrors.passwordConfirm }"
                autocomplete="new-password"
                required
              />
              <div v-if="passwordMismatch" class="invalid-feedback">비밀번호가 일치하지 않습니다.</div>
              <div v-else-if="fieldErrors.passwordConfirm" class="invalid-feedback">
                {{ fieldErrors.passwordConfirm.join(' ') }}
              </div>
            </div>
          </div>

          <div class="row g-3 mb-3">
            <div class="col-12 col-md-6">
              <label for="suFullName" class="form-label">성명 <span class="text-danger" aria-hidden="true">*</span></label>
              <input
                id="suFullName"
                v-model.trim="form.fullName"
                type="text"
                class="form-control"
                :class="{ 'is-invalid': fieldErrors.fullName }"
                autocomplete="name"
                required
              />
              <div v-if="fieldErrors.fullName" class="invalid-feedback">{{ fieldErrors.fullName.join(' ') }}</div>
            </div>
            <div class="col-12 col-md-6">
              <label for="suOrganization" class="form-label">소속 <span class="text-danger" aria-hidden="true">*</span></label>
              <input
                id="suOrganization"
                v-model.trim="form.organization"
                type="text"
                class="form-control"
                :class="{ 'is-invalid': fieldErrors.organization }"
                autocomplete="organization"
                placeholder="회사·부서"
                required
              />
              <div v-if="fieldErrors.organization" class="invalid-feedback">
                {{ fieldErrors.organization.join(' ') }}
              </div>
            </div>
          </div>

          <div class="mb-3">
            <label for="suEmail" class="form-label">이메일 <span class="text-secondary small">(선택)</span></label>
            <input
              id="suEmail"
              v-model.trim="form.email"
              type="email"
              class="form-control"
              :class="{ 'is-invalid': fieldErrors.email }"
              autocomplete="email"
            />
            <div v-if="fieldErrors.email" class="invalid-feedback">{{ fieldErrors.email.join(' ') }}</div>
          </div>

          <div class="mb-4">
            <label for="suReason" class="form-label">
              가입 사유 <span class="text-secondary small">(선택)</span>
            </label>
            <textarea
              id="suReason"
              v-model.trim="form.signupReason"
              class="form-control"
              rows="2"
              maxlength="500"
              placeholder="관리자가 승인 여부를 판단하는 데 참고합니다."
            ></textarea>
          </div>

          <div
            v-if="error && !Object.keys(fieldErrors).length"
            class="alert alert-danger py-2 small"
            role="alert"
          >
            {{ error.message }}
          </div>

          <div class="d-flex flex-wrap align-items-center gap-3">
            <button class="btn btn-primary" type="submit" :disabled="submitting || passwordMismatch">
              <span v-if="submitting" class="spinner-border spinner-border-sm me-2" aria-hidden="true"></span>
              가입 신청
            </button>
            <span class="small text-secondary">
              이미 계정이 있나요?
              <button type="button" class="btn btn-link btn-sm p-0 align-baseline" @click.stop="ui.openLogin()">
                로그인
              </button>
            </span>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>
