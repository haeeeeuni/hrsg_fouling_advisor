<script setup>
import { onMounted, ref, watch } from 'vue'

import { fetchAutoRecalc, saveAutoRecalc } from '@/api/optional'
import { useToast } from '@/composables/useToast'

const props = defineProps({
  unitId: { type: Number, required: true },
})

const toast = useToast()
const form = ref(null)
const saving = ref(false)
const errors = ref({})

async function load() {
  errors.value = {}
  const { data } = await fetchAutoRecalc(props.unitId)
  form.value = { ...data }
}

async function onSave() {
  saving.value = true
  errors.value = {}
  try {
    const { data } = await saveAutoRecalc(props.unitId, {
      enabled: form.value.enabled,
      trigger: form.value.trigger,
      schedule_cron: form.value.schedule_cron,
      period_mode: form.value.period_mode,
      rolling_months: form.value.rolling_months,
      retrain_model: form.value.retrain_model,
      notify_on_grade_change: form.value.notify_on_grade_change,
    })
    form.value = { ...data }
    toast.push('자동 재계산 설정을 저장했습니다.', 'success')
  } catch (err) {
    errors.value = err.response?.data?.error?.details ?? {}
    toast.push(err.response?.data?.error?.message ?? '저장하지 못했습니다.', 'danger')
  } finally {
    saving.value = false
  }
}

onMounted(load)
watch(() => props.unitId, load)
</script>

<template>
  <div v-if="form" class="card">
    <div class="card-header py-2">
      <strong class="small">자동 재계산</strong>
    </div>
    <div class="card-body">
      <div class="form-check form-switch mb-3">
        <input
          id="autoRecalcEnabled"
          v-model="form.enabled"
          class="form-check-input"
          type="checkbox"
        />
        <label class="form-check-label" for="autoRecalcEnabled">자동 재계산 사용</label>
      </div>

      <div class="row g-3">
        <div class="col-md-6">
          <label for="autoTrigger" class="form-label small">실행 시점</label>
          <select id="autoTrigger" v-model="form.trigger" class="form-select form-select-sm">
            <option value="ON_UPLOAD">데이터 적재 완료 시</option>
            <option value="SCHEDULE">정해진 주기</option>
          </select>
        </div>

        <div v-if="form.trigger === 'SCHEDULE'" class="col-md-6">
          <label for="autoCron" class="form-label small">주기(cron)</label>
          <input
            id="autoCron"
            v-model="form.schedule_cron"
            class="form-control form-control-sm"
            :class="{ 'is-invalid': errors.schedule_cron }"
            placeholder="0 3 * * 1"
          />
          <div v-if="errors.schedule_cron" class="invalid-feedback">
            {{ errors.schedule_cron[0] }}
          </div>
        </div>

        <div class="col-md-6">
          <label for="autoPeriod" class="form-label small">분석 기간 산정</label>
          <select id="autoPeriod" v-model="form.period_mode" class="form-select form-select-sm">
            <option value="ROLLING">최근 N개월(이동 창)</option>
            <option value="EXTEND">기준 분석 시작일 고정, 끝만 연장</option>
          </select>
        </div>

        <div v-if="form.period_mode === 'ROLLING'" class="col-md-6">
          <label for="autoMonths" class="form-label small">최근 개월</label>
          <input
            id="autoMonths"
            v-model.number="form.rolling_months"
            type="number"
            min="1"
            max="120"
            class="form-control form-control-sm"
          />
        </div>
      </div>

      <hr />

      <div class="form-check mb-2">
        <input
          id="autoNotify"
          v-model="form.notify_on_grade_change"
          class="form-check-input"
          type="checkbox"
        />
        <label class="form-check-label small" for="autoNotify">
          오염 등급이 올라가면 알림 생성
        </label>
      </div>

      <div class="form-check mb-3">
        <input
          id="autoRetrain"
          v-model="form.retrain_model"
          class="form-check-input"
          type="checkbox"
        />
        <label class="form-check-label small" for="autoRetrain">
          기대값 모델도 자동으로 재학습
        </label>
        <p class="form-text mb-0">
          오염이 진행된 구간으로 학습하면 기준 자체가 오염되므로 기본값은 꺼짐입니다.
        </p>
      </div>

      <p class="text-muted small">
        자동 재계산은 기준 분석의 설정값 스냅샷을 그대로 사용하므로, 결과 변화가 설정 변경이 아닌
        데이터 변화에서만 나옵니다.
      </p>

      <button class="btn btn-sm btn-primary" type="button" :disabled="saving" @click="onSave">
        {{ saving ? '저장 중…' : '저장' }}
      </button>
    </div>
  </div>
</template>
