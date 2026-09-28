<script setup>
import { computed } from 'vue'

import HelpHint from '@/components/common/HelpHint.vue'

import { formatCount, formatPercent } from '@/utils/format'

const props = defineProps({ quality: { type: Object, default: null } })

const ratioPct = computed(() => (props.quality?.valid_ratio ?? 0) * 100)
const reasons = computed(() => Object.entries(props.quality?.excluded_by_reason ?? {}))
const maxReason = computed(() => Math.max(1, ...reasons.value.map(([, n]) => n)))
</script>

<template>
  <div class="card h-100">
    <div class="card-body">
      <h2 class="h6 mb-3 d-flex align-items-center gap-2">
        <span>데이터 품질</span>
        <HelpHint label="데이터 품질" align="end">
          분석은 <strong>정상 운전(STEADY) 구간만</strong> 씁니다. 기동·정지·부하 변동·
          덕트버너 가동 구간은 오염과 무관하게 차압과 온도를 흔들기 때문입니다.
          <br /><br />
          따라서 <strong>제외 비율이 높아도 정상일 수 있습니다</strong> — 기동·정지가 잦은
          호기일수록 높아집니다. 원본 데이터는 삭제되지 않고 제외 표시만 남습니다.
        </HelpHint>
      </h2>

      <template v-if="quality">
        <div class="d-flex justify-content-between small">
          <span class="text-secondary">총 / 유효 포인트</span>
          <span>
            {{ formatCount(quality.row_total) }} /
            <strong>{{ formatCount(quality.row_valid) }}</strong>
          </span>
        </div>

        <div
          class="progress mt-2"
          style="height: 0.6rem"
          role="img"
          :aria-label="`유효 비율 ${formatPercent(ratioPct)}`"
        >
          <div
            class="progress-bar"
            :class="ratioPct < 20 ? 'bg-danger' : 'bg-success'"
            :style="{ width: `${ratioPct}%` }"
          ></div>
        </div>
        <p class="small text-secondary mt-1 mb-3">유효 비율 {{ formatPercent(ratioPct) }}</p>

        <table class="table table-sm mb-0">
          <caption class="visually-hidden">제외 사유별 건수</caption>
          <tbody>
            <tr v-for="[label, count] in reasons" :key="label">
              <td class="small text-secondary" style="width: 40%">제외 – {{ label }}</td>
              <td>
                <div class="progress" style="height: 0.4rem">
                  <div
                    class="progress-bar bg-secondary"
                    :style="{ width: `${(count / maxReason) * 100}%` }"
                  ></div>
                </div>
              </td>
              <td class="small text-end" style="width: 22%">{{ formatCount(count) }}</td>
            </tr>
          </tbody>
        </table>

        <dl class="row small mt-3 mb-0">
          <dt class="col-7 text-secondary fw-normal">유효 세그먼트</dt>
          <dd class="col-5 text-end mb-1">{{ formatCount(quality.segment_count) }}개</dd>
          <dt class="col-7 text-secondary fw-normal">청정 기준 포인트</dt>
          <dd class="col-5 text-end mb-1">{{ formatCount(quality.baseline_points) }}</dd>
          <dt class="col-7 text-secondary fw-normal">도메인 밖 비율</dt>
          <dd class="col-5 text-end mb-0">
            {{ formatPercent((quality.out_of_domain_ratio ?? 0) * 100) }}
          </dd>
        </dl>
      </template>

      <p v-else class="text-secondary small mb-0">분석을 실행하면 표시됩니다.</p>
    </div>
  </div>
</template>
