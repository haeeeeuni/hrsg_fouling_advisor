<script setup>
/**
 * 계산기 (specs/05). 탭 3개가 같은 GT 모델·운전값을 공유한다.
 * 값을 바꾸면 300ms 뒤 서버에 계산을 요청한다 — 계산식이 비공개라 브라우저에서 계산하지 않는다(CALC-8).
 */
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import * as api from '@/api/calculator'
import LossResults from '@/components/calculator/LossResults.vue'
import MethodResults from '@/components/calculator/MethodResults.vue'
import NumberField from '@/components/calculator/NumberField.vue'
import PinchResults from '@/components/calculator/PinchResults.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import { useLatestRequest } from '@/composables/useLatestRequest'
import { decodeLoss, decodeStages, encodeLoss, encodeStages } from '@/utils/calcQuery'
import { formatDate } from '@/utils/format'

const TABS = [
  { key: 'loss', title: '손실·회수 효과', icon: 'bi-graph-down-arrow' },
  { key: 'methods', title: '공법별 비용 비교', icon: 'bi-bar-chart' },
  { key: 'pinch', title: '핀치·어프로치 점검', icon: 'bi-thermometer-half' },
]

const route = useRoute()
const router = useRouter()

const options = ref(null)
const optionsError = ref(null)
const tab = computed(() => (TABS.some((t) => t.key === route.params.tab) ? route.params.tab : 'loss'))

const form = reactive({
  gt_model_id: null,
  gt_power_mw: null,
  backpressure_kpa: null,
  clean_backpressure_kpa: null,
  exhaust_temp_c: null,
  stack_temp_c: null,
  clean_stack_temp_c: null,
  operating_hours_per_day: null,
  smp_won_per_kwh: null,
  cleaning_method_id: null,
})
/** SMP 를 직접 입력할지. 끄면 관리자가 등록한 최신값을 쓴다(specs/06 REF-4). */
const customSmp = ref(false)
const stages = ref([blankStage('HP')])

const loss = useLatestRequest((payload) => api.calculateLoss(payload).then((r) => r.data))
const methods = useLatestRequest((payload) => api.compareMethods(payload).then((r) => r.data))
const pinch = useLatestRequest((payload) => api.checkPinchApproach(payload).then((r) => r.data))
const active = computed(() => ({ loss, methods, pinch })[tab.value])

const selectedModel = computed(() => options.value?.gt_models.find((m) => m.id === form.gt_model_id) ?? null)

function blankStage(label = '') {
  return {
    label,
    drum_pressure_barg: null,
    evaporator_outlet_gas_temp_c: null,
    economizer_outlet_water_temp_c: null,
    design_pinch_c: null,
    design_approach_c: null,
  }
}

/** GT 모델을 바꾸면 설계값 기반 칸을 그 모델의 설계값으로 다시 채운다. */
function applyModelDefaults(model) {
  form.gt_power_mw = model.rated_gt_mw
  form.backpressure_kpa = model.design_backpressure_kpa
  form.clean_backpressure_kpa = model.design_backpressure_kpa
  form.exhaust_temp_c = model.design_exhaust_temp_c
  form.stack_temp_c = model.design_stack_temp_c
  form.clean_stack_temp_c = model.design_stack_temp_c
}

function onModelChange(event) {
  form.gt_model_id = Number(event.target.value)
  if (selectedModel.value) applyModelDefaults(selectedModel.value)
}

onMounted(async () => {
  try {
    const { data } = await api.fetchOptions()
    options.value = data
  } catch (err) {
    optionsError.value = err.parsed ?? { message: '계산기 정보를 불러오지 못했습니다.' }
    return
  }
  const fromUrl = decodeLoss(route.query)
  const model = options.value.gt_models.find((m) => m.id === fromUrl.gt_model_id) ?? options.value.gt_models[0]
  if (!model) return
  form.gt_model_id = model.id
  applyModelDefaults(model)
  form.operating_hours_per_day = options.value.defaults.operating_hours_per_day
  form.cleaning_method_id = options.value.defaults.cleaning_method_id
  // 링크에 담긴 값이 있으면 그 값이 우선한다.
  for (const [field, value] of Object.entries(fromUrl)) {
    if (value !== null && field !== 'gt_model_id') form[field] = value
  }
  customSmp.value = fromUrl.smp_won_per_kwh !== null || !options.value.smp
  const urlStages = decodeStages(route.query.ps)
  if (urlStages) stages.value = urlStages.map((s, i) => ({ ...s, label: ['HP', 'IP', 'LP'][i] }))
})

/** 빈 칸·숫자가 아닌 값은 요청하지 않고 그 칸에 바로 표시한다. 범위 검사는 서버가 한다. */
const REQUIRED_LOSS_FIELDS = [
  'gt_power_mw',
  'backpressure_kpa',
  'clean_backpressure_kpa',
  'exhaust_temp_c',
  'stack_temp_c',
  'clean_stack_temp_c',
  'operating_hours_per_day',
]

const clientErrors = computed(() => {
  const errors = {}
  for (const field of REQUIRED_LOSS_FIELDS) {
    if (form[field] === null || Number.isNaN(form[field])) errors[field] = '값을 입력해 주세요.'
  }
  if (customSmp.value && (form.smp_won_per_kwh === null || Number.isNaN(form.smp_won_per_kwh))) {
    errors.smp_won_per_kwh = 'SMP 를 입력해 주세요.'
  }
  return errors
})

const STAGE_REQUIRED = ['drum_pressure_barg', 'evaporator_outlet_gas_temp_c', 'economizer_outlet_water_temp_c']
const isBlankNumber = (v) => v === null || Number.isNaN(v)

/** 계산을 막는 압력단 오류. 아직 하나도 입력하지 않은 칸을 처음부터 빨갛게 보이지는 않는다(stageMessages). */
const stageErrors = computed(() =>
  stages.value.map((s) =>
    Object.fromEntries(STAGE_REQUIRED.filter((f) => isBlankNumber(s[f])).map((f) => [f, '값을 입력해 주세요.'])),
  ),
)
const stageMessages = computed(() =>
  stages.value.map((s, i) => (STAGE_REQUIRED.some((f) => !isBlankNumber(s[f])) ? stageErrors.value[i] : {})),
)

function lossPayload() {
  return { ...form, smp_won_per_kwh: customSmp.value ? form.smp_won_per_kwh : null }
}

function fieldError(field) {
  return clientErrors.value[field] || active.value.error.value?.details?.[field] || ''
}

function syncUrl() {
  const query = { ...encodeLoss(lossPayload()) }
  if (tab.value === 'pinch') query.ps = encodeStages(stages.value)
  router.replace({ query })
}

function recalculate() {
  if (!options.value || !form.gt_model_id) return
  if (tab.value === 'pinch') {
    if (stageErrors.value.some((e) => Object.keys(e).length)) return pinch.cancel()
    pinch.run({ stages: stages.value })
  } else {
    if (Object.keys(clientErrors.value).length) return active.value.cancel()
    active.value.run(lossPayload())
  }
  syncUrl()
}

watch([form, customSmp, stages], recalculate, { deep: true })
watch(tab, recalculate)

function setTab(key) {
  router.replace({ name: 'calculator', params: key === 'loss' ? {} : { tab: key }, query: route.query })
}

function addStage() {
  if (stages.value.length < 3) stages.value.push(blankStage(['HP', 'IP', 'LP'][stages.value.length]))
}

function removeStage(index) {
  stages.value.splice(index, 1)
}
</script>

<template>
  <div class="ui-container">
    <h1 class="h3 mb-1">계산기</h1>
    <p class="text-secondary">가스터빈 모델과 운전값을 넣으면 결과가 바로 다시 계산됩니다.</p>

    <div v-if="optionsError" class="alert alert-danger" role="alert">{{ optionsError.message }}</div>
    <div v-else-if="!options" class="text-center py-5">
      <div class="spinner-border text-primary" role="status"><span class="visually-hidden">불러오는 중</span></div>
    </div>
    <div v-else-if="!options.gt_models.length" class="card">
      <EmptyState
        title="등록된 GT 모델이 없습니다."
        description="관리자가 GT 운전 한계 참조표를 등록하면 계산기를 쓸 수 있습니다."
        icon="bi-calculator"
      />
    </div>

    <template v-else>
      <ul class="nav nav-tabs mb-3" role="tablist">
        <li v-for="item in TABS" :key="item.key" class="nav-item" role="presentation">
          <button
            class="nav-link"
            :class="{ active: tab === item.key }"
            type="button"
            role="tab"
            :aria-selected="tab === item.key ? 'true' : 'false'"
            @click="setTab(item.key)"
          >
            <i class="bi me-1" :class="item.icon" aria-hidden="true"></i>{{ item.title }}
          </button>
        </li>
      </ul>

      <div class="row g-4">
        <!-- 입력 -->
        <section class="col-12 col-lg-4" aria-label="입력">
          <div class="card">
            <div class="card-body">
              <div class="mb-3">
                <label for="cGtModel" class="form-label">GT 모델</label>
                <select id="cGtModel" class="form-select" :value="form.gt_model_id" @change="onModelChange">
                  <option v-for="model in options.gt_models" :key="model.id" :value="model.id">
                    {{ model.name }}<template v-if="model.is_placeholder"> (임시값)</template>
                  </option>
                </select>
                <div v-if="selectedModel" class="form-text">
                  정격 GT {{ selectedModel.rated_gt_mw }} MW
                  <template v-if="selectedModel.rated_st_mw">· ST {{ selectedModel.rated_st_mw }} MW</template>
                </div>
              </div>

              <template v-if="tab !== 'pinch'">
                <NumberField id="cPower" v-model="form.gt_power_mw" label="GT 출력" unit="MW" :error="fieldError('gt_power_mw')" />
                <div class="row g-2">
                  <div class="col-6">
                    <NumberField id="cBp" v-model="form.backpressure_kpa" label="현재 배압" unit="kPa" :error="fieldError('backpressure_kpa')" />
                  </div>
                  <div class="col-6">
                    <NumberField id="cCbp" v-model="form.clean_backpressure_kpa" label="청정 배압" unit="kPa" :error="fieldError('clean_backpressure_kpa')" />
                  </div>
                  <div class="col-6">
                    <NumberField id="cStk" v-model="form.stack_temp_c" label="현재 굴뚝 온도" unit="℃" :error="fieldError('stack_temp_c')" />
                  </div>
                  <div class="col-6">
                    <NumberField id="cCstk" v-model="form.clean_stack_temp_c" label="청정 굴뚝 온도" unit="℃" :error="fieldError('clean_stack_temp_c')" />
                  </div>
                  <div class="col-6">
                    <NumberField id="cExh" v-model="form.exhaust_temp_c" label="배기온도" unit="℃" :error="fieldError('exhaust_temp_c')" />
                  </div>
                  <div class="col-6">
                    <NumberField id="cHrs" v-model="form.operating_hours_per_day" label="일 운전 시간" unit="h" :error="fieldError('operating_hours_per_day')" />
                  </div>
                </div>

                <div class="mb-3">
                  <div class="form-check form-switch">
                    <input id="cCustomSmp" v-model="customSmp" class="form-check-input" type="checkbox" :disabled="!options.smp" />
                    <label for="cCustomSmp" class="form-check-label">SMP 직접 입력</label>
                  </div>
                  <NumberField
                    v-if="customSmp"
                    id="cSmp"
                    v-model="form.smp_won_per_kwh"
                    label="SMP"
                    unit="원/kWh"
                    :error="fieldError('smp_won_per_kwh')"
                  />
                  <p v-else class="small text-secondary mb-0" data-testid="registered-smp">
                    등록된 SMP {{ options.smp.value }} 원/kWh · 기준일 {{ formatDate(options.smp.as_of) }} · {{ options.smp.source }}
                    <span v-if="options.smp.is_estimate" class="badge text-bg-warning ms-1">추정</span>
                  </p>
                </div>

                <div v-if="tab === 'loss'" class="mb-1">
                  <label for="cMethod" class="form-label">세정 공법</label>
                  <select id="cMethod" v-model.number="form.cleaning_method_id" class="form-select">
                    <option v-for="method in options.cleaning_methods" :key="method.id" :value="method.id">
                      {{ method.name }}
                    </option>
                  </select>
                </div>
              </template>

              <template v-else>
                <fieldset v-for="(stage, index) in stages" :key="index" class="border rounded p-2 mb-3">
                  <legend class="float-none w-auto px-1 fs-6 fw-semibold mb-0">{{ stage.label || `${index + 1}단` }}</legend>
                  <NumberField :id="`pDrum${index}`" v-model="stage.drum_pressure_barg" label="드럼 압력" unit="bar(g)" :error="stageMessages[index].drum_pressure_barg" />
                  <NumberField
                    :id="`pGas${index}`"
                    v-model="stage.evaporator_outlet_gas_temp_c"
                    label="증발기 출구 가스 온도"
                    unit="℃"
                    :error="stageMessages[index].evaporator_outlet_gas_temp_c"
                  />
                  <NumberField
                    :id="`pWater${index}`"
                    v-model="stage.economizer_outlet_water_temp_c"
                    label="절탄기 출구 급수 온도"
                    unit="℃"
                    :error="stageMessages[index].economizer_outlet_water_temp_c"
                  />
                  <div class="row g-2">
                    <div class="col-6">
                      <NumberField :id="`pDp${index}`" v-model="stage.design_pinch_c" label="설계 핀치 (선택)" unit="℃" />
                    </div>
                    <div class="col-6">
                      <NumberField :id="`pDa${index}`" v-model="stage.design_approach_c" label="설계 어프로치 (선택)" unit="℃" />
                    </div>
                  </div>
                  <button v-if="stages.length > 1" type="button" class="btn btn-sm btn-outline-secondary" @click="removeStage(index)">
                    이 압력단 빼기
                  </button>
                </fieldset>
                <button v-if="stages.length < 3" type="button" class="btn btn-sm btn-outline-secondary" @click="addStage">
                  <i class="bi bi-plus-lg me-1" aria-hidden="true"></i>압력단 추가
                </button>
              </template>
            </div>
          </div>
        </section>

        <!-- 결과 -->
        <section class="col-12 col-lg-8" aria-label="결과" aria-live="polite">
          <div v-if="active.error.value && !Object.keys(active.error.value.details ?? {}).length" class="alert alert-danger" role="alert">
            {{ active.error.value.message }}
          </div>
          <div
            v-if="active.data.value"
            class="ui-result"
            :class="{ 'ui-result--stale': active.loading.value }"
            :aria-busy="active.loading.value ? 'true' : 'false'"
          >
            <LossResults v-if="tab === 'loss'" :data="active.data.value" />
            <MethodResults v-else-if="tab === 'methods'" :data="active.data.value" />
            <PinchResults v-else :data="active.data.value" />
          </div>
          <div v-else-if="tab === 'pinch' && !active.loading.value" class="card">
            <EmptyState
              title="압력단 값을 입력하세요"
              description="드럼 압력, 증발기 출구 가스 온도, 절탄기 출구 급수 온도를 넣으면 핀치·어프로치를 계산합니다."
              icon="bi-thermometer-half"
            />
          </div>
          <div v-else class="text-center py-5">
            <div class="spinner-border text-primary" role="status"><span class="visually-hidden">계산 중</span></div>
          </div>
        </section>
      </div>
    </template>
  </div>
</template>
