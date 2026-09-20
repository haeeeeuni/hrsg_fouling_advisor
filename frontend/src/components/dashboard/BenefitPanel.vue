<script setup>
import { computed, ref } from 'vue'

import { useToast } from '@/composables/useToast'
import { useAnalysisStore } from '@/stores/analysis'
import { formatCurrency, formatDate, formatPower } from '@/utils/format'

const props = defineProps({ benefit: { type: Object, default: null } })

const analysis = useAnalysisStore()
const toast = useToast()

const open = ref(false)
const busy = ref(false)
const error = ref(null)
const form = ref({})

// 이 분석에만 적용되는 임시값 (specs/09 §3.2)
const EDITABLE = [
  ['electricity_price', '전력 단가', '원/kWh'],
  ['cleaning_cost', '세정 1회 비용', '원'],
  ['outage_days', '세정 정지 일수', '일'],
  ['dp_power_loss_coeff', '배압 손실 계수', '%MW/kPa'],
  ['stack_temp_loss_coeff', '스택온도 손실 계수', '%MW(ST)/℃'],
  ['cleaning_recovery_ratio', '세정 후 회복률', '–'],
]

const params = computed(() => props.benefit?.params_snapshot ?? {})
const changed = computed(() =>
  EDITABLE.filter(([key]) => form.value[key] !== undefined && form.value[key] !== params.value[key])
    .map(([key]) => key),
)

function openPanel() {
  open.value = true
  error.value = null
  form.value = Object.fromEntries(EDITABLE.map(([key]) => [key, params.value[key]]))
}

async function apply() {
  busy.value = true
  error.value = null
  try {
    const payload = Object.fromEntries(changed.value.map((key) => [key, form.value[key]]))
    await analysis.recalculateBenefit(payload)
    toast.push('편익을 재계산했습니다. 관리자 기본값은 변경되지 않았습니다.', 'success')
    open.value = false
  } catch (err) {
    error.value = err.parsed ?? { message: '재계산에 실패했습니다.' }
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="card h-100">
    <div class="card-body">
      <div class="d-flex justify-content-between align-items-center mb-3">
        <h2 class="h6 mb-0">편익 상세</h2>
        <button v-if="benefit" class="btn btn-sm btn-outline-secondary" @click="openPanel">
          파라미터 조정
        </button>
      </div>

      <template v-if="benefit">
        <dl class="row small mb-0">
          <dt class="col-7 text-secondary fw-normal">현재 손실 출력</dt>
          <dd class="col-5 text-end mb-1">
            {{ formatPower(benefit.power_loss_total_mw) }}
            <span class="text-secondary">
              (GT {{ formatPower(benefit.power_loss_gt_mw) }} / ST {{ formatPower(benefit.power_loss_st_mw) }})
            </span>
          </dd>

          <dt class="col-7 text-secondary fw-normal">일일 손실 비용</dt>
          <dd class="col-5 text-end mb-1">{{ formatCurrency(benefit.daily_loss_cost, { withEok: false }) }}</dd>

          <dt class="col-7 text-secondary fw-normal">세정 비용 + 정지 손실</dt>
          <dd class="col-5 text-end mb-1">{{ formatCurrency(benefit.total_cleaning_cost) }}</dd>

          <dt class="col-7 text-secondary fw-normal">회수 편익(평가기간)</dt>
          <dd class="col-5 text-end mb-1">{{ formatCurrency(benefit.gross_benefit) }}</dd>

          <dt class="col-7 fw-semibold">순편익</dt>
          <dd class="col-5 text-end mb-1 fw-semibold" :class="benefit.net_benefit >= 0 ? 'text-success' : 'text-danger'">
            {{ formatCurrency(benefit.net_benefit) }}
          </dd>

          <dt class="col-7 text-secondary fw-normal">회수기간</dt>
          <dd class="col-5 text-end mb-1">
            {{ benefit.payback_days ? `${Math.round(benefit.payback_days)}일` : '–' }}
          </dd>

          <dt class="col-7 text-secondary fw-normal">지연 비용</dt>
          <dd class="col-5 text-end mb-1">{{ formatCurrency(benefit.daily_loss_cost, { withEok: false }) }}/일</dd>

          <dt class="col-7 text-secondary fw-normal">권고 세정 시점</dt>
          <dd class="col-5 text-end mb-0">
            {{ formatDate(benefit.recommended_cleaning_date) }}
            <span v-if="benefit.recommended_offset_days !== null" class="text-secondary">
              (D+{{ benefit.recommended_offset_days }})
            </span>
          </dd>
        </dl>

        <!-- 시나리오 비교 (specs/09 §4.6) -->
        <table class="table table-sm mt-3 mb-0">
          <caption class="visually-hidden">세정 시점 시나리오 비교</caption>
          <thead>
            <tr><th scope="col">시나리오</th><th scope="col" class="text-end">순편익</th></tr>
          </thead>
          <tbody>
            <tr v-for="row in benefit.scenarios" :key="row.scenario">
              <td class="small">
                {{ row.label }}
                <span v-if="row.offset_days !== null" class="text-secondary">(D+{{ row.offset_days }})</span>
              </td>
              <td class="small text-end">
                <template v-if="row.net_benefit !== null">{{ formatCurrency(row.net_benefit) }}</template>
                <span v-else class="text-secondary" :title="row.note">–</span>
              </td>
            </tr>
          </tbody>
        </table>

        <!-- 적용된 주요 가정을 각주로 표기한다 (specs/09 §9) -->
        <p class="small text-secondary mt-3 mb-0">
          가정: 전력단가 {{ params.electricity_price }}원/kWh ·
          배압 손실계수 {{ params.dp_power_loss_coeff }}%MW/kPa ·
          회복률 {{ params.cleaning_recovery_ratio }} ·
          평가기간 {{ params.evaluation_horizon_days }}일.
          계수 기반 추정치이므로 실적 데이터로 보정이 필요합니다.
        </p>

        <div v-if="benefit.warnings?.length" class="mt-2">
          <p v-for="w in benefit.warnings" :key="w.code" class="small text-warning mb-1">
            {{ w.message }}
          </p>
        </div>
      </template>

      <p v-else class="text-secondary small mb-0">분석을 실행하면 표시됩니다.</p>

      <!-- 임시 파라미터 조정 -->
      <div v-if="open" class="border-top mt-3 pt-3">
        <p class="small fw-semibold mb-2">
          파라미터 조정
          <span class="badge text-bg-info ms-1">이 분석에만 적용됨</span>
        </p>
        <div class="row g-2">
          <div v-for="[key, label, unit] in EDITABLE" :key="key" class="col-6">
            <label :for="`bp-${key}`" class="form-label small mb-0">
              {{ label }}
              <span class="text-secondary">({{ unit }})</span>
              <span v-if="changed.includes(key)" class="badge text-bg-warning ms-1">변경</span>
            </label>
            <input :id="`bp-${key}`" v-model.number="form[key]" type="number" step="any"
                   class="form-control form-control-sm" />
          </div>
        </div>

        <div v-if="error" class="alert alert-danger py-2 small mt-2 mb-0" role="alert">
          {{ error.message }}
        </div>

        <div class="mt-2">
          <button class="btn btn-sm btn-primary me-2" :disabled="busy || !changed.length" @click="apply">
            <span v-if="busy" class="spinner-border spinner-border-sm me-1"></span>
            재계산
          </button>
          <button class="btn btn-sm btn-outline-secondary" @click="open = false">닫기</button>
        </div>
      </div>
    </div>
  </div>
</template>
