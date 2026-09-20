<script setup>
import { reactive, watch } from 'vue'

const props = defineProps({
  user: { type: Object, default: null },
  error: { type: Object, default: null },
})
const emit = defineEmits(['save', 'cancel'])

const blank = {
  employee_no: '',
  full_name: '',
  role: 'USER',
  department: '',
  phone: '',
  email: '',
  is_active: true,
  initial_password: '',
}
const form = reactive({ ...blank })

watch(
  () => props.user,
  (user) => Object.assign(form, user ? { ...blank, ...user } : blank),
  { immediate: true },
)

const isNew = () => !props.user?.id

function submit() {
  const payload = { ...form }
  if (!isNew()) {
    delete payload.initial_password
    delete payload.employee_no
  }
  emit('save', payload)
}
</script>

<template>
  <div class="card mt-3">
    <div class="card-body">
      <h3 class="h6 mb-3">{{ isNew() ? '사용자 추가' : '사용자 수정' }}</h3>

      <div class="row g-3">
        <div class="col-6 col-lg-3">
          <label for="uEmpNo" class="form-label">사번</label>
          <input id="uEmpNo" v-model.trim="form.employee_no" class="form-control"
                 :disabled="!isNew()" />
          <div v-if="!isNew()" class="form-text">사번은 변경할 수 없습니다.</div>
        </div>
        <div class="col-6 col-lg-3">
          <label for="uName" class="form-label">성명</label>
          <input id="uName" v-model.trim="form.full_name" class="form-control" />
        </div>
        <div class="col-6 col-lg-3">
          <label for="uRole" class="form-label">역할</label>
          <select id="uRole" v-model="form.role" class="form-select">
            <option value="USER">일반 사용자</option>
            <option value="ADMIN">관리자</option>
          </select>
        </div>
        <div class="col-6 col-lg-3">
          <label for="uDept" class="form-label">부서</label>
          <input id="uDept" v-model.trim="form.department" class="form-control" />
        </div>
        <div class="col-6 col-lg-3">
          <label for="uPhone" class="form-label">연락처</label>
          <input id="uPhone" v-model.trim="form.phone" class="form-control" />
        </div>
        <div v-if="isNew()" class="col-6 col-lg-3">
          <label for="uPw" class="form-label">초기 비밀번호</label>
          <input id="uPw" v-model="form.initial_password" type="password" class="form-control" />
          <div class="form-text">최소 4자. 첫 로그인 시 변경을 요구합니다.</div>
        </div>
        <div class="col-6 col-lg-3 d-flex align-items-end">
          <div class="form-check">
            <input id="uActive" v-model="form.is_active" class="form-check-input" type="checkbox" />
            <label for="uActive" class="form-check-label">사용</label>
          </div>
        </div>
      </div>

      <div v-if="error" class="alert alert-danger py-2 small mt-3" role="alert">
        {{ error.message }}
        <ul v-if="error.details" class="mb-0 mt-1 ps-3">
          <li v-for="(messages, field) in error.details" :key="field">
            {{ field }}: {{ Array.isArray(messages) ? messages.join(', ') : messages }}
          </li>
        </ul>
      </div>

      <div class="mt-3">
        <button class="btn btn-primary me-2" @click="submit">저장</button>
        <button class="btn btn-outline-secondary" @click="emit('cancel')">취소</button>
      </div>
    </div>
  </div>
</template>
