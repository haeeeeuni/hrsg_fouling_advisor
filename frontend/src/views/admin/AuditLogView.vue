<script setup>
import { onMounted, ref } from 'vue'

import * as api from '@/api/users'
import EmptyState from '@/components/common/EmptyState.vue'
import { formatDateTime } from '@/utils/format'

const logs = ref([])
const filters = ref({ target_type: '', action: '' })
const expanded = ref(null)

const TARGET_TYPES = [
  'Setting', 'UnitSetting', 'User', 'Unit', 'ColumnMapping',
  'CleaningEvent', 'FoulingKeyword', 'ModelVersion', 'UploadBatch',
  'CleanBaselinePeriod', 'ClusterDefinition',
]
const ACTIONS = ['CREATE', 'UPDATE', 'DELETE', 'ACTIVATE', 'RESTORE', 'ROLLBACK', 'TRAIN']

onMounted(load)

async function load() {
  const params = Object.fromEntries(Object.entries(filters.value).filter(([, v]) => v !== ''))
  const { data } = await api.fetchAuditLogs({ ...params, page_size: 100 })
  logs.value = data.results ?? data
}
</script>

<template>
  <div>
    <div class="row g-2 align-items-end mb-3">
      <div class="col-6 col-lg-3">
        <label for="alTarget" class="form-label small">대상</label>
        <select id="alTarget" v-model="filters.target_type" class="form-select form-select-sm" @change="load">
          <option value="">전체</option>
          <option v-for="t in TARGET_TYPES" :key="t" :value="t">{{ t }}</option>
        </select>
      </div>
      <div class="col-6 col-lg-3">
        <label for="alAction" class="form-label small">동작</label>
        <select id="alAction" v-model="filters.action" class="form-select form-select-sm" @change="load">
          <option value="">전체</option>
          <option v-for="a in ACTIONS" :key="a" :value="a">{{ a }}</option>
        </select>
      </div>
    </div>

    <EmptyState v-if="!logs.length" title="감사 로그가 없습니다." icon="bi-journal-text" />

    <table v-else class="table table-sm align-middle">
      <thead>
        <tr>
          <th scope="col">일시</th><th scope="col">행위자</th><th scope="col">동작</th>
          <th scope="col">대상</th><th scope="col">IP</th><th scope="col"></th>
        </tr>
      </thead>
      <tbody>
        <template v-for="log in logs" :key="log.id">
          <tr>
            <td class="small">{{ formatDateTime(log.created_at) }}</td>
            <td class="small">
              {{ log.actor_name || '시스템' }}
              <span v-if="log.actor_employee_no" class="text-secondary">
                ({{ log.actor_employee_no }})
              </span>
            </td>
            <td><span class="badge text-bg-light">{{ log.action_label }}</span></td>
            <td class="small">
              <code>{{ log.target_type }}</code> {{ log.target_label }}
            </td>
            <td class="small">{{ log.ip || '–' }}</td>
            <td class="text-end">
              <button v-if="log.before || log.after" class="btn btn-sm btn-outline-secondary"
                      @click="expanded = expanded === log.id ? null : log.id">
                변경 내역
              </button>
            </td>
          </tr>
          <tr v-if="expanded === log.id">
            <td colspan="6" class="bg-body-tertiary">
              <div class="row g-3">
                <div class="col-6">
                  <p class="small fw-semibold mb-1">변경 전</p>
                  <pre class="small mb-0">{{ JSON.stringify(log.before ?? {}, null, 2) }}</pre>
                </div>
                <div class="col-6">
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
</template>
