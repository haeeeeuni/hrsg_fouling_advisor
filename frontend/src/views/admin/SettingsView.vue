<script setup>
import { computed, onMounted, ref, watch } from 'vue'

import * as api from '@/api/settings'
import SettingForm from '@/components/admin/SettingForm.vue'
import { useToast } from '@/composables/useToast'
import { useSettingsStore } from '@/stores/settings'
import { useUnitsStore } from '@/stores/units'

const props = defineProps({
  // BenefitSettingsView 가 category="BENEFIT" 로 재사용한다.
  category: { type: String, default: '' },
})

const toast = useToast()
const units = useUnitsStore()
const settingsStore = useSettingsStore()

const CATEGORY_LABELS = {
  FOULING: '오염도',
  PREPROCESS: '전처리',
  CLUSTER: '군집화',
  MODEL: '모델',
  BENEFIT: '편익',
  SYSTEM: '시스템',
}

const rows = ref([])
const categories = ref([])
const activeCategory = ref(props.category || 'FOULING')
const draft = ref({})
const error = ref(null)
const busy = ref(false)

// 호기별 오버라이드 탭
const mode = ref('GLOBAL') // GLOBAL | UNIT
const unitRows = ref([])
const unitDraft = ref({})

const visibleRows = computed(() =>
  rows.value.filter((r) => r.category === activeCategory.value),
)
const changed = computed(() =>
  Object.keys(draft.value).filter(
    (key) => JSON.stringify(draft.value[key]) !== JSON.stringify(rowByKey.value[key]?.value),
  ),
)
const rowByKey = computed(() => Object.fromEntries(rows.value.map((r) => [r.key, r])))

onMounted(async () => {
  await units.fetchUnits()
  await load()
})
watch(() => units.selectedUnitId, () => mode.value === 'UNIT' && loadUnit())
watch(mode, (m) => (m === 'UNIT' ? loadUnit() : load()))

async function load() {
  const { data } = await api.fetchSettings()
  rows.value = data.results
  categories.value = props.category ? [props.category] : data.categories
  if (!categories.value.includes(activeCategory.value)) {
    activeCategory.value = categories.value[0]
  }
  draft.value = Object.fromEntries(rows.value.map((r) => [r.key, r.value]))
}

async function loadUnit() {
  if (!units.selectedUnitId) return
  const { data } = await api.fetchUnitSettings(units.selectedUnitId)
  unitRows.value = data.settings
  unitDraft.value = Object.fromEntries(
    data.settings.filter((r) => r.is_overridden).map((r) => [r.key, r.effective_value]),
  )
}

async function save() {
  if (!changed.value.length) return
  busy.value = true
  error.value = null
  try {
    const payload = Object.fromEntries(changed.value.map((k) => [k, draft.value[k]]))
    const { data } = await api.patchSettings(payload)
    await load()
    settingsStore.invalidate()
    toast.push(`${data.updated.length}개 항목을 저장했습니다. ${data.notice}`, 'success')
  } catch (err) {
    error.value = err.parsed
  } finally {
    busy.value = false
  }
}

async function restore() {
  if (!window.confirm(`${CATEGORY_LABELS[activeCategory.value]} 설정을 기본값으로 되돌릴까요?`)) return
  const { data } = await api.restoreDefaults({ category: activeCategory.value })
  await load()
  settingsStore.invalidate()
  toast.push(`${data.count}개 항목을 기본값으로 복원했습니다.`, 'success')
}

async function saveOverrides() {
  busy.value = true
  error.value = null
  try {
    await api.saveUnitSettings(units.selectedUnitId, unitDraft.value)
    await loadUnit()
    settingsStore.invalidate()
    toast.push('호기별 설정을 저장했습니다.', 'success')
  } catch (err) {
    error.value = err.parsed
  } finally {
    busy.value = false
  }
}

async function clearOverride(key) {
  await api.clearUnitSetting(units.selectedUnitId, key)
  await loadUnit()
  settingsStore.invalidate()
  toast.push('오버라이드를 해제했습니다. 전역값을 상속합니다.', 'info')
}

function toggleOverride(row, on) {
  if (on) unitDraft.value[row.key] = row.effective_value
  else delete unitDraft.value[row.key]
}
</script>

<template>
  <div>
    <div class="d-flex justify-content-between align-items-center mb-3">
      <h2 class="h6 mb-0">{{ category ? '편익 계산 기본값' : '분석 설정' }}</h2>
      <div class="btn-group btn-group-sm" role="group" aria-label="설정 범위">
        <button class="btn" :class="mode === 'GLOBAL' ? 'btn-primary' : 'btn-outline-secondary'"
                @click="mode = 'GLOBAL'">전역</button>
        <button class="btn" :class="mode === 'UNIT' ? 'btn-primary' : 'btn-outline-secondary'"
                @click="mode = 'UNIT'">호기별 오버라이드</button>
      </div>
    </div>

    <div class="alert alert-secondary py-2 small" role="note">
      변경은 <strong>다음 분석부터 적용</strong>됩니다. 기존 분석 결과는 실행 당시 설정 스냅샷을
      보관하므로 바뀌지 않습니다.
    </div>

    <!-- 전역 설정 -->
    <template v-if="mode === 'GLOBAL'">
      <ul v-if="categories.length > 1" class="nav nav-tabs mb-3">
        <li v-for="cat in categories" :key="cat" class="nav-item">
          <button class="nav-link" :class="{ active: activeCategory === cat }"
                  @click="activeCategory = cat">
            {{ CATEGORY_LABELS[cat] ?? cat }}
          </button>
        </li>
      </ul>

      <div class="card">
        <div class="card-body">
          <SettingForm
            v-for="row in visibleRows"
            :key="row.key"
            :row="row"
            v-model="draft[row.key]"
          />

          <div v-if="error" class="alert alert-danger py-2 small mt-3" role="alert">
            {{ error.message }}
            <div v-if="error.details?.suggestion" class="mt-1">
              제안: {{ JSON.stringify(error.details.suggestion) }}
            </div>
          </div>

          <div class="mt-3">
            <button class="btn btn-primary me-2" :disabled="busy || !changed.length" @click="save">
              <span v-if="busy" class="spinner-border spinner-border-sm me-2"></span>
              저장 ({{ changed.length }}개 변경)
            </button>
            <button class="btn btn-outline-secondary" :disabled="busy" @click="restore">
              기본값으로 복원
            </button>
          </div>
        </div>
      </div>
    </template>

    <!-- 호기별 오버라이드 -->
    <template v-else>
      <div class="mb-3" style="max-width: 24rem">
        <label for="ovUnit" class="form-label">호기</label>
        <select id="ovUnit" class="form-select" :value="units.selectedUnitId"
                @change="units.selectUnit(Number($event.target.value))">
          <option v-for="unit in units.list" :key="unit.id" :value="unit.id">
            {{ unit.code }} — {{ unit.name }}
          </option>
        </select>
      </div>

      <div class="card">
        <div class="card-body">
          <table class="table table-sm align-middle mb-0">
            <thead>
              <tr>
                <th scope="col" style="width: 8%">덮어쓰기</th>
                <th scope="col" style="width: 34%">항목</th>
                <th scope="col" style="width: 20%">전역값</th>
                <th scope="col" style="width: 24%">호기값</th>
                <th scope="col"></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in unitRows.filter((r) => !category || r.category === category)"
                  :key="row.key">
                <td>
                  <div class="form-check">
                    <input class="form-check-input" type="checkbox"
                           :checked="row.key in unitDraft"
                           :aria-label="`${row.label} 오버라이드`"
                           @change="toggleOverride(row, $event.target.checked)" />
                  </div>
                </td>
                <td class="small">
                  {{ row.label }}
                  <code class="text-secondary">{{ row.key }}</code>
                </td>
                <td class="small text-secondary">{{ JSON.stringify(row.global_value) }}</td>
                <td>
                  <input v-if="row.key in unitDraft" v-model="unitDraft[row.key]"
                         class="form-control form-control-sm"
                         :type="['INT', 'FLOAT'].includes(row.value_type) ? 'number' : 'text'"
                         step="any" :aria-label="`${row.label} 호기값`" />
                  <span v-else class="small text-secondary">전역값 상속</span>
                </td>
                <td class="text-end">
                  <button v-if="row.is_overridden" class="btn btn-sm btn-outline-danger"
                          @click="clearOverride(row.key)">해제</button>
                </td>
              </tr>
            </tbody>
          </table>

          <div v-if="error" class="alert alert-danger py-2 small mt-3">{{ error.message }}</div>

          <button class="btn btn-primary mt-3" :disabled="busy" @click="saveOverrides">
            호기별 설정 저장
          </button>
        </div>
      </div>
    </template>
  </div>
</template>
