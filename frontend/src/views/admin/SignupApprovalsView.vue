<script setup>
/** 가입 승인 (specs/01 AUTH-4·AUTH-5). 대기 신청을 승인하거나 사유와 함께 반려한다. */
import { onMounted, ref } from 'vue'

import * as api from '@/api/users'
import EmptyState from '@/components/common/EmptyState.vue'
import { useToast } from '@/composables/useToast'
import { formatDateTime } from '@/utils/format'

const toast = useToast()

const tab = ref('PENDING') // PENDING | REJECTED
const rows = ref([])
const loading = ref(false)
const loadError = ref(null)
const rejecting = ref(null) // 반려 사유를 입력 중인 사용자
const reason = ref('')
const busyId = ref(null)

onMounted(load)

async function load() {
  loading.value = true
  loadError.value = null
  try {
    const { data } = await api.fetchUsers({ approval_status: tab.value, ordering: 'created_at', page_size: 100 })
    rows.value = data.results ?? data
  } catch (err) {
    loadError.value = err.parsed ?? { message: '목록을 불러오지 못했습니다.' }
  } finally {
    loading.value = false
  }
}

function switchTab(next) {
  tab.value = next
  rejecting.value = null
  load()
}

async function approve(user) {
  busyId.value = user.id
  try {
    await api.approveUser(user.id)
    toast.push(`${user.full_name}(${user.username}) 님을 승인했습니다.`, 'success')
    await load()
  } catch (err) {
    toast.push(err.parsed?.message ?? '승인하지 못했습니다.', 'danger')
  } finally {
    busyId.value = null
  }
}

function startReject(user) {
  rejecting.value = user
  reason.value = ''
}

async function confirmReject() {
  const user = rejecting.value
  if (!reason.value.trim()) return
  busyId.value = user.id
  try {
    await api.rejectUser(user.id, reason.value.trim())
    toast.push(`${user.full_name}(${user.username}) 님의 가입을 반려했습니다.`, 'info')
    rejecting.value = null
    await load()
  } catch (err) {
    toast.push(err.parsed?.message ?? '반려하지 못했습니다.', 'danger')
  } finally {
    busyId.value = null
  }
}
</script>

<template>
  <div>
    <ul class="nav nav-tabs mb-3">
      <li class="nav-item">
        <button class="nav-link" :class="{ active: tab === 'PENDING' }" type="button" @click="switchTab('PENDING')">
          승인 대기
        </button>
      </li>
      <li class="nav-item">
        <button class="nav-link" :class="{ active: tab === 'REJECTED' }" type="button" @click="switchTab('REJECTED')">
          반려
        </button>
      </li>
    </ul>

    <div v-if="loadError" class="alert alert-danger" role="alert">{{ loadError.message }}</div>
    <div v-else-if="loading" class="text-center py-4">
      <div class="spinner-border text-primary" role="status"><span class="visually-hidden">불러오는 중</span></div>
    </div>
    <EmptyState
      v-else-if="!rows.length"
      :title="tab === 'PENDING' ? '승인 대기 중인 가입 신청이 없습니다.' : '반려된 가입 신청이 없습니다.'"
      icon="bi-person-check"
    />

    <div v-else class="row g-3">
      <div v-for="user in rows" :key="user.id" class="col-12 col-xl-6">
        <article class="card h-100" :aria-label="`${user.full_name}(${user.username}) 가입 신청`">
          <div class="card-body">
            <div class="d-flex flex-wrap justify-content-between gap-2 mb-2">
              <div>
                <h2 class="h6 mb-0">{{ user.full_name }} <span class="text-secondary fw-normal">({{ user.username }})</span></h2>
                <p class="small text-secondary mb-0">{{ user.organization }}<template v-if="user.email"> · {{ user.email }}</template></p>
              </div>
              <span class="small text-secondary">신청 {{ formatDateTime(user.created_at) }}</span>
            </div>

            <p class="small mb-2">
              <span class="text-secondary">가입 사유</span><br />
              {{ user.signup_reason || '(입력하지 않음)' }}
            </p>
            <p v-if="tab === 'REJECTED'" class="small mb-2">
              <span class="text-secondary">반려 사유</span><br />
              {{ user.rejection_reason }}
              <span class="text-secondary">— {{ user.approved_by_name || '알 수 없음' }}, {{ formatDateTime(user.approved_at) }}</span>
            </p>

            <form
              v-if="rejecting?.id === user.id"
              class="mt-2"
              novalidate
              @submit.prevent="confirmReject"
            >
              <label :for="`reason-${user.id}`" class="form-label small">반려 사유 (가입자가 로그인할 때 보입니다)</label>
              <textarea
                :id="`reason-${user.id}`"
                v-model="reason"
                class="form-control form-control-sm mb-2"
                rows="2"
                maxlength="500"
                required
              ></textarea>
              <button class="btn btn-sm btn-danger me-2" type="submit" :disabled="!reason.trim() || busyId === user.id">
                반려 확정
              </button>
              <button class="btn btn-sm btn-outline-secondary" type="button" @click="rejecting = null">취소</button>
            </form>

            <div v-else class="d-flex gap-2 mt-2">
              <button class="btn btn-sm btn-primary" type="button" :disabled="busyId === user.id" @click="approve(user)">
                <i class="bi bi-check-lg me-1" aria-hidden="true"></i>승인
              </button>
              <button
                v-if="tab === 'PENDING'"
                class="btn btn-sm btn-outline-danger"
                type="button"
                :disabled="busyId === user.id"
                @click="startReject(user)"
              >
                반려
              </button>
            </div>
          </div>
        </article>
      </div>
    </div>
  </div>
</template>
