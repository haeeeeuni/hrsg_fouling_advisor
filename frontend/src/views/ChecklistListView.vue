<script setup>
/**
 * 데이터 요청 건 목록 (specs/07 CHK-3·CHK-4). 요청 건은 만든 사람만 본다.
 * 새 요청 건을 만들면 그 시점의 체크리스트 항목이 복사된다 — 나중에 템플릿이 바뀌어도 그대로다.
 */
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import * as api from '@/api/checklist'
import ErrorAlert from '@/components/admin/ErrorAlert.vue'
import ProgressBar from '@/components/checklist/ProgressBar.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import { formatDate, formatDateTime } from '@/utils/format'

const router = useRouter()

const STATUS_BADGE = { IN_PROGRESS: 'text-bg-primary', DONE: 'text-bg-success', ARCHIVED: 'text-bg-secondary' }

const rows = ref([])
const loaded = ref(false)
const loadError = ref(null)
const showArchived = ref(false)
const form = ref({ title: '', memo: '', due_date: '' })
const creating = ref(false)
const createError = ref(null)

onMounted(load)

async function load() {
  loaded.value = false
  loadError.value = null
  try {
    const { data } = await api.fetchRequests(showArchived.value ? { status: 'ARCHIVED' } : {})
    rows.value = data.results ?? data
  } catch (err) {
    loadError.value = err.parsed
  } finally {
    loaded.value = true
  }
}

async function create() {
  if (creating.value) return
  creating.value = true
  createError.value = null
  try {
    const payload = { ...form.value, due_date: form.value.due_date || null }
    const { data } = await api.createRequest(payload)
    router.push({ name: 'checklist-detail', params: { id: data.id } })
  } catch (err) {
    createError.value = err.parsed
  } finally {
    creating.value = false
  }
}

function toggleArchived() {
  showArchived.value = !showArchived.value
  load()
}
</script>

<template>
  <div class="ui-container">
    <h1 class="h3 mb-1">플랜트 데이터 요청 체크리스트</h1>
    <p class="text-secondary">
      정확한 평가에 꼭 필요한 데이터를 요청 건별로 관리합니다. 받은 항목을 체크하고, 남은 항목을 이메일 본문으로 복사하세요.
    </p>

    <form class="card mb-4" novalidate @submit.prevent="create">
      <div class="card-body row g-2 align-items-end">
        <div class="col-12 col-md-5">
          <label for="reqTitle" class="form-label">새 요청 건 이름</label>
          <input id="reqTitle" v-model.trim="form.title" class="form-control" placeholder="예: 10월 사전 평가" maxlength="200" />
        </div>
        <div class="col-6 col-md-3">
          <label for="reqDue" class="form-label">희망 회신일 (선택)</label>
          <input id="reqDue" v-model="form.due_date" type="date" class="form-control" />
        </div>
        <div class="col-6 col-md-4">
          <button class="btn btn-primary w-100" type="submit" :disabled="creating || !form.title">
            <i class="bi bi-plus-lg me-1" aria-hidden="true"></i>요청 건 만들기
          </button>
        </div>
        <div class="col-12">
          <label for="reqMemo" class="form-label small text-secondary mb-1">메모 (선택)</label>
          <input id="reqMemo" v-model.trim="form.memo" class="form-control form-control-sm" />
        </div>
        <div class="col-12"><ErrorAlert :error="createError" /></div>
      </div>
    </form>

    <div class="d-flex justify-content-between align-items-center mb-2">
      <h2 class="h5 mb-0">{{ showArchived ? '보관한 요청 건' : '내 요청 건' }}</h2>
      <button class="btn btn-sm btn-outline-secondary" type="button" @click="toggleArchived">
        {{ showArchived ? '진행 중인 요청 건 보기' : '보관함 보기' }}
      </button>
    </div>

    <ErrorAlert :error="loadError" />
    <div v-if="!loaded" class="text-center py-4">
      <div class="spinner-border text-primary" role="status"><span class="visually-hidden">불러오는 중</span></div>
    </div>
    <div v-else-if="!rows.length" class="card">
      <EmptyState
        :title="showArchived ? '보관한 요청 건이 없습니다.' : '아직 요청 건이 없습니다.'"
        :description="showArchived ? '' : '위에서 요청 건을 만들면 데이터 요청 항목이 준비됩니다.'"
        icon="bi-ui-checks"
      />
    </div>
    <div v-else class="row g-3">
      <div v-for="row in rows" :key="row.id" class="col-12 col-lg-6">
        <RouterLink :to="{ name: 'checklist-detail', params: { id: row.id } }" class="card h-100 ui-feature-card text-decoration-none">
          <div class="card-body">
            <div class="d-flex justify-content-between gap-2 mb-2">
              <h3 class="h6 mb-0">{{ row.title }}</h3>
              <span class="badge" :class="STATUS_BADGE[row.status]">{{ row.status_label }}</span>
            </div>
            <ProgressBar :progress="row.progress" :label="`${row.title} 진행률`" />
            <p class="small text-secondary mb-0 mt-2">
              <template v-if="row.due_date">회신 희망 {{ formatDate(row.due_date) }} · </template>
              수정 {{ formatDateTime(row.updated_at) }}
            </p>
          </div>
        </RouterLink>
      </div>
    </div>
  </div>
</template>
