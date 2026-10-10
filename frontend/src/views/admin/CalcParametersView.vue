<script setup>
/**
 * 계산 파라미터 (specs/06 REF-5). 값을 바꾸면 행을 고치지 않고 새 버전을 만든다 — 이전 결과의
 * 파라미터 버전이 계속 뜻을 가진다. 항목 이름·범위는 서버 정의를 받아 그린다(프론트에 계수 이름을 두지 않는다).
 * 관리자가 바꿀 수 있는 것은 계수다. 식의 구조는 코드이며 실무 확정 후 개발자가 교체한다.
 */
import { computed, onMounted, ref } from 'vue'

import * as api from '@/api/reference'
import ErrorAlert from '@/components/admin/ErrorAlert.vue'
import { useToast } from '@/composables/useToast'
import { formatDateTime, formatMw, formatWonShort } from '@/utils/format'

const toast = useToast()

const GROUP_LABELS = { LOSS: '손실 모델 (비공개)', PINCH: '핀치·어프로치 판정 기준 (공개)' }

const definitions = ref([])
const versions = ref([])
const draft = ref({})
const note = ref('')
const loaded = ref(false)
const error = ref(null)
const preview = ref(null)
const busy = ref(false)

const active = computed(() => versions.value.find((v) => v.is_active) ?? null)
const groups = computed(() =>
  Object.entries(GROUP_LABELS).map(([code, label]) => ({
    code,
    label,
    items: definitions.value.filter((d) => d.group === code),
  })),
)
const changedKeys = computed(() =>
  definitions.value
    .filter((d) => JSON.stringify(draft.value[d.key]) !== JSON.stringify(active.value?.params[d.key]))
    .map((d) => d.key),
)

onMounted(load)

async function load() {
  try {
    const { data } = await api.fetchParameterSets()
    definitions.value = data.definitions
    versions.value = data.results
    resetDraft()
  } catch (err) {
    error.value = err.parsed
  } finally {
    loaded.value = true
  }
}

/** 깊은 복사. 반응형 프록시는 structuredClone 이 거부하므로(DataCloneError) JSON 으로 복사한다. */
const clone = (value) => JSON.parse(JSON.stringify(value))

function resetDraft() {
  draft.value = clone(active.value?.params ?? Object.fromEntries(definitions.value.map((d) => [d.key, d.default])))
  preview.value = null
  error.value = null
}

async function runPreview() {
  error.value = null
  try {
    preview.value = (await api.previewParameters(draft.value)).data
  } catch (err) {
    preview.value = null
    error.value = err.parsed
  }
}

async function saveVersion() {
  if (busy.value || !changedKeys.value.length) return
  if (!window.confirm(`새 버전을 만들어 바로 활성화할까요? (${changedKeys.value.length}개 항목 변경)`)) return
  busy.value = true
  error.value = null
  try {
    const { data } = await api.createParameterSet(draft.value, note.value)
    note.value = ''
    toast.push(`${data.version_label} 을(를) 만들고 활성화했습니다. 다음 계산부터 적용됩니다.`, 'success')
    await load()
  } catch (err) {
    error.value = err.parsed
  } finally {
    busy.value = false
  }
}

async function activate(version) {
  if (!window.confirm(`${version.version_label} 로 되돌릴까요?`)) return
  try {
    await api.activateParameterSet(version.id)
    toast.push(`${version.version_label} 을(를) 활성화했습니다.`, 'success')
    await load()
  } catch (err) {
    toast.push(err.parsed?.message ?? '되돌리지 못했습니다.', 'danger')
  }
}

function bestMethod(result) {
  return result.methods[0]
}
</script>

<template>
  <div>
    <div v-if="!loaded" class="text-center py-4">
      <div class="spinner-border text-primary" role="status"><span class="visually-hidden">불러오는 중</span></div>
    </div>

    <template v-else>
      <div class="alert alert-warning small py-2" role="note">
        현재 계수는 이전 앱의 편익 모델에서 가져온 <strong>임시값</strong>입니다. 실적 기반 값으로 교체하세요.
        손실 모델 계수는 사용자 화면·응답에 나오지 않습니다.
      </div>

      <div class="row g-4">
        <div class="col-12 col-xl-7">
          <form class="card" novalidate @submit.prevent="saveVersion">
            <div class="card-body">
              <h2 class="h6 mb-1">값 편집</h2>
              <p class="small text-secondary">현재 활성 버전: <strong data-testid="active-version">{{ active?.version_label ?? '없음' }}</strong></p>

              <fieldset v-for="group in groups" :key="group.code" class="mb-3">
                <legend class="fs-6 fw-semibold">{{ group.label }}</legend>
                <div v-for="item in group.items" :key="item.key" class="row g-2 align-items-center py-1 border-bottom">
                  <div class="col-12 col-md-6">
                    <label :for="`param-${item.key}`" class="form-label small mb-0">
                      {{ item.label }} <span v-if="item.unit" class="text-secondary fw-normal">({{ item.unit }})</span>
                      <span v-if="changedKeys.includes(item.key)" class="badge text-bg-warning ms-1">변경</span>
                    </label>
                    <div class="small text-secondary">{{ item.description }}</div>
                  </div>
                  <div class="col-12 col-md-6">
                    <div v-if="item.kind === 'RANGE'" class="input-group input-group-sm">
                      <input
                        :id="`param-${item.key}`"
                        v-model.number="draft[item.key][0]"
                        type="number"
                        step="any"
                        class="form-control"
                        :aria-label="`${item.label} 하한`"
                      />
                      <span class="input-group-text">~</span>
                      <input
                        v-model.number="draft[item.key][1]"
                        type="number"
                        step="any"
                        class="form-control"
                        :aria-label="`${item.label} 상한`"
                      />
                    </div>
                    <input
                      v-else
                      :id="`param-${item.key}`"
                      v-model.number="draft[item.key]"
                      type="number"
                      step="any"
                      class="form-control form-control-sm"
                    />
                    <div class="form-text">허용 {{ item.min_value ?? '–' }} ~ {{ item.max_value ?? '–' }}</div>
                  </div>
                </div>
              </fieldset>

              <label for="param-note" class="form-label small">변경 사유</label>
              <input id="param-note" v-model.trim="note" class="form-control form-control-sm mb-3" placeholder="예: 2025년 세정 실적 반영" />

              <ErrorAlert :error="error" />

              <div class="d-flex flex-wrap gap-2">
                <button class="btn btn-sm btn-outline-secondary" type="button" @click="runPreview">미리보기</button>
                <button class="btn btn-sm btn-primary" type="submit" :disabled="busy || !changedKeys.length">
                  새 버전으로 저장 ({{ changedKeys.length }}개 변경)
                </button>
                <button class="btn btn-sm btn-link" type="button" @click="resetDraft">편집 취소</button>
              </div>
            </div>
          </form>
        </div>

        <div class="col-12 col-xl-5">
          <div v-if="preview" class="card mb-3" data-testid="preview">
            <div class="card-body">
              <h2 class="h6">미리보기 — 같은 예시 입력의 결과</h2>
              <p class="small text-secondary">
                {{ preview.example.gt_model }}, 배압 +{{ preview.example.backpressure_rise_kpa }} kPa,
                굴뚝 +{{ preview.example.stack_temp_rise_c }} ℃, SMP {{ preview.example.smp_won_per_kwh }} 원/kWh
              </p>
              <table class="table table-sm">
                <thead>
                  <tr><th scope="col"></th><th scope="col" class="text-end">현재 {{ preview.current.param_version }}</th><th scope="col" class="text-end">변경안</th></tr>
                </thead>
                <tbody>
                  <tr>
                    <th scope="row" class="fw-normal">손실 출력</th>
                    <td class="text-end">{{ formatMw(preview.current.power_loss_total_mw) }}</td>
                    <td class="text-end">{{ formatMw(preview.candidate.power_loss_total_mw) }}</td>
                  </tr>
                  <tr>
                    <th scope="row" class="fw-normal">일 손실</th>
                    <td class="text-end">{{ formatWonShort(preview.current.daily_loss_won) }}</td>
                    <td class="text-end">{{ formatWonShort(preview.candidate.daily_loss_won) }}</td>
                  </tr>
                  <tr>
                    <th scope="row" class="fw-normal">순편익 최대 공법</th>
                    <td class="text-end">{{ bestMethod(preview.current).name }}<br /><span class="small">{{ formatWonShort(bestMethod(preview.current).net_benefit_won) }}</span></td>
                    <td class="text-end">{{ bestMethod(preview.candidate).name }}<br /><span class="small">{{ formatWonShort(bestMethod(preview.candidate).net_benefit_won) }}</span></td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <div class="card">
            <div class="card-body">
              <h2 class="h6">버전 이력</h2>
              <ul class="list-unstyled mb-0">
                <li v-for="version in versions" :key="version.id" class="d-flex justify-content-between align-items-start gap-2 py-2 border-bottom">
                  <div>
                    <strong>{{ version.version_label }}</strong>
                    <span v-if="version.is_active" class="badge text-bg-primary ms-1">활성</span>
                    <span v-if="version.is_seed" class="badge text-bg-warning ms-1">시드값</span>
                    <div class="small text-secondary">{{ version.created_by_name || '시드' }} · {{ formatDateTime(version.created_at) }}</div>
                    <div v-if="version.note" class="small">{{ version.note }}</div>
                  </div>
                  <button v-if="!version.is_active" class="btn btn-sm btn-outline-secondary" type="button" @click="activate(version)">
                    이 버전으로 되돌리기
                  </button>
                </li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
