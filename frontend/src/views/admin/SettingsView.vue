<script setup>
/**
 * 설정 (specs/08 ADM-4·ADM-5). 튜닝값은 전부 여기서 바꾼다 — 코드에 상수로 두지 않는다.
 * 분류(인증·질의응답·검색 등)는 마일스톤마다 늘어난다.
 */
import { computed, onMounted, ref } from 'vue'

import * as api from '@/api/settings'
import SettingForm from '@/components/admin/SettingForm.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import { useToast } from '@/composables/useToast'

const toast = useToast()

const rows = ref([])
const categories = ref([])
const activeCategory = ref('')
const draft = ref({})
const error = ref(null)
const loadError = ref(null)
const loaded = ref(false)
const busy = ref(false)

const rowByKey = computed(() => Object.fromEntries(rows.value.map((r) => [r.key, r])))
const visibleRows = computed(() => rows.value.filter((r) => r.category === activeCategory.value))
const changed = computed(() =>
  Object.keys(draft.value).filter(
    (key) => JSON.stringify(draft.value[key]) !== JSON.stringify(rowByKey.value[key]?.value),
  ),
)

onMounted(load)

async function load() {
  loadError.value = null
  try {
    const { data } = await api.fetchSettings()
    rows.value = data.results
    categories.value = data.categories
    if (!categories.value.some((c) => c.code === activeCategory.value)) {
      activeCategory.value = categories.value[0]?.code ?? ''
    }
    draft.value = Object.fromEntries(rows.value.map((r) => [r.key, r.value]))
  } catch (err) {
    loadError.value = err.parsed ?? { message: '설정을 불러오지 못했습니다.' }
  } finally {
    loaded.value = true
  }
}

async function save() {
  if (!changed.value.length || busy.value) return
  busy.value = true
  error.value = null
  try {
    const payload = Object.fromEntries(changed.value.map((k) => [k, draft.value[k]]))
    const { data } = await api.patchSettings(payload)
    await load()
    toast.push(`${data.updated.length}개 항목을 저장했습니다.`, 'success')
  } catch (err) {
    error.value = err.parsed
  } finally {
    busy.value = false
  }
}

async function reset(row) {
  if (!window.confirm(`"${row.label}" 을(를) 기본값으로 되돌릴까요?`)) return
  try {
    await api.resetSetting(row.key)
    await load()
    toast.push('기본값으로 되돌렸습니다.', 'success')
  } catch (err) {
    toast.push(err.parsed?.message ?? '되돌리지 못했습니다.', 'danger')
  }
}
</script>

<template>
  <div>
    <div v-if="loadError" class="alert alert-danger" role="alert">{{ loadError.message }}</div>
    <div v-else-if="!loaded" class="text-center py-4">
      <div class="spinner-border text-primary" role="status"><span class="visually-hidden">불러오는 중</span></div>
    </div>
    <EmptyState v-else-if="!rows.length" title="설정 항목이 없습니다." icon="bi-sliders" />

    <template v-else>
      <ul v-if="categories.length > 1" class="nav nav-tabs mb-3">
        <li v-for="cat in categories" :key="cat.code" class="nav-item">
          <button
            class="nav-link"
            :class="{ active: activeCategory === cat.code }"
            type="button"
            @click="activeCategory = cat.code"
          >
            {{ cat.label }}
          </button>
        </li>
      </ul>

      <div class="card">
        <div class="card-body">
          <SettingForm
            v-for="row in visibleRows"
            :key="row.key"
            v-model="draft[row.key]"
            :row="row"
            @reset="reset(row)"
          />

          <div v-if="error" class="alert alert-danger py-2 small mt-3" role="alert">{{ error.message }}</div>

          <div class="mt-3">
            <button class="btn btn-primary" type="button" :disabled="busy || !changed.length" @click="save">
              <span v-if="busy" class="spinner-border spinner-border-sm me-2" aria-hidden="true"></span>
              저장 ({{ changed.length }}개 변경)
            </button>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
