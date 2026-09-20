<script setup>
import { computed, onMounted, ref, watch } from 'vue'

import * as unitsApi from '@/api/units'
import FileDropzone from '@/components/upload/FileDropzone.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import { useToast } from '@/composables/useToast'
import { useUnitsStore } from '@/stores/units'
import { formatDateTime } from '@/utils/format'

const store = useUnitsStore()
const toast = useToast()

const standardFields = ref([])
const mappings = ref({}) // standard_field -> row
const problems = ref([])
const sourceColumns = ref([])
const preview = ref(null)
const versions = ref([])
const sampleFile = ref(null)
const error = ref(null)

const isComplete = computed(() => problems.value.length === 0)

const grouped = computed(() => ({
  REQUIRED: standardFields.value.filter((f) => f.requirement === 'REQUIRED'),
  ALTERNATIVE: standardFields.value.filter((f) => f.requirement === 'ALTERNATIVE'),
  OPTIONAL: standardFields.value.filter((f) => f.requirement === 'OPTIONAL'),
}))

onMounted(async () => {
  await store.fetchUnits()
  const { data } = await unitsApi.fetchStandardFields()
  standardFields.value = data
  await load()
})

watch(() => store.selectedUnitId, load)

async function load() {
  if (!store.selectedUnitId) return
  preview.value = null
  const { data } = await unitsApi.fetchColumnMappings(store.selectedUnitId)
  mappings.value = Object.fromEntries(data.mappings.map((m) => [m.standard_field, { ...m }]))
  problems.value = data.problems
  const versionRes = await unitsApi.fetchMappingVersions(store.selectedUnitId)
  versions.value = versionRes.data
}

function rowFor(field) {
  if (!mappings.value[field.key]) {
    mappings.value[field.key] = {
      standard_field: field.key,
      source_column: '',
      unit_label: '',
      scale_factor: 1,
      offset: 0,
      bool_rule: field.key === 'duct_burner_on' ? 'BOOL' : '',
      bool_threshold: null,
    }
  }
  return mappings.value[field.key]
}

function activeMappings() {
  return Object.values(mappings.value).filter((m) => m.source_column?.trim())
}

async function onSampleFile(file) {
  sampleFile.value = file
  error.value = null
  try {
    const { data } = await unitsApi.previewMapping(store.selectedUnitId, file, activeMappings())
    sourceColumns.value = data.header
    preview.value = data
  } catch (err) {
    error.value = err.parsed
  }
}

async function refreshPreview() {
  if (sampleFile.value) await onSampleFile(sampleFile.value)
}

async function save() {
  error.value = null
  try {
    const { data } = await unitsApi.saveColumnMappings(store.selectedUnitId, activeMappings())
    problems.value = data.problems
    store.invalidate()
    await store.fetchUnits(true)
    await load()
    toast.push(`매핑을 저장했습니다. (버전 ${data.version})`, 'success')
  } catch (err) {
    error.value = err.parsed
  }
}
</script>

<template>
  <div>
    <div class="row g-3 align-items-end mb-3">
      <div class="col-12 col-md-5">
        <label for="mapUnit" class="form-label">호기</label>
        <select
          id="mapUnit"
          class="form-select"
          :value="store.selectedUnitId"
          @change="store.selectUnit(Number($event.target.value))"
        >
          <option v-for="unit in store.list" :key="unit.id" :value="unit.id">
            {{ unit.code }} — {{ unit.name }}
          </option>
        </select>
      </div>
      <div class="col-12 col-md-7">
        <FileDropzone @select="onSampleFile" />
        <p class="form-text mb-0">
          샘플 CSV를 올리면 원본 컬럼 목록을 불러오고 상위 20행 변환을 미리 봅니다.
        </p>
      </div>
    </div>

    <!-- 필수 충족 규칙 실시간 배지 (specs/02 §5.3) -->
    <div class="alert py-2" :class="isComplete ? 'alert-success' : 'alert-warning'" role="status">
      <strong>{{ isComplete ? '필수 충족 규칙 통과' : '필수 충족 규칙 미통과' }}</strong>
      <ul v-if="!isComplete" class="mb-0 mt-1 ps-3 small">
        <li v-for="p in problems" :key="p.code">{{ p.message }} ({{ p.fields?.join(', ') }})</li>
      </ul>
    </div>

    <EmptyState v-if="!store.selectedUnitId" title="호기를 먼저 선택하세요." icon="bi-diagram-3" />

    <template v-else>
      <div v-for="(fields, group) in grouped" :key="group" class="mb-4">
        <h3 class="h6">
          {{ { REQUIRED: '필수 항목', ALTERNATIVE: '대체 항목', OPTIONAL: '선택 항목' }[group] }}
        </h3>
        <table class="table table-sm align-middle">
          <thead>
            <tr>
              <th scope="col" style="width: 22%">표준 항목</th>
              <th scope="col" style="width: 26%">원본 컬럼</th>
              <th scope="col" style="width: 12%">원본 단위</th>
              <th scope="col" style="width: 12%">계수</th>
              <th scope="col" style="width: 12%">오프셋</th>
              <th scope="col">해석 규칙</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="field in fields" :key="field.key">
              <td>
                <div class="small fw-semibold">{{ field.label }}</div>
                <code class="small text-secondary">{{ field.key }}</code>
                <span v-if="field.unit_label" class="small text-secondary"> ({{ field.unit_label }})</span>
              </td>
              <td>
                <input
                  v-if="!sourceColumns.length"
                  v-model.trim="rowFor(field).source_column"
                  class="form-control form-control-sm"
                  :aria-label="`${field.label} 원본 컬럼`"
                  @change="refreshPreview"
                />
                <select
                  v-else
                  v-model="rowFor(field).source_column"
                  class="form-select form-select-sm"
                  :aria-label="`${field.label} 원본 컬럼`"
                  @change="refreshPreview"
                >
                  <option value="">(매핑 안 함)</option>
                  <option v-for="column in sourceColumns" :key="column" :value="column">
                    {{ column }}
                  </option>
                </select>
              </td>
              <td>
                <input v-model.trim="rowFor(field).unit_label" class="form-control form-control-sm" :aria-label="`${field.label} 단위`" />
              </td>
              <td>
                <input
                  v-model.number="rowFor(field).scale_factor"
                  type="number"
                  step="any"
                  class="form-control form-control-sm"
                  :aria-label="`${field.label} 계수`"
                  @change="refreshPreview"
                />
              </td>
              <td>
                <input
                  v-model.number="rowFor(field).offset"
                  type="number"
                  step="any"
                  class="form-control form-control-sm"
                  :aria-label="`${field.label} 오프셋`"
                  @change="refreshPreview"
                />
              </td>
              <td>
                <div v-if="field.key === 'duct_burner_on'" class="d-flex gap-2">
                  <select v-model="rowFor(field).bool_rule" class="form-select form-select-sm" aria-label="덕트버너 해석 규칙">
                    <option value="BOOL">참/거짓 문자열</option>
                    <option value="THRESHOLD">임계값 초과 시 ON</option>
                  </select>
                  <input
                    v-if="rowFor(field).bool_rule === 'THRESHOLD'"
                    v-model.number="rowFor(field).bool_threshold"
                    type="number"
                    step="any"
                    class="form-control form-control-sm"
                    aria-label="ON 판정 임계값"
                  />
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-if="error" class="alert alert-danger py-2 small" role="alert">{{ error.message }}</div>

      <button class="btn btn-primary mb-4" @click="save">매핑 저장</button>

      <!-- 미리보기 (specs/02 §5.4) -->
      <div v-if="preview?.rows?.length" class="card mb-4">
        <div class="card-body">
          <h3 class="h6 mb-3">변환 미리보기 (상위 {{ preview.rows.length }}행)</h3>
          <div v-if="preview.missing_source_columns.length" class="alert alert-warning py-2 small">
            파일에 없는 원본 컬럼: {{ preview.missing_source_columns.join(', ') }}
          </div>
          <div class="table-responsive">
            <table class="table table-sm table-bordered mb-0">
              <thead>
                <tr><th v-for="key in Object.keys(preview.rows[0])" :key="key">{{ key }}</th></tr>
              </thead>
              <tbody>
                <tr v-for="(row, i) in preview.rows" :key="i">
                  <td v-for="(value, key) in row" :key="key" class="small">{{ value ?? '–' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- 변경 이력 (specs/02 §5.5) -->
      <div v-if="versions.length" class="card">
        <div class="card-body">
          <h3 class="h6 mb-3">변경 이력</h3>
          <table class="table table-sm mb-0">
            <thead>
              <tr><th scope="col">버전</th><th scope="col">변경자</th><th scope="col">일시</th><th scope="col" class="text-end">항목 수</th></tr>
            </thead>
            <tbody>
              <tr v-for="v in versions" :key="v.id">
                <td>v{{ v.version }}</td>
                <td>{{ v.created_by_name ?? '–' }}</td>
                <td class="small">{{ formatDateTime(v.created_at) }}</td>
                <td class="text-end">{{ v.snapshot.length }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </div>
</template>
