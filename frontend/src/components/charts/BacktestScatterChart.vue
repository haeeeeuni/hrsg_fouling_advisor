<script setup>
/** 예측 도달일 vs 실제 세정일 산점도 + 45° 기준선 (specs/19 §2.4). */
import {
  Chart as ChartJS,
  Legend,
  LineController,
  LineElement,
  LinearScale,
  PointElement,
  ScatterController,
  TimeScale,
  Tooltip,
} from 'chart.js'
import 'chartjs-adapter-dayjs-4'
import { computed } from 'vue'
import { Scatter } from 'vue-chartjs'

ChartJS.register(
  ScatterController,
  LineController,
  LineElement,
  PointElement,
  LinearScale,
  TimeScale,
  Tooltip,
  Legend,
)

const props = defineProps({
  // [{ x: 실제 세정일(ISO), y: 예측 도달일(ISO) }]
  points: { type: Array, default: () => [] },
})

const times = computed(() =>
  props.points.flatMap((p) => [new Date(p.x).getTime(), new Date(p.y).getTime()]),
)

/** 점이 이 선 위에 있으면 정확히 맞춘 것이다. */
const referenceLine = computed(() => {
  if (!times.value.length) return []
  const min = Math.min(...times.value)
  const max = Math.max(...times.value)
  return [
    { x: new Date(min).toISOString(), y: new Date(min).toISOString() },
    { x: new Date(max).toISOString(), y: new Date(max).toISOString() },
  ]
})

const chartData = computed(() => ({
  datasets: [
    {
      type: 'scatter',
      label: '세정 사례',
      data: props.points,
      backgroundColor: '#0d6efd',
      pointRadius: 5,
    },
    {
      type: 'line',
      label: '정확히 일치(45°)',
      data: referenceLine.value,
      borderColor: '#6c757d',
      borderDash: [6, 4],
      borderWidth: 1.5,
      pointRadius: 0,
      fill: false,
    },
  ],
}))

const options = {
  responsive: true,
  maintainAspectRatio: false,
  scales: {
    x: { type: 'time', time: { unit: 'month' }, title: { display: true, text: '실제 세정일' } },
    y: { type: 'time', time: { unit: 'month' }, title: { display: true, text: '예측 도달일' } },
  },
  plugins: { legend: { display: true, position: 'bottom', labels: { boxWidth: 18 } } },
}
</script>

<template>
  <div style="height: 300px">
    <Scatter :data="chartData" :options="options" />
  </div>
</template>
