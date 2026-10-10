<script setup>
/**
 * 데이터 요청 건 상세 (specs/07). 항목별로 받음/미수신/해당 없음을 체크하고, 미수신 항목을
 * 이메일 본문으로 복사한다. 이메일을 직접 보내지는 않는다(결정 D25).
 */
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import * as api from '@/api/checklist'
import ErrorAlert from '@/components/admin/ErrorAlert.vue'
import ChecklistItemRow from '@/components/checklist/ChecklistItemRow.vue'
import ProgressBar from '@/components/checklist/ProgressBar.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import { useToast } from '@/composables/useToast'
import { copyText } from '@/composables/useClipboard'
import { groupByCategory } from '@/utils/checklist'
import { formatDate } from '@/utils/format'

const props = defineProps({
  id: { type: String, required: true },
})

const router = useRouter()
const toast = useToast()

const STATUS_BADGE = { IN_PROGRESS: 'text-bg-primary', DONE: 'text-bg-success', ARCHIVED: 'text-bg-secondary' }

const data = ref(null)
const loadError = ref(null)
const notFound = ref(false)
const busyItem = ref(null)
const editing = ref(false)
const draft = ref({})
const editError = ref(null)
/** 복사 실패 시 펼치는 텍스트 상자 */
const manualCopy = ref(null)

const groups = computed(() => (data.value ? groupByCategory(data.value.items) : []))

onMounted(load)

async function load() {
  try {
    data.value = (await api.fetchRequest(props.id)).data
  } catch (err) {
    if (err.response?.status === 404) notFound.value = true
    else loadError.value = err.parsed
  }
}

async function changeItem(item, payload) {
  busyItem.value = item.id
  try {
    const { data: result } = await api.updateItem(props.id, item.id, payload)
    Object.assign(item, result.item)
    const { progress, status, status_label: statusLabel } = result.request
    Object.assign(data.value, { progress, status, status_label: statusLabel })
    if (payload.state && status === 'DONE') toast.push('필수 항목을 모두 받았습니다. 요청 건이 완료되었습니다.', 'success')
  } catch (err) {
    toast.push(err.parsed?.message ?? '저장하지 못했습니다.', 'danger')
  } finally {
    busyItem.value = null
  }
}

async function copy(lang, scope) {
  manualCopy.value = null
  try {
    const { data: result } = await api.fetchEmailText(props.id, { lang, scope })
    if (await copyText(result.text)) {
      toast.push(`${scope === 'pending' ? '미수신' : '전체'} 항목을 ${lang === 'en' ? '영어' : '한국어'} 이메일 본문으로 복사했습니다.`, 'success')
    } else {
      manualCopy.value = result.text
    }
  } catch (err) {
    toast.push(err.parsed?.message ?? '복사할 문구를 만들지 못했습니다.', 'danger')
  }
}

async function addNewItems() {
  try {
    const { data: result } = await api.syncTemplate(props.id)
    data.value = result.request
    toast.push(`새 항목 ${result.added}개를 추가했습니다.`, 'success')
  } catch (err) {
    toast.push(err.parsed?.message ?? '추가하지 못했습니다.', 'danger')
  }
}

function startEdit() {
  draft.value = { title: data.value.title, memo: data.value.memo, due_date: data.value.due_date ?? '' }
  editError.value = null
  editing.value = true
}

async function saveEdit() {
  editError.value = null
  try {
    const payload = { ...draft.value, due_date: draft.value.due_date || null }
    const { data: result } = await api.updateRequest(props.id, payload)
    Object.assign(data.value, result)
    editing.value = false
  } catch (err) {
    editError.value = err.parsed
  }
}

async function setArchived(archived) {
  const { data: result } = await api.updateRequest(props.id, { status: archived ? 'ARCHIVED' : 'IN_PROGRESS' })
  Object.assign(data.value, result)
  toast.push(archived ? '보관했습니다.' : '보관을 해제했습니다.', 'info')
}

async function remove() {
  if (!window.confirm(`"${data.value.title}" 요청 건을 삭제할까요? 되돌릴 수 없습니다.`)) return
  await api.deleteRequest(props.id)
  toast.push('삭제했습니다.', 'info')
  router.push({ name: 'checklist' })
}

function selectAll(event) {
  event.target.select()
}
</script>

<template>
  <div class="ui-container">
    <RouterLink class="small" :to="{ name: 'checklist' }">
      <i class="bi bi-arrow-left me-1" aria-hidden="true"></i>요청 건 목록
    </RouterLink>

    <div v-if="notFound" class="card mt-3">
      <EmptyState title="요청 건을 찾을 수 없습니다." description="삭제됐거나 다른 사용자의 요청 건입니다." icon="bi-question-circle" />
    </div>
    <ErrorAlert v-else-if="loadError" class="mt-3" :error="loadError" />
    <div v-else-if="!data" class="text-center py-5">
      <div class="spinner-border text-primary" role="status"><span class="visually-hidden">불러오는 중</span></div>
    </div>

    <template v-else>
      <section class="card my-3">
        <div class="card-body">
          <template v-if="!editing">
            <div class="d-flex flex-wrap justify-content-between align-items-start gap-2">
              <div>
                <h1 class="h4 mb-1">{{ data.title }}</h1>
                <p class="small text-secondary mb-0">
                  <template v-if="data.due_date">회신 희망 {{ formatDate(data.due_date) }} · </template>
                  항목 기준 {{ formatDate(data.template_snapshot_at) }}
                </p>
                <p v-if="data.memo" class="small mb-0 mt-1">{{ data.memo }}</p>
              </div>
              <span class="badge fs-6" :class="STATUS_BADGE[data.status]" data-testid="request-status">{{ data.status_label }}</span>
            </div>
            <div class="mt-3"><ProgressBar :progress="data.progress" label="전체 진행률" /></div>
            <div class="d-flex flex-wrap gap-2 mt-3">
              <div class="dropdown">
                <button class="btn btn-primary btn-sm dropdown-toggle" type="button" data-bs-toggle="dropdown" aria-expanded="false">
                  <i class="bi bi-clipboard me-1" aria-hidden="true"></i>이메일 본문 복사
                </button>
                <ul class="dropdown-menu">
                  <li><button class="dropdown-item" type="button" @click="copy('ko', 'pending')">미수신 항목 — 한국어</button></li>
                  <li><button class="dropdown-item" type="button" @click="copy('en', 'pending')">미수신 항목 — English</button></li>
                  <li><hr class="dropdown-divider" /></li>
                  <li><button class="dropdown-item" type="button" @click="copy('ko', 'all')">전체 항목 — 한국어 (처음 요청)</button></li>
                  <li><button class="dropdown-item" type="button" @click="copy('en', 'all')">전체 항목 — English (처음 요청)</button></li>
                </ul>
              </div>
              <button class="btn btn-outline-secondary btn-sm" type="button" @click="startEdit">정보 수정</button>
              <button
                class="btn btn-outline-secondary btn-sm"
                type="button"
                @click="setArchived(data.status !== 'ARCHIVED')"
              >
                {{ data.status === 'ARCHIVED' ? '보관 해제' : '보관' }}
              </button>
              <button class="btn btn-outline-danger btn-sm" type="button" @click="remove">삭제</button>
            </div>
          </template>

          <form v-else novalidate @submit.prevent="saveEdit">
            <div class="row g-2">
              <div class="col-12 col-md-6">
                <label for="editTitle" class="form-label small">요청 건 이름</label>
                <input id="editTitle" v-model.trim="draft.title" class="form-control form-control-sm" maxlength="200" />
              </div>
              <div class="col-6 col-md-3">
                <label for="editDue" class="form-label small">희망 회신일</label>
                <input id="editDue" v-model="draft.due_date" type="date" class="form-control form-control-sm" />
              </div>
              <div class="col-12">
                <label for="editMemo" class="form-label small">메모</label>
                <input id="editMemo" v-model.trim="draft.memo" class="form-control form-control-sm" />
              </div>
            </div>
            <ErrorAlert class="mt-2" :error="editError" />
            <div class="mt-2">
              <button class="btn btn-sm btn-primary me-2" type="submit">저장</button>
              <button class="btn btn-sm btn-outline-secondary" type="button" @click="editing = false">취소</button>
            </div>
          </form>
        </div>
      </section>

      <div v-if="manualCopy" class="card mb-3" role="region" aria-label="복사할 문구">
        <div class="card-body">
          <p class="small mb-2">
            <i class="bi bi-info-circle me-1" aria-hidden="true"></i>
            이 환경에서는 자동 복사가 되지 않습니다. 아래 문구를 선택해 복사하세요(Ctrl/⌘ + C).
          </p>
          <textarea class="form-control font-monospace small" rows="10" readonly :value="manualCopy" aria-label="이메일 본문" @focus="selectAll"></textarea>
          <button class="btn btn-sm btn-link px-0" type="button" @click="manualCopy = null">닫기</button>
        </div>
      </div>

      <div v-if="data.new_template_items" class="alert alert-info d-flex flex-wrap align-items-center gap-2" role="status">
        <i class="bi bi-plus-circle" aria-hidden="true"></i>
        <span>이 요청 건을 만든 뒤 체크리스트에 새 항목 {{ data.new_template_items }}개가 생겼습니다.</span>
        <button class="btn btn-sm btn-outline-primary ms-auto" type="button" @click="addNewItems">새 항목 추가하기</button>
      </div>

      <section v-for="group in groups" :key="group.category" class="card mb-3" :aria-labelledby="`cat-${group.category}`">
        <div class="card-body">
          <div class="d-flex flex-wrap justify-content-between align-items-center gap-2 mb-2">
            <h2 :id="`cat-${group.category}`" class="h6 mb-0">{{ group.label }}</h2>
            <div style="min-width: 12rem"><ProgressBar :progress="group.progress" :label="`${group.label} 진행률`" /></div>
          </div>
          <ul class="list-unstyled mb-0">
            <ChecklistItemRow
              v-for="item in group.items"
              :key="item.id"
              :item="item"
              :busy="busyItem === item.id"
              @change="(payload) => changeItem(item, payload)"
            />
          </ul>
        </div>
      </section>
    </template>
  </div>
</template>
