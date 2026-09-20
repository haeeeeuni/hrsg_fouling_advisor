<script setup>
import { onMounted, reactive, ref } from 'vue'

import * as unitsApi from '@/api/units'
import AutoRecalcForm from '@/components/admin/AutoRecalcForm.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import { useToast } from '@/composables/useToast'
import { useUnitsStore } from '@/stores/units'
import { formatPower } from '@/utils/format'

const store = useUnitsStore()
const toast = useToast()

const editing = ref(null)
const error = ref(null)
const blank = {
  code: '',
  name: '',
  plant_name: '',
  gt_model: '',
  rated_power_mw: 160,
  rated_st_power_mw: 80,
  min_load_mw: 60,
  sampling_interval_min: 10,
  dp_source: 'DP',
  flow_source: 'EXHAUST_FLOW',
  is_active: true,
}
const form = reactive({ ...blank })

onMounted(() => store.fetchUnits(true))

function startCreate() {
  editing.value = 'new'
  error.value = null
  Object.assign(form, blank)
}

function startEdit(unit) {
  editing.value = unit.id
  error.value = null
  Object.assign(form, unit)
}

async function save() {
  error.value = null
  try {
    if (editing.value === 'new') await unitsApi.createUnit({ ...form })
    else await unitsApi.updateUnit(editing.value, { ...form })
    editing.value = null
    await store.fetchUnits(true)
    toast.push('저장했습니다.', 'success')
  } catch (err) {
    error.value = err.parsed
  }
}

async function remove(unit) {
  if (!window.confirm(`호기 "${unit.code} ${unit.name}" 을(를) 삭제할까요?`)) return
  try {
    await unitsApi.deleteUnit(unit.id)
    await store.fetchUnits(true)
    toast.push('삭제했습니다.', 'success')
  } catch (err) {
    toast.push(err.parsed?.message ?? '삭제할 수 없습니다.', 'danger')
  }
}
</script>

<template>
  <div>
    <div class="d-flex justify-content-between align-items-center mb-3">
      <h2 class="h6 mb-0">호기 목록</h2>
      <button class="btn btn-primary btn-sm" @click="startCreate">호기 추가</button>
    </div>

    <EmptyState
      v-if="!store.list.length"
      title="등록된 호기가 없습니다."
      description="호기를 추가한 뒤 컬럼 매핑을 설정하면 데이터를 업로드할 수 있습니다."
      icon="bi-hdd-stack"
    />

    <table v-else class="table table-sm align-middle">
      <thead>
        <tr>
          <th scope="col">코드</th>
          <th scope="col">호기명</th>
          <th scope="col" class="text-end">GT 정격</th>
          <th scope="col" class="text-end">최소 부하</th>
          <th scope="col">차압 기준</th>
          <th scope="col">매핑</th>
          <th scope="col">사용</th>
          <th scope="col"></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="unit in store.list" :key="unit.id">
          <td>{{ unit.code }}</td>
          <td>{{ unit.name }}</td>
          <td class="text-end">{{ formatPower(unit.rated_power_mw) }}</td>
          <td class="text-end">{{ formatPower(unit.min_load_mw) }}</td>
          <td class="small">{{ unit.dp_source === 'DP' ? '가스측 차압' : 'GT 배압 대체' }}</td>
          <td>
            <span
              class="badge"
              :class="unit.is_mapping_complete ? 'text-bg-success' : 'text-bg-warning'"
            >
              {{ unit.is_mapping_complete ? '완료' : '미완료' }}
            </span>
          </td>
          <td>
            <span class="badge" :class="unit.is_active ? 'text-bg-secondary' : 'text-bg-light'">
              {{ unit.is_active ? '사용' : '중지' }}
            </span>
          </td>
          <td class="text-end">
            <button class="btn btn-sm btn-outline-secondary me-1" @click="startEdit(unit)">수정</button>
            <button class="btn btn-sm btn-outline-danger" @click="remove(unit)">삭제</button>
          </td>
        </tr>
      </tbody>
    </table>

    <div v-if="editing" class="card mt-3">
      <div class="card-body">
        <h3 class="h6 mb-3">{{ editing === 'new' ? '호기 추가' : '호기 수정' }}</h3>
        <div class="row g-3">
          <div class="col-6 col-lg-3">
            <label for="code" class="form-label">호기 코드</label>
            <input id="code" v-model.trim="form.code" class="form-control" :disabled="editing !== 'new'" />
          </div>
          <div class="col-6 col-lg-3">
            <label for="name" class="form-label">호기명</label>
            <input id="name" v-model.trim="form.name" class="form-control" />
          </div>
          <div class="col-6 col-lg-3">
            <label for="plant" class="form-label">발전소명</label>
            <input id="plant" v-model.trim="form.plant_name" class="form-control" />
          </div>
          <div class="col-6 col-lg-3">
            <label for="gtModel" class="form-label">GT 기종</label>
            <input id="gtModel" v-model.trim="form.gt_model" class="form-control" />
          </div>
          <div class="col-6 col-lg-3">
            <label for="rated" class="form-label">GT 정격 출력 (MW)</label>
            <input id="rated" v-model.number="form.rated_power_mw" type="number" step="0.1" class="form-control" />
          </div>
          <div class="col-6 col-lg-3">
            <label for="ratedSt" class="form-label">ST 정격 출력 (MW)</label>
            <input id="ratedSt" v-model.number="form.rated_st_power_mw" type="number" step="0.1" class="form-control" />
          </div>
          <div class="col-6 col-lg-3">
            <label for="minLoad" class="form-label">최소 안정 부하 (MW)</label>
            <input id="minLoad" v-model.number="form.min_load_mw" type="number" step="0.1" class="form-control" />
          </div>
          <div class="col-6 col-lg-3">
            <label for="interval" class="form-label">데이터 주기 (분)</label>
            <input id="interval" v-model.number="form.sampling_interval_min" type="number" class="form-control" />
          </div>
          <div class="col-6 col-lg-3">
            <label for="dpSource" class="form-label">차압 기준</label>
            <select id="dpSource" v-model="form.dp_source" class="form-select">
              <option value="DP">가스측 차압 계측</option>
              <option value="BACKPRESSURE">GT 배압 대체</option>
            </select>
          </div>
          <div class="col-6 col-lg-3">
            <label for="flowSource" class="form-label">유량 기준</label>
            <select id="flowSource" v-model="form.flow_source" class="form-select">
              <option value="EXHAUST_FLOW">배기유량</option>
              <option value="FUEL_FLOW">연료유량</option>
              <option value="IGV">IGV 개도</option>
            </select>
          </div>
          <div class="col-6 col-lg-3 d-flex align-items-end">
            <div class="form-check">
              <input id="isActive" v-model="form.is_active" class="form-check-input" type="checkbox" />
              <label for="isActive" class="form-check-label">사용</label>
            </div>
          </div>
        </div>

        <div v-if="error" class="alert alert-danger py-2 small mt-3" role="alert">
          {{ error.message }}
          <ul v-if="error.details" class="mb-0 mt-1 ps-3">
            <li v-for="(messages, field) in error.details" :key="field">
              {{ field }}: {{ messages.join(', ') }}
            </li>
          </ul>
        </div>

        <div class="mt-3">
          <button class="btn btn-primary me-2" @click="save">저장</button>
          <button class="btn btn-outline-secondary" @click="editing = null">취소</button>
        </div>
      </div>
    </div>

    <!-- specs/19 §1 — 선택된 호기의 자동 재계산 설정 -->
    <div v-if="store.selectedUnitId" class="mt-4">
      <AutoRecalcForm :key="store.selectedUnitId" :unit-id="store.selectedUnitId" />
    </div>
  </div>
</template>
