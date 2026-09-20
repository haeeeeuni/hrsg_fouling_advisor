<script setup>
import { onMounted, ref } from 'vue'

import * as api from '@/api/users'
import UserForm from '@/components/admin/UserForm.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import { useToast } from '@/composables/useToast'
import { formatDateTime } from '@/utils/format'

const toast = useToast()

const users = ref([])
const histories = ref([])
const editing = ref(null)
const error = ref(null)
const filters = ref({ search: '', role: '', is_active: '' })
const tab = ref('USERS')

onMounted(load)

async function load() {
  const params = Object.fromEntries(Object.entries(filters.value).filter(([, v]) => v !== ''))
  const { data } = await api.fetchUsers({ ...params, page_size: 100 })
  users.value = data.results ?? data
}

async function loadHistories() {
  const { data } = await api.fetchLoginHistories({ page_size: 100 })
  histories.value = data.results ?? data
}

function startCreate() {
  editing.value = {}
  error.value = null
}

function startEdit(user) {
  editing.value = user
  error.value = null
}

async function save(payload) {
  error.value = null
  try {
    if (editing.value?.id) await api.updateUser(editing.value.id, payload)
    else await api.createUser(payload)
    editing.value = null
    await load()
    toast.push('저장했습니다.', 'success')
  } catch (err) {
    error.value = err.parsed
  }
}

async function remove(user, hard = false) {
  const message = hard
    ? `사용자 "${user.full_name}(${user.employee_no})" 을(를) 완전히 삭제할까요?\n분석 이력이 있으면 삭제할 수 없습니다.`
    : `사용자 "${user.full_name}(${user.employee_no})" 을(를) 비활성화할까요?`
  if (!window.confirm(message)) return
  try {
    await api.deleteUser(user.id, hard)
    await load()
    toast.push(hard ? '삭제했습니다.' : '비활성화했습니다.', 'success')
  } catch (err) {
    toast.push(err.parsed?.message ?? '처리할 수 없습니다.', 'danger')
  }
}

async function reset(user) {
  const password = window.prompt(`"${user.full_name}" 의 새 비밀번호를 입력하세요 (최소 4자)`)
  if (!password) return
  try {
    await api.resetPassword(user.id, password)
    toast.push('비밀번호를 초기화했습니다. 첫 로그인 시 변경을 요구합니다.', 'success')
    await load()
  } catch (err) {
    toast.push(err.parsed?.message ?? '초기화할 수 없습니다.', 'danger')
  }
}
</script>

<template>
  <div>
    <ul class="nav nav-tabs mb-3">
      <li class="nav-item">
        <button class="nav-link" :class="{ active: tab === 'USERS' }" @click="tab = 'USERS'">
          사용자
        </button>
      </li>
      <li class="nav-item">
        <button class="nav-link" :class="{ active: tab === 'HISTORY' }"
                @click="tab = 'HISTORY'; loadHistories()">
          로그인 이력
        </button>
      </li>
    </ul>

    <template v-if="tab === 'USERS'">
      <div class="row g-2 align-items-end mb-3">
        <div class="col-6 col-lg-4">
          <label for="uSearch" class="form-label small">검색 (성명/사번)</label>
          <input id="uSearch" v-model.trim="filters.search" class="form-control form-control-sm"
                 @keyup.enter="load" />
        </div>
        <div class="col-3 col-lg-2">
          <label for="uFilterRole" class="form-label small">역할</label>
          <select id="uFilterRole" v-model="filters.role" class="form-select form-select-sm"
                  @change="load">
            <option value="">전체</option>
            <option value="USER">일반 사용자</option>
            <option value="ADMIN">관리자</option>
          </select>
        </div>
        <div class="col-3 col-lg-2">
          <label for="uFilterActive" class="form-label small">사용 여부</label>
          <select id="uFilterActive" v-model="filters.is_active" class="form-select form-select-sm"
                  @change="load">
            <option value="">전체</option>
            <option value="true">사용</option>
            <option value="false">중지</option>
          </select>
        </div>
        <div class="col-12 col-lg-4 text-lg-end">
          <button class="btn btn-primary btn-sm" @click="startCreate">사용자 추가</button>
        </div>
      </div>

      <EmptyState v-if="!users.length" title="사용자가 없습니다." icon="bi-people" />

      <table v-else class="table table-sm align-middle">
        <thead>
          <tr>
            <th scope="col">사번</th>
            <th scope="col">성명</th>
            <th scope="col">부서</th>
            <th scope="col">역할</th>
            <th scope="col">사용</th>
            <th scope="col">최근 로그인</th>
            <th scope="col"></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="user in users" :key="user.id" :class="user.is_active ? '' : 'text-secondary'">
            <td class="small">{{ user.employee_no }}</td>
            <td class="small">
              {{ user.full_name }}
              <span v-if="user.must_change_password" class="badge text-bg-light ms-1">
                비밀번호 변경 필요
              </span>
            </td>
            <td class="small">{{ user.department || '–' }}</td>
            <td>
              <span class="badge" :class="user.role === 'ADMIN' ? 'text-bg-primary' : 'text-bg-light'">
                {{ user.role_label }}
              </span>
            </td>
            <td>
              <span class="badge" :class="user.is_active ? 'text-bg-secondary' : 'text-bg-light'">
                {{ user.is_active ? '사용' : '중지' }}
              </span>
            </td>
            <td class="small">{{ formatDateTime(user.last_login_at) }}</td>
            <td class="text-end">
              <button class="btn btn-sm btn-outline-secondary me-1" @click="startEdit(user)">수정</button>
              <button class="btn btn-sm btn-outline-secondary me-1" @click="reset(user)">
                비밀번호 초기화
              </button>
              <button class="btn btn-sm btn-outline-danger" @click="remove(user)">비활성화</button>
            </td>
          </tr>
        </tbody>
      </table>

      <UserForm v-if="editing" :user="editing" :error="error" @save="save" @cancel="editing = null" />
    </template>

    <template v-else>
      <EmptyState v-if="!histories.length" title="로그인 이력이 없습니다." icon="bi-clock-history" />
      <table v-else class="table table-sm align-middle">
        <thead>
          <tr>
            <th scope="col">일시</th>
            <th scope="col">입력 사번</th>
            <th scope="col">성명</th>
            <th scope="col">결과</th>
            <th scope="col">사유</th>
            <th scope="col">IP</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in histories" :key="row.id">
            <td class="small">{{ formatDateTime(row.created_at) }}</td>
            <td class="small">{{ row.attempted_employee_no }}</td>
            <td class="small">{{ row.full_name || row.full_name_input || '–' }}</td>
            <td>
              <span class="badge" :class="row.success ? 'text-bg-success' : 'text-bg-danger'">
                {{ row.success ? '성공' : '실패' }}
              </span>
            </td>
            <td class="small">{{ row.fail_reason || '–' }}</td>
            <td class="small">{{ row.ip || '–' }}</td>
          </tr>
        </tbody>
      </table>
    </template>
  </div>
</template>
