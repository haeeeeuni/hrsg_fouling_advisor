<script setup>
/** 호기별 FI 시계열 오버레이 (specs/19 §3.4). */
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
  LineController,
  LineElement,
  PointElement,
  LinearScale,
  CategoryScale,
  TimeScale,
  Tooltip,
  Legend,
)

const props = defineProps({
  // [{ unit_code, points: [{ date, fi_value }] }]
  series: { type: Array, default: () => [] },
  cautionMin: { type: Number, default: 30 },
  warningMin: { type: Number, default: 60 },
})

const COLORS = ['#0d6efd', '#dc3545', '#198754', '#fd7e14', '#6f42c1', '#20c997']

const chartData = computed(() => ({
  datasets: props.series.map((item, index) => ({
    label: item.unit_code,
    data: item.points.map((p) => ({ x: p.date, y: p.fi_value })),
    borderColor: COLORS[index % COLORS.length],
    borderWidth: 2,
    pointRadius: 0,
    // 결측 구간은 선을 잇지 않는다 (specs/11 §4).
    spanGaps: false,
    fill: false,
  })),
}))

const options = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  interaction: { mode: 'index', intersect: false },
  scales: {
    x: { type: 'time', time: { unit: 'month' }, title: { display: true, text: '날짜' } },
    y: { min: 0, max: 100, title: { display: true, text: 'FI' } },
  },
  plugins: {
    legend: { display: true, position: 'bottom', labels: { boxWidth: 18 } },
    gradeBands: { cautionMin: props.cautionMin, warningMin: props.warningMin },
  },
}))

// 등급 배경만 옅게 깔아 호기 간 위치를 읽기 쉽게 한다.
const gradeBands = {
  id: 'gradeBands',
  beforeDatasetsDraw(chart, _args, pluginOptions) {
    const { ctx, chartArea, scales } = chart
    if (!chartArea) return
    const bands = [
      [0, pluginOptions.cautionMin, 'rgba(25,135,84,0.05)'],
      [pluginOptions.cautionMin, pluginOptions.warningMin, 'rgba(255,193,7,0.07)'],
      [pluginOptions.warningMin, 100, 'rgba(220,53,69,0.06)'],
    ]
    ctx.save()
    for (const [from, to, color] of bands) {
      const yFrom = scales.y.getPixelForValue(to)
      const yTo = scales.y.getPixelForValue(from)
      ctx.fillStyle = color
      ctx.fillRect(chartArea.left, yFrom, chartArea.right - chartArea.left, yTo - yFrom)
    }
    ctx.restore()
  },
}
</script>

<template>
  <div style="height: 320px">
    <Line :data="chartData" :options="options" :plugins="[gradeBands]" />
  </div>
</template>
