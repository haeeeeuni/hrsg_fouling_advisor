<script setup>
/** 감사 로그 (specs/08 ADM-6). 수정·삭제할 수 없고 조회만 한다. */
import { onMounted, ref } from 'vue'

import * as api from '@/api/users'
import EmptyState from '@/components/common/EmptyState.vue'
import { formatDateTime } from '@/utils/format'

const logs = ref([])
const loadError = ref(null)
const loaded = ref(false)
const filters = ref({ target_type: '', action: '' })
const expanded = ref(null)

/** 대상 종류. 마일스톤마다 늘어난다(문서·GT 모델·공법·SMP·파라미터 세트·체크리스트 템플릿 등). */
const TARGET_TYPES = [
  { code: 'User', label: '사용자' },
  { code: 'Setting', label: '설정' },
]
const ACTIONS = [
  { code: 'CREATE', label: '생성' },
  { code: 'UPDATE', label: '수정' },
  { code: 'DELETE', label: '삭제' },
  { code: 'APPROVE', label: '승인' },
  { code: 'REJECT', label: '반려' },
  { code: 'RESTORE', label: '복원' },
  { code: 'ACTIVATE', label: '활성화' },
]

onMounted(load)

async function load() {
  loadError.value = null
  const params = Object.fromEntries(Object.entries(filters.value).filter(([, v]) => v !== ''))
  try {
    const { data } = await api.fetchAuditLogs({ ...params, page_size: 100 })
    logs.value = data.results ?? data
  } catch (err) {
    loadError.value = err.parsed ?? { message: '감사 로그를 불러오지 못했습니다.' }
  } finally {
    loaded.value = true
  }
}
</script>

<template>
  <div>
    <div class="row g-2 align-items-end mb-3">
      <div class="col-6 col-lg-3">
        <label for="alTarget" class="form-label small">대상</label>
        <select id="alTarget" v-model="filters.target_type" class="form-select form-select-sm" @change="load">
          <option value="">전체</option>
          <option v-for="t in TARGET_TYPES" :key="t.code" :value="t.code">{{ t.label }}</option>
        </select>
      </div>
      <div class="col-6 col-lg-3">
        <label for="alAction" class="form-label small">동작</label>
        <select id="alAction" v-model="filters.action" class="form-select form-select-sm" @change="load">
          <option value="">전체</option>
          <option v-for="a in ACTIONS" :key="a.code" :value="a.code">{{ a.label }}</option>
        </select>
      </div>
    </div>

    <div v-if="loadError" class="alert alert-danger" role="alert">{{ loadError.message }}</div>
    <div v-else-if="!loaded" class="text-center py-4">
      <div class="spinner-border text-primary" role="status"><span class="visually-hidden">불러오는 중</span></div>
    </div>
    <EmptyState v-else-if="!logs.length" title="감사 로그가 없습니다." icon="bi-journal-text" />

    <div v-else class="table-responsive">
      <table class="table table-sm align-middle">
        <thead>
          <tr>
            <th scope="col">일시</th>
            <th scope="col">행위자</th>
            <th scope="col">동작</th>
            <th scope="col">대상</th>
            <th scope="col">IP</th>
            <th scope="col"><span class="visually-hidden">변경 내역</span></th>
          </tr>
        </thead>
        <tbody>
          <template v-for="log in logs" :key="log.id">
            <tr>
              <td class="small text-nowrap">{{ formatDateTime(log.created_at) }}</td>
              <td class="small">
                {{ log.actor_name || '시스템' }}
                <span v-if="log.actor_username" class="text-secondary">({{ log.actor_username }})</span>
              </td>
              <td><span class="badge text-bg-light">{{ log.action_label }}</span></td>
              <td class="small"><code>{{ log.target_type }}</code> {{ log.target_label }}</td>
              <td class="small">{{ log.ip || '–' }}</td>
              <td class="text-end">
                <button
                  v-if="log.before || log.after"
                  class="btn btn-sm btn-outline-secondary"
                  type="button"
                  :aria-expanded="expanded === log.id ? 'true' : 'false'"
                  @click="expanded = expanded === log.id ? null : log.id"
                >
                  변경 내역
                </button>
              </td>
            </tr>
            <tr v-if="expanded === log.id">
              <td colspan="6" class="bg-body-tertiary">
                <div class="row g-3">
                  <div class="col-12 col-md-6">
                    <p class="small fw-semibold mb-1">변경 전</p>
                    <pre class="small mb-0">{{ JSON.stringify(log.before ?? {}, null, 2) }}</pre>
                  </div>
                  <div class="col-12 col-md-6">
                    <p class="small fw-semibold mb-1">변경 후</p>
                    <pre class="small mb-0">{{ JSON.stringify(log.after ?? {}, null, 2) }}</pre>
                  </div>
                </div>
              </td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>
  </div>
</template>
