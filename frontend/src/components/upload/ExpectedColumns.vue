<script setup>
import { computed, ref, watch } from 'vue'

import * as unitsApi from '@/api/units'
import { useAuthStore } from '@/stores/auth'

/**
 * 선택한 호기가 기대하는 컬럼명 (specs/03 §2.2).
 *
 * 시스템은 호기별 매핑에 등록된 원본 컬럼명을 그대로 찾는다. 이름이 한 글자라도 다르면
 * 검증에서 MISSING_SOURCE_COLUMN 으로 적재가 막히는데, 그 사실을 파일을 올린 뒤에야
 * 알게 된다. 올리기 전에 헤더를 맞출 수 있도록 미리 보여준다.
 */
const props = defineProps({
  unitId: { type: Number, default: null },
})

const auth = useAuthStore()

const fields = ref([])
const mappings = ref([])
const loadError = ref(false)
const loading = ref(false)

// 표준 항목 정의는 호기와 무관하므로 한 번만 읽는다.
let fieldsLoaded = null
function loadFields() {
  fieldsLoaded ??= unitsApi.fetchStandardFields().then(({ data }) => {
    fields.value = data.results ?? data
  })
  return fieldsLoaded
}

let seq = 0
async function load(unitId) {
  const mine = ++seq
  mappings.value = []
  loadError.value = false
  if (!unitId) return
  loading.value = true
  try {
    const [, { data }] = await Promise.all([loadFields(), unitsApi.fetchColumnMappings(unitId)])
    if (mine === seq) mappings.value = data.mappings
  } catch {
    if (mine === seq) loadError.value = true
  } finally {
    if (mine === seq) loading.value = false
  }
}

watch(() => props.unitId, load, { immediate: true })

/**
 * 표에 쓸 행. 매핑된 항목만 보여준다 — 매핑하지 않은 항목은 파일에 있어도 무시되므로
 * 사용자가 신경 쓸 필요가 없다. 대체 항목(유량·차압 계열)은 이 호기가 그것으로 필수를
 * 채우므로 필수로 표시한다.
 */
const rows = computed(() => {
  const meta = Object.fromEntries(fields.value.map((f) => [f.key, f]))
  const order = Object.fromEntries(fields.value.map((f, i) => [f.key, i]))
  return mappings.value
    .map((m) => {
      const f = meta[m.standard_field]
      return {
        key: m.standard_field,
        label: f?.label ?? m.standard_field,
        column: m.source_column,
        required: f ? f.requirement !== 'OPTIONAL' : true,
      }
    })
    .sort((a, b) => Number(b.required) - Number(a.required) || order[a.key] - order[b.key])
})
</script>

<template>
  <div v-if="unitId" class="card mb-3">
    <div class="card-body">
      <h2 class="h6 mb-2">업로드 전 확인 — 이 호기가 찾는 컬럼명</h2>
      <p class="small text-secondary mb-3">
        파일 첫 줄(헤더)에 아래 이름이 <strong>그대로</strong> 있어야 합니다.
        띄어쓰기·괄호·단위 표기가 하나라도 다르면 해당 컬럼을 찾지 못해 <strong>적재가 막힙니다.</strong>
        표에 없는 컬럼은 파일에 있어도 무시됩니다.
      </p>

      <p v-if="loading" class="small text-secondary mb-3">컬럼 정보를 불러오는 중…</p>
      <p v-else-if="loadError" class="small text-warning mb-3">컬럼 정보를 불러오지 못했습니다.</p>

      <table v-else-if="rows.length" class="table table-sm align-middle mb-3">
        <thead>
          <tr>
            <th scope="col" style="width: 5rem">구분</th>
            <th scope="col">항목</th>
            <th scope="col">파일의 컬럼명</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="row.key">
            <td>
              <span class="badge" :class="row.required ? 'text-bg-primary' : 'text-bg-light'">
                {{ row.required ? '필수' : '선택' }}
              </span>
            </td>
            <td class="small">{{ row.label }}</td>
            <td><code>{{ row.column }}</code></td>
          </tr>
        </tbody>
      </table>

      <ul class="small text-secondary mb-0 ps-3">
        <li><strong>선택</strong> 항목도 매핑돼 있으면 파일에 컬럼이 있어야 합니다. 없으면 필수와 똑같이 적재가 막힙니다.</li>
        <li>
          값이 비어 있거나 숫자가 아닌 칸(<code>Bad</code>, <code>N/A</code> 등)은 적재는 되지만
          <strong>그 시각은 분석에서 제외</strong>됩니다. 필수 항목에 빈 칸이 많으면 분석할 데이터가 부족해질 수 있습니다.
        </li>
        <li v-if="auth.isAdmin">
          파일의 컬럼명이 바뀌었다면
          <RouterLink :to="{ name: 'admin-column-mapping' }">컬럼 매핑</RouterLink>에서 새 이름으로 바꾼 뒤 올리세요.
        </li>
        <li v-else>파일의 컬럼명이 바뀌었다면 관리자에게 컬럼 매핑 변경을 요청하세요.</li>
      </ul>
    </div>
  </div>
</template>
