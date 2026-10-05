<script setup>
import { computed, onMounted, ref } from 'vue'

import * as uploadsApi from '@/api/uploads'
import ExpectedColumns from '@/components/upload/ExpectedColumns.vue'
import FileDropzone from '@/components/upload/FileDropzone.vue'
import NewUnitSetup from '@/components/upload/NewUnitSetup.vue'
import ValidationReport from '@/components/upload/ValidationReport.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import { useJobPolling } from '@/composables/useJobPolling'
import { useToast } from '@/composables/useToast'
import { useUnitsStore } from '@/stores/units'
import { formatCount, formatDateTime } from '@/utils/format'

const units = useUnitsStore()
const toast = useToast()

/**
 * 업로드는 두 갈래다 (specs/03 §2.1).
 *  EXISTING : 매핑이 끝난 호기에 데이터를 덧붙인다 — 대부분의 경우
 *  NEW      : 아직 매핑이 없는 호기. 등록·매핑을 먼저 해야 해서 안내가 필요하다
 * 업로드 가능한 호기가 하나도 없으면 새 호기 쪽으로 시작한다.
 */
const mode = ref('EXISTING')

const file = ref(null)
const uploadPercent = ref(0)
const batchId = ref(null)
const report = ref(null)
const duplicatePolicy = ref('SKIP')
const busy = ref(false)
const error = ref(null)
const history = ref([])

// 페이지를 이탈했다 돌아와도 진행 상태가 복원된다 (AC-16-4).
const validateJob = useJobPolling({ key: 'upload.validate' })
const commitJob = useJobPolling({ key: 'upload.commit' })

const canCommit = computed(
  () => report.value?.is_loadable && batchId.value && !busy.value,
)

onMounted(async () => {
  await units.fetchUnits()
  if (!units.uploadableUnits.length) mode.value = 'NEW'
  await loadHistory()
  const resumed = validateJob.resume()
  if (resumed) {
    busy.value = true
    const outcome = await resumed
    if (outcome.status === 'SUCCESS') report.value = outcome.result
    busy.value = false
  }
})

async function useReadyUnit(unitId) {
  units.selectUnit(unitId)
  mode.value = 'EXISTING'
  await loadHistory()
}

async function loadHistory() {
  if (!units.selectedUnitId) return
  const { data } = await uploadsApi.fetchUploads({
    unit_id: units.selectedUnitId,
    page_size: 10,
  })
  history.value = data.results ?? data
}

function onSelectFile(selected) {
  file.value = selected
  report.value = null
  batchId.value = null
  error.value = null
}

async function runValidate(confirmDuplicateFile = false) {
  if (!file.value || !units.selectedUnitId || busy.value) return
  busy.value = true
  error.value = null
  report.value = null
  uploadPercent.value = 0

  try {
    const { data } = await uploadsApi.validateOperation(
      { unitId: units.selectedUnitId, file: file.value, confirmDuplicateFile },
      (percent) => (uploadPercent.value = percent),
    )
    batchId.value = data.batch_id
    const outcome = await validateJob.start(data.job_id)
    if (outcome.status === 'SUCCESS') {
      report.value = outcome.result
    } else {
      error.value = outcome.error
    }
  } catch (err) {
    const parsed = err.parsed ?? { code: '', message: '검증에 실패했습니다.' }
    if (parsed.code === 'DUPLICATE_FILE') {
      if (window.confirm(`${parsed.message}\n계속 진행할까요?`)) {
        busy.value = false
        return runValidate(true)
      }
    }
    error.value = parsed
  } finally {
    busy.value = false
  }
}

async function runCommit() {
  if (!canCommit.value) return
  busy.value = true
  error.value = null
  try {
    const { data } = await uploadsApi.commitUpload(batchId.value, duplicatePolicy.value)
    const outcome = await commitJob.start(data.job_id)
    if (outcome.status === 'SUCCESS') {
      toast.push(`${formatCount(outcome.result.row_loaded)}행을 적재했습니다.`, 'success')
      file.value = null
      report.value = null
      batchId.value = null
      await loadHistory()
    } else {
      error.value = outcome.error
    }
  } catch (err) {
    error.value = err.parsed ?? { message: '적재에 실패했습니다.' }
  } finally {
    busy.value = false
  }
}

async function onCancel() {
  if (!batchId.value) return
  await uploadsApi.cancelUpload(batchId.value)
  file.value = null
  report.value = null
  batchId.value = null
  toast.push('검증 결과를 폐기했습니다.', 'info')
}
</script>

<template>
  <div>
    <!-- 두 갈래 (specs/03 §2.1) -->
    <ul class="nav nav-tabs mb-3" role="tablist">
      <li class="nav-item" role="presentation">
        <button
          type="button"
          class="nav-link"
          :class="{ active: mode === 'EXISTING' }"
          :aria-selected="mode === 'EXISTING'"
          role="tab"
          :disabled="busy"
          @click="mode = 'EXISTING'"
        >
          기존 호기에 데이터 추가
          <span class="badge text-bg-secondary ms-1">{{ units.uploadableUnits.length }}</span>
        </button>
      </li>
      <li class="nav-item" role="presentation">
        <button
          type="button"
          class="nav-link"
          :class="{ active: mode === 'NEW' }"
          :aria-selected="mode === 'NEW'"
          role="tab"
          :disabled="busy"
          @click="mode = 'NEW'"
        >
          새 호기 데이터 올리기
        </button>
      </li>
    </ul>

    <NewUnitSetup
      v-if="mode === 'NEW'"
      :units="units.list"
      @select-ready="useReadyUnit"
    />

    <!-- 호기 목록을 읽기 전에는 "업로드 가능한 호기가 없습니다" 가 잠깐 깜빡인다. 읽는 동안은 로딩만 보인다. -->
    <LoadingSpinner v-else-if="!units.loaded" label="호기 목록을 불러오는 중" />

    <div v-else-if="!units.uploadableUnits.length" class="card">
      <div class="card-body">
        <EmptyState
          title="업로드 가능한 호기가 없습니다."
          description="호기를 등록하고 컬럼 매핑을 마쳐야 업로드할 수 있습니다. 위의 '새 호기 데이터 올리기' 를 눌러 남은 단계를 확인하세요."
          icon="bi-hdd-stack"
        >
          <template #action>
            <button type="button" class="btn btn-primary btn-sm" @click="mode = 'NEW'">
              남은 단계 보기
            </button>
          </template>
        </EmptyState>
      </div>
    </div>

    <template v-else>
      <div class="card mb-3">
        <div class="card-body">
          <div class="row g-3 align-items-end">
            <div class="col-12 col-md-5">
              <label for="unitSelect" class="form-label">호기</label>
              <select
                id="unitSelect"
                class="form-select"
                :value="units.selectedUnitId"
                :disabled="busy"
                @change="units.selectUnit(Number($event.target.value)); loadHistory()"
              >
                <option v-for="unit in units.uploadableUnits" :key="unit.id" :value="unit.id">
                  {{ unit.code }} — {{ unit.name }}
                </option>
              </select>
            </div>
            <div class="col-12 col-md-7">
              <FileDropzone :disabled="busy" @select="onSelectFile" />
            </div>
          </div>

          <div v-if="file" class="d-flex align-items-center gap-3 mt-3">
            <span class="small">
              <i class="bi bi-file-earmark-spreadsheet me-1" aria-hidden="true"></i>
              {{ file.name }}
            </span>
            <button class="btn btn-primary btn-sm" :disabled="busy" @click="runValidate()">
              <span v-if="busy" class="spinner-border spinner-border-sm me-2"></span>
              검증
            </button>
          </div>

          <div v-if="busy" class="mt-3">
            <div class="progress" style="height: 0.5rem">
              <div
                class="progress-bar progress-bar-striped progress-bar-animated"
                :style="{ width: `${validateJob.progress.value || uploadPercent}%` }"
              ></div>
            </div>
            <p class="small text-secondary mt-1 mb-0">
              {{ validateJob.stage.value || '파일 전송 중' }}
            </p>
          </div>

          <div v-if="error" class="alert alert-danger mt-3 py-2 small" role="alert">
            {{ error.message }}
          </div>
        </div>
      </div>

      <!-- 파일을 고르기 전에 헤더를 맞출 수 있게 보여준다. 적재가 막혔을 때도 남겨 둔다 —
           컬럼명이 달라 막힌 경우 이 표가 바로 고칠 방법이다. -->
      <ExpectedColumns v-if="!report || !report.is_loadable" :unit-id="units.selectedUnitId" />

      <div v-if="report" class="card mb-3">
        <div class="card-body">
          <h2 class="h6 mb-3">검증 결과</h2>
          <ValidationReport :report="report" />

          <div class="d-flex align-items-end gap-3 mt-3">
            <div>
              <label for="dupPolicy" class="form-label small">중복 시각 처리</label>
              <select id="dupPolicy" v-model="duplicatePolicy" class="form-select form-select-sm">
                <option value="SKIP">건너뛰기</option>
                <option value="OVERWRITE">덮어쓰기</option>
              </select>
            </div>
            <button class="btn btn-primary" :disabled="!canCommit" @click="runCommit">
              <span v-if="busy" class="spinner-border spinner-border-sm me-2"></span>
              적재
            </button>
            <button class="btn btn-outline-secondary" :disabled="busy" @click="onCancel">
              폐기
            </button>
          </div>
        </div>
      </div>

      <div class="card">
        <div class="card-body">
          <h2 class="h6 mb-3">업로드 이력</h2>
          <EmptyState v-if="!history.length" title="업로드 이력이 없습니다." icon="bi-clock-history" />
          <table v-else class="table table-sm align-middle mb-0">
            <thead>
              <tr>
                <th scope="col">일시</th>
                <th scope="col">파일</th>
                <th scope="col">기간</th>
                <th scope="col" class="text-end">적재</th>
                <th scope="col">상태</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in history" :key="row.id">
                <td class="small">{{ formatDateTime(row.uploaded_at) }}</td>
                <td class="small">{{ row.original_filename }}</td>
                <td class="small">
                  {{ formatDateTime(row.period_start) }} ~ {{ formatDateTime(row.period_end) }}
                </td>
                <td class="text-end small">{{ formatCount(row.row_loaded) }}</td>
                <td><span class="badge text-bg-secondary">{{ row.status }}</span></td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </div>
</template>
