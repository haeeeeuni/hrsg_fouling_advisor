<script setup>
/** 차압·스택온도 실측 vs 기대 오버레이 + 잔차 (specs/11 §5.1~5.2). */
import {
  CategoryScale,
  Chart as ChartJS,
  Legend,
  LineController,
  LineElement,
  LinearScale,
  PointElement,
  TimeScale,
  Tooltip,
} from 'chart.js'
import 'chartjs-adapter-dayjs-4'
import { computed } from 'vue'
import { Line } from 'vue-chartjs'

ChartJS.register(
  LineController, LineElement, PointElement, LinearScale, CategoryScale, TimeScale, Tooltip, Legend,
)

const props = defineProps({
  points: { type: Array, default: () => [] },
  target: { type: String, required: true }, // 'dp' | 'st'
})

const meta = computed(() =>
  props.target === 'dp'
    ? { title: '차압 실측 vs 기대', unit: 'kPa', measured: 'measured_dp', expected: 'expected_dp' }
    : { title: '스택온도 실측 vs 기대', unit: '℃', measured: 'measured_st', expected: 'expected_st' },
)

const chartData = computed(() => ({
  datasets: [
    {
      label: '실측',
      data: props.points.map((p) => ({ x: p.date, y: p[meta.value.measured] })),
      borderColor: '#0d6efd',
      borderWidth: 2,
      pointRadius: 0,
      spanGaps: false,
    },
    {
      label: '기대',
      data: props.points.map((p) => ({ x: p.date, y: p[meta.value.expected] })),
      borderColor: '#6c757d',
      borderDash: [5, 4],
      borderWidth: 1.5,
      pointRadius: 0,
      spanGaps: false,
    },
  ],
}))

const options = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  interaction: { mode: 'index', intersect: false },
  scales: {
    x: { type: 'time', time: { unit: 'month' } },
    y: { title: { display: true, text: meta.value.unit } },
  },
  plugins: { legend: { position: 'bottom', labels: { boxWidth: 18 } } },
}))
</script>

<template>
  <div class="card h-100">
    <div class="card-body">
      <h2 class="h6 mb-3">{{ meta.title }}</h2>
      <div v-if="points.length" style="height: 200px">
        <Line :data="chartData" :options="options" />
      </div>
      <p v-else class="text-secondary small mb-0">분석을 실행하면 표시됩니다.</p>
    </div>
  </div>
</template>
