<script setup>
import { computed, onMounted, ref } from 'vue'

import { fetchFoulingIndex } from '@/api/analysis'
import { fetchUnitComparison } from '@/api/optional'
import UnitFiOverlayChart from '@/components/charts/UnitFiOverlayChart.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import { formatCurrency, formatDate, formatDday, formatFi } from '@/utils/format'

// 분석 기준일이 이보다 벌어지면 같은 선상에서 비교하기 어렵다 (specs/19 §3.2).
const STALE_GAP_DAYS = 30

const rows = ref([])
const weights = ref({})
const series = ref([])
const loading = ref(false)
const error = ref('')

const GRADE_LABEL = { NORMAL: '양호', CAUTION: '주의', WARNING: '경고' }
const GRADE_CLASS = {
  NORMAL: 'text-bg-success',
  CAUTION: 'text-bg-warning',
  WARNING: 'text-bg-danger',
}

const CONFIDENCE_LABEL = { HIGH: '높음', MEDIUM: '보통', LOW: '낮음' }

const ranked = computed(() => rows.value.filter((row) => row.has_analysis))
const pending = computed(() => rows.value.filter((row) => !row.has_analysis))

/** 분석 기준일이 크게 다르면 비교 자체가 공정하지 않다 (specs/19 §3.2). */
const staleGapDays = computed(() => {
  const times = ranked.value.map((row) => new Date(row.executed_at).getTime())
  if (times.length < 2) return 0
  return Math.round((Math.max(...times) - Math.min(...times)) / 86400000)
})
const hasStaleGap = computed(() => staleGapDays.value > STALE_GAP_DAYS)

async function load() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await fetchUnitComparison()
    rows.value = data.results ?? []
    weights.value = data.weights ?? {}
    await loadSeries()
  } catch (err) {
    error.value = err.response?.data?.error?.message ?? '비교 결과를 불러오지 못했습니다.'
  } finally {
    loading.value = false
  }
}

/** 각 호기의 최신 분석에서 FI 시계열을 받아 한 차트에 겹친다 (specs/19 §3.4). */
async function loadSeries() {
  const loaded = await Promise.all(
    ranked.value.map(async (row) => {
      try {
        const { data } = await fetchFoulingIndex(row.analysis_run_id)
        return { unit_code: row.unit_code, points: data ?? [] }
      } catch {
        return { unit_code: row.unit_code, points: [] }
      }
    }),
  )
  series.value = loaded.filter((item) => item.points.length)
}

onMounted(load)
</script>

<template>
  <section>
    <div class="d-flex align-items-center justify-content-between mb-3">
      <div>
        <h2 class="h5 mb-1">호기 간 오염도 비교</h2>
        <p class="text-muted small mb-0">
          각 호기의 최신 성공 분석을 기준으로 세정 우선순위를 매깁니다. 설비마다 절대값이 다르므로
          FI와 잔차 기반 지표만 비교합니다.
        </p>
      </div>
      <button class="btn btn-sm btn-outline-secondary" type="button" @click="load">새로고침</button>
    </div>

    <div v-if="Object.keys(weights).length" class="alert alert-light border small py-2">
      적용 가중치 — 오염도 {{ weights.fi }} · 진행률 {{ weights.slope }} · 일일 손실
      {{ weights.daily_loss }} · 임박도 {{ weights.urgency }}
      <RouterLink class="ms-2" :to="{ name: 'admin-settings' }">가중치 변경</RouterLink>
    </div>

    <div v-if="hasStaleGap" class="alert alert-warning small py-2">
      호기 간 분석 기준일이 최대 {{ staleGapDays }}일 차이 납니다. 같은 시점 기준으로 다시 분석한
      뒤 비교하는 것을 권장합니다.
    </div>

    <LoadingSpinner v-if="loading" />
    <div v-else-if="error" class="alert alert-danger">{{ error }}</div>
    <EmptyState
      v-else-if="!rows.length"
      title="비교할 호기가 없습니다."
      description="호기를 등록하고 분석을 한 번 이상 실행하면 우선순위가 표시됩니다."
      icon="bi-bar-chart-steps"
    />

    <div v-else class="table-responsive">
      <table class="table table-sm align-middle">
        <caption class="small text-muted">
          점수는 비교 대상 호기들 사이의 상대 순위이며, 절대적인 오염 정도가 아닙니다.
        </caption>
        <thead>
          <tr>
            <th scope="col">순위</th>
            <th scope="col">호기</th>
            <th scope="col" class="text-end">오염도(FI)</th>
            <th scope="col">등급</th>
            <th scope="col" class="text-end">진행률(FI/일)</th>
            <th scope="col" class="text-end">일일 손실</th>
            <th scope="col" class="text-end">D-day</th>
            <th scope="col">도달 예상일</th>
            <th scope="col" class="text-end">예상 순편익</th>
            <th scope="col">분석 기준일</th>
            <th scope="col">신뢰도</th>
            <th scope="col" class="text-end">우선순위 점수</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in ranked" :key="row.unit_id">
            <td class="fw-semibold">{{ row.rank }}</td>
            <td>{{ row.unit_code }} — {{ row.unit_name }}</td>
            <td class="text-end">{{ formatFi(row.fi) }}</td>
            <td>
              <span class="badge" :class="GRADE_CLASS[row.grade] ?? 'text-bg-secondary'">
                {{ GRADE_LABEL[row.grade] ?? '-' }}
              </span>
            </td>
            <td class="text-end">
              {{ row.slope_per_day == null ? '-' : row.slope_per_day.toFixed(3) }}
            </td>
            <td class="text-end">{{ formatCurrency(row.daily_loss_cost) }}</td>
            <td class="text-end">
              {{ row.already_exceeded ? '도달' : formatDday(row.eta_days) }}
            </td>
            <td>{{ formatDate(row.eta_date) }}</td>
            <td class="text-end">{{ formatCurrency(row.net_benefit) }}</td>
            <td>{{ formatDate(row.executed_at) }}</td>
            <td>{{ CONFIDENCE_LABEL[row.confidence] ?? '-' }}</td>
            <td class="text-end">{{ row.priority_score?.toFixed(3) }}</td>
          </tr>

          <tr v-for="row in pending" :key="row.unit_id" class="text-muted">
            <td>-</td>
            <td>{{ row.unit_code }} — {{ row.unit_name }}</td>
            <td colspan="10" class="small">분석 필요 — 성공한 분석 결과가 없습니다.</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="series.length" class="card mt-4">
      <div class="card-header py-2"><strong class="small">호기별 오염도 추이</strong></div>
      <div class="card-body">
        <UnitFiOverlayChart :series="series" />
      </div>
    </div>
  </section>
</template>
