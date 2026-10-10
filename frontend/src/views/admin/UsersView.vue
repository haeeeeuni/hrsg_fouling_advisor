<script setup>
/**
 * 사용자 관리 (specs/01 AUTH-10·AUTH-11). 사용자 생성은 회원가입으로만 한다.
 * 가입 승인은 별도 메뉴(가입 승인)에서 한다.
 */
import { onMounted, ref } from 'vue'

import * as api from '@/api/users'
import EmptyState from '@/components/common/EmptyState.vue'
import { useToast } from '@/composables/useToast'
import { useAuthStore } from '@/stores/auth'
import { APPROVAL } from '@/utils/constants'
import { formatDateTime } from '@/utils/format'

const toast = useToast()
const auth = useAuthStore()

const tab = ref('USERS')
const users = ref([])
const histories = ref([])
const loadError = ref(null)
/** 첫 응답 전에는 '사용자가 없습니다' 대신 로딩을 보인다(빈 상태 깜빡임 방지). */
const loaded = ref(false)
const filters = ref({ search: '', role: '', approval_status: 'APPROVED', is_active: '' })

const editing = ref(null) // 수정 중인 사용자 id
const draft = ref({})
const saveError = ref(null)

onMounted(load)

async function load() {
  loadError.value = null
  const params = Object.fromEntries(Object.entries(filters.value).filter(([, v]) => v !== ''))
  try {
    const { data } = await api.fetchUsers({ ...params, page_size: 100 })
    users.value = data.results ?? data
  } catch (err) {
    loadError.value = err.parsed ?? { message: '목록을 불러오지 못했습니다.' }
  } finally {
    loaded.value = true
  }
}

async function loadHistories() {
  try {
    const { data } = await api.fetchLoginHistories({ page_size: 100 })
    histories.value = data.results ?? data
  } catch (err) {
    toast.push(err.parsed?.message ?? '로그인 이력을 불러오지 못했습니다.', 'danger')
  }
}

function startEdit(user) {
  editing.value = user.id
  saveError.value = null
  draft.value = {
    full_name: user.full_name,
    organization: user.organization,
    email: user.email,
    role: user.role,
    is_active: user.is_active,
  }
}

async function save(user) {
  saveError.value = null
  try {
    await api.updateUser(user.id, draft.value)
    editing.value = null
    toast.push('저장했습니다.', 'success')
    await load()
  } catch (err) {
    saveError.value = err.parsed
  }
}

async function deactivate(user) {
  if (!window.confirm(`${user.full_name}(${user.username}) 계정을 비활성화할까요?\n비활성 계정은 로그인할 수 없습니다.`)) return
  try {
    await api.deleteUser(user.id)
    toast.push('비활성화했습니다.', 'success')
    await load()
  } catch (err) {
    toast.push(err.parsed?.message ?? '처리할 수 없습니다.', 'danger')
  }
}

async function reset(user) {
  const password = window.prompt(
    `${user.full_name}(${user.username}) 의 새 비밀번호를 입력하세요.\n8자 이상, 숫자만으로는 만들 수 없습니다.`,
  )
  if (!password) return
  try {
    await api.resetPassword(user.id, password)
    toast.push('비밀번호를 초기화했습니다. 다음 로그인 때 변경을 요구합니다.', 'success')
    await load()
  } catch (err) {
    const details = Object.values(err.parsed?.details ?? {}).flat().join(' ')
    toast.push(details || err.parsed?.message || '초기화할 수 없습니다.', 'danger')
  }
}
</script>

<template>
  <div>
    <ul class="nav nav-tabs mb-3">
      <li class="nav-item">
        <button class="nav-link" :class="{ active: tab === 'USERS' }" type="button" @click="tab = 'USERS'">
          사용자
        </button>
      </li>
      <li class="nav-item">
        <button
          class="nav-link"
          :class="{ active: tab === 'HISTORY' }"
          type="button"
          @click="tab = 'HISTORY'; loadHistories()"
        >
          로그인 이력
        </button>
      </li>
    </ul>

    <template v-if="tab === 'USERS'">
      <form class="row g-2 align-items-end mb-3" @submit.prevent="load">
        <div class="col-12 col-md-4">
          <label for="uSearch" class="form-label small">검색 (ID·성명·소속)</label>
          <input id="uSearch" v-model.trim="filters.search" class="form-control form-control-sm" />
        </div>
        <div class="col-4 col-md-2">
          <label for="uApproval" class="form-label small">승인 상태</label>
          <select id="uApproval" v-model="filters.approval_status" class="form-select form-select-sm" @change="load">
            <option value="">전체</option>
            <option v-for="(meta, code) in APPROVAL" :key="code" :value="code">{{ meta.label }}</option>
          </select>
        </div>
        <div class="col-4 col-md-2">
          <label for="uRole" class="form-label small">역할</label>
          <select id="uRole" v-model="filters.role" class="form-select form-select-sm" @change="load">
            <option value="">전체</option>
            <option value="USER">일반 사용자</option>
            <option value="ADMIN">관리자</option>
          </select>
        </div>
        <div class="col-4 col-md-2">
          <label for="uActive" class="form-label small">사용 여부</label>
          <select id="uActive" v-model="filters.is_active" class="form-select form-select-sm" @change="load">
            <option value="">전체</option>
            <option value="true">사용</option>
            <option value="false">중지</option>
          </select>
        </div>
        <div class="col-12 col-md-2">
          <button class="btn btn-sm btn-outline-secondary w-100" type="submit">검색</button>
        </div>
      </form>

      <div v-if="loadError" class="alert alert-danger" role="alert">{{ loadError.message }}</div>
      <div v-else-if="!loaded" class="text-center py-4">
        <div class="spinner-border text-primary" role="status"><span class="visually-hidden">불러오는 중</span></div>
      </div>
      <EmptyState v-else-if="!users.length" title="조건에 맞는 사용자가 없습니다." icon="bi-people" />

      <div v-else class="table-responsive">
        <table class="table table-sm align-middle">
          <thead>
            <tr>
              <th scope="col">ID</th>
              <th scope="col">성명</th>
              <th scope="col">소속</th>
              <th scope="col">역할</th>
              <th scope="col">승인</th>
              <th scope="col">사용</th>
              <th scope="col">최근 로그인</th>
              <th scope="col"><span class="visually-hidden">작업</span></th>
            </tr>
          </thead>
          <tbody>
            <template v-for="user in users" :key="user.id">
              <tr :class="user.is_active ? '' : 'text-secondary'">
                <td class="small">{{ user.username }}</td>
                <td class="small">
                  {{ user.full_name }}
                  <span v-if="user.must_change_password" class="badge text-bg-light ms-1">비밀번호 변경 필요</span>
                </td>
                <td class="small">{{ user.organization }}</td>
                <td>
                  <span class="badge" :class="user.role === 'ADMIN' ? 'text-bg-primary' : 'text-bg-light'">
                    {{ user.role_label }}
                  </span>
                </td>
                <td>
                  <span class="badge" :class="`text-bg-${APPROVAL[user.approval_status]?.variant ?? 'light'}`">
                    {{ user.approval_status_label }}
                  </span>
                </td>
                <td class="small">{{ user.is_active ? '사용' : '중지' }}</td>
                <td class="small">{{ formatDateTime(user.last_login_at) }}</td>
                <td class="text-end text-nowrap">
                  <button class="btn btn-sm btn-outline-secondary me-1" type="button" @click="startEdit(user)">
                    수정
                  </button>
                  <button class="btn btn-sm btn-outline-secondary me-1" type="button" @click="reset(user)">
                    비밀번호 초기화
                  </button>
                  <button
                    v-if="user.is_active && user.id !== auth.user?.id"
                    class="btn btn-sm btn-outline-danger"
                    type="button"
                    @click="deactivate(user)"
                  >
                    비활성화
                  </button>
                </td>
              </tr>
              <tr v-if="editing === user.id">
                <td colspan="8" class="bg-body-tertiary">
                  <form class="row g-2 align-items-end py-2" novalidate @submit.prevent="save(user)">
                    <div class="col-12 col-md-3">
                      <label :for="`eName-${user.id}`" class="form-label small">성명</label>
                      <input :id="`eName-${user.id}`" v-model.trim="draft.full_name" class="form-control form-control-sm" />
                    </div>
                    <div class="col-12 col-md-3">
                      <label :for="`eOrg-${user.id}`" class="form-label small">소속</label>
                      <input :id="`eOrg-${user.id}`" v-model.trim="draft.organization" class="form-control form-control-sm" />
                    </div>
                    <div class="col-12 col-md-2">
                      <label :for="`eEmail-${user.id}`" class="form-label small">이메일</label>
                      <input :id="`eEmail-${user.id}`" v-model.trim="draft.email" type="email" class="form-control form-control-sm" />
                    </div>
                    <div class="col-6 col-md-2">
                      <label :for="`eRole-${user.id}`" class="form-label small">역할</label>
                      <select :id="`eRole-${user.id}`" v-model="draft.role" class="form-select form-select-sm">
                        <option value="USER">일반 사용자</option>
                        <option value="ADMIN">관리자</option>
                      </select>
                    </div>
                    <div class="col-6 col-md-2">
                      <div class="form-check mb-1">
                        <input :id="`eActive-${user.id}`" v-model="draft.is_active" class="form-check-input" type="checkbox" />
                        <label :for="`eActive-${user.id}`" class="form-check-label small">사용</label>
                      </div>
                    </div>
                    <div v-if="saveError" class="col-12">
                      <div class="alert alert-danger py-2 small mb-0" role="alert">
                        {{ saveError.message }}
                        <ul v-if="Object.keys(saveError.details ?? {}).length" class="mb-0 mt-1 ps-3">
                          <li v-for="(messages, field) in saveError.details" :key="field">
                            {{ [].concat(messages).join(' ') }}
                          </li>
                        </ul>
                      </div>
                    </div>
                    <div class="col-12">
                      <button class="btn btn-sm btn-primary me-2" type="submit">저장</button>
                      <button class="btn btn-sm btn-outline-secondary" type="button" @click="editing = null">
                        취소
                      </button>
                    </div>
                  </form>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>
    </template>

    <template v-else>
      <EmptyState v-if="!histories.length" title="로그인 이력이 없습니다." icon="bi-clock-history" />
      <div v-else class="table-responsive">
        <table class="table table-sm align-middle">
          <thead>
            <tr>
              <th scope="col">일시</th>
              <th scope="col">입력 ID</th>
              <th scope="col">성명</th>
              <th scope="col">결과</th>
              <th scope="col">사유</th>
              <th scope="col">IP</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in histories" :key="row.id">
              <td class="small">{{ formatDateTime(row.created_at) }}</td>
              <td class="small">{{ row.attempted_username }}</td>
              <td class="small">{{ row.full_name || '–' }}</td>
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
      </div>
    </template>
  </div>
</template>
