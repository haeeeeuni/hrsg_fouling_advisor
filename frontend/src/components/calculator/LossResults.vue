<script setup>
/** 손실·회수 효과 결과 (specs/05 §3.3). 상태와 큰 숫자가 스크롤 없이 먼저 보이게 둔다. */
import { computed } from 'vue'

import BigNumber from '@/components/calculator/BigNumber.vue'
import HrsgDiagram from '@/components/calculator/HrsgDiagram.vue'
import LossBreakdownChart from '@/components/calculator/LossBreakdownChart.vue'
import ResultNotices from '@/components/calculator/ResultNotices.vue'
import StatusGauge from '@/components/calculator/StatusGauge.vue'
import StatusBadge from '@/components/common/StatusBadge.vue'
import { formatCurrency, formatKpa, formatMw, formatPayback, formatTemp, formatWonShort } from '@/utils/format'

const props = defineProps({
  data: { type: Object, required: true },
})

const STATE_LABEL = { NORMAL: '정상 운전', ALARM: '주의 — 경보 구간', TRIP: '위험 — 트립 구간' }

const results = computed(() => props.data.results)
const recovery = computed(() => props.data.results.recovery)
const variables = computed(() => Object.fromEntries(props.data.status.variables.map((v) => [v.key, v])))
</script>

<template>
  <div>
    <!-- 임시값·SMP 출처 안내는 결과보다 먼저 보이게 위에 둔다 (specs/12 §6). -->
    <ResultNotices class="mb-3" :meta="data.meta" />
    <div class="d-flex flex-wrap align-items-center gap-2 mb-3">
      <span class="text-secondary small">현재 상태</span>
      <StatusBadge
        :level="data.status.level"
        :label="STATE_LABEL[data.status.state]"
        size="lg"
        data-testid="overall-status"
      />
    </div>

    <div class="row g-3 mb-3">
      <div class="col-6 col-xl-3">
        <BigNumber
          label="예상 손실 (일)"
          :value="formatWonShort(results.daily_loss_won)"
          :detail="formatCurrency(results.daily_loss_won, { withEok: false })"
          testid="daily-loss"
        />
      </div>
      <div class="col-6 col-xl-3">
        <BigNumber label="예상 손실 (30일)" :value="formatWonShort(results.monthly_loss_won)" />
      </div>
      <div class="col-6 col-xl-3">
        <BigNumber
          :label="`회수 기간 (${recovery.name})`"
          :value="formatPayback(recovery.payback_days)"
          testid="payback"
        />
      </div>
      <div class="col-6 col-xl-3">
        <BigNumber label="세정 순편익 (평가 기간)" :value="formatWonShort(recovery.net_benefit_won)" testid="net-benefit" />
      </div>
    </div>

    <div class="row g-3 mb-3">
      <div class="col-6">
        <div class="card h-100"><div class="card-body p-2"><StatusGauge :variable="variables.backpressure" /></div></div>
      </div>
      <div class="col-6">
        <div class="card h-100"><div class="card-body p-2"><StatusGauge :variable="variables.exhaust_temp" /></div></div>
      </div>
    </div>

    <div class="card mb-3">
      <div class="card-body">
        <h3 class="h6">HRSG 상태</h3>
        <HrsgDiagram
          :exhaust-temp-c="data.inputs.exhaust_temp_c"
          :stack-temp-c="data.inputs.stack_temp_c"
          :exhaust-level="variables.exhaust_temp.level"
          :stack-level="results.delta_stack_temp_c > 0 ? 'CAUTION' : 'NORMAL'"
        />
      </div>
    </div>

    <div class="row g-3 mb-3">
      <div class="col-12 col-lg-6">
        <div class="card h-100">
          <div class="card-body">
            <h3 class="h6">손실 구성</h3>
            <LossBreakdownChart :gt-mw="results.power_loss_gt_mw" :st-mw="results.power_loss_st_mw" />
          </div>
        </div>
      </div>
      <div class="col-12 col-lg-6">
        <div class="card h-100">
          <div class="card-body">
            <h3 class="h6">상세</h3>
            <dl class="row small mb-0">
              <dt class="col-7 fw-normal text-secondary">배압 상승</dt>
              <dd class="col-5 text-end">{{ formatKpa(results.delta_backpressure_kpa) }}</dd>
              <dt class="col-7 fw-normal text-secondary">굴뚝 온도 상승</dt>
              <dd class="col-5 text-end">{{ formatTemp(results.delta_stack_temp_c) }}</dd>
              <dt class="col-7 fw-normal text-secondary">손실 출력 합계</dt>
              <dd class="col-5 text-end">{{ formatMw(results.power_loss_total_mw) }}</dd>
              <dt class="col-7 fw-normal text-secondary">세정 비용 + 정지 손실</dt>
              <dd class="col-5 text-end">{{ formatWonShort(recovery.total_cost_won) }}</dd>
              <dt class="col-7 fw-normal text-secondary">세정 후 회수 (일)</dt>
              <dd class="col-5 text-end mb-0">{{ formatWonShort(recovery.recovered_daily_won) }}</dd>
            </dl>
          </div>
        </div>
      </div>
    </div>

  </div>
</template>
