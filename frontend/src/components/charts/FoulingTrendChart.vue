<script setup>
/**
 * FI 시계열 메인 차트 (specs/11 §4).
 * 등급 배경 + 임계치 라인 + 세정 마커. 추세선·예측밴드는 Phase 4에서 추가한다.
 */
import {
  CategoryScale,
  Chart as ChartJS,
  Filler,
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

import { GRADE } from '@/utils/constants'

ChartJS.register(
  LineController, LineElement, PointElement, LinearScale, CategoryScale,
  TimeScale, Tooltip, Legend, Filler,
)

const props = defineProps({
  points: { type: Array, default: () => [] },
  threshold: { type: Number, default: 60 },
  cautionMin: { type: Number, default: 30 },
  warningMin: { type: Number, default: 60 },
  cleaningEvents: { type: Array, default: () => [] },
  trend: { type: Object, default: null },
})

/** 추세선을 적합 시작일부터 도달 예상일(또는 마지막 관측일)까지 그린다. */
function trendCurve() {
  const t = props.trend
  if (!t?.coefficients || !t.fit_start) return []

  const start = new Date(t.fit_start)
  const lastPoint = props.points.at(-1)?.date
  const endDate = new Date(t.eta_date ?? t.fit_end ?? lastPoint)
  const totalDays = Math.max(1, Math.round((endDate - start) / 86400000))
  const step = Math.max(1, Math.floor(totalDays / 120))

  const fi = (days) =>
    t.model_type === 'EXPONENTIAL'
      ? t.coefficients.c * (1 - Math.exp(-t.coefficients.k * days))
      : t.coefficients.intercept + t.coefficients.slope * days

  const out = []
  for (let d = 0; d <= totalDays; d += step) {
    const at = new Date(start.getTime() + d * 86400000)
    out.push({ x: at.toISOString().slice(0, 10), y: Math.min(100, Math.max(0, fi(d))) })
  }
  return out
}

/** 결측 구간은 선을 잇지 않고 끊어 표시한다 (specs/11 §4). */
const chartData = computed(() => {
  const datasets = [
    {
      label: '오염도 지수',
      data: props.points.map((p) => ({ x: p.date, y: p.fi_value })),
      borderColor: '#0d6efd',
      backgroundColor: 'rgba(13,110,253,0.08)',
      borderWidth: 2,
      pointRadius: 0,
      spanGaps: false,
      fill: true,
    },
  ]

  const curve = trendCurve()
  if (curve.length) {
    datasets.push({
      label: '추세선',
      data: curve,
      borderColor: '#6c757d',
      borderDash: [6, 4],
      borderWidth: 1.5,
      pointRadius: 0,
      fill: false,
    })
  }
  return { datasets }
})

/** 세정 이벤트 수직 마커 (specs/11 §4). */
const cleaningMarkers = {
  id: 'cleaningMarkers',
  afterDatasetsDraw(chart, _args, options) {
    const { ctx, chartArea, scales } = chart
    if (!chartArea || !options.events?.length) return
    ctx.save()
    for (const event of options.events) {
      const x = scales.x.getPixelForValue(new Date(event.cleaned_at).getTime())
      if (x < chartArea.left || x > chartArea.right) continue
      ctx.strokeStyle = '#198754'
      ctx.setLineDash([4, 3])
      ctx.beginPath()
      ctx.moveTo(x, chartArea.top)
      ctx.lineTo(x, chartArea.bottom)
      ctx.stroke()
      ctx.setLineDash([])
      ctx.fillStyle = '#198754'
      ctx.font = '11px sans-serif'
      ctx.fillText('세정', x + 3, chartArea.top + 12)
    }
    ctx.restore()
  },
}

// 등급 배경과 임계치 라인을 그리는 플러그인 (매우 옅게)
const gradeBands = {
  id: 'gradeBands',
  beforeDatasetsDraw(chart, _args, options) {
    const { ctx, chartArea, scales } = chart
    if (!chartArea) return
    const bands = [
      [0, options.cautionMin, 'rgba(25,135,84,0.05)'],
      [options.cautionMin, options.warningMin, 'rgba(255,193,7,0.07)'],
      [options.warningMin, 100, 'rgba(220,53,69,0.06)'],
    ]
    ctx.save()
    for (const [from, to, color] of bands) {
      const yFrom = scales.y.getPixelForValue(to)
      const yTo = scales.y.getPixelForValue(from)
      ctx.fillStyle = color
      ctx.fillRect(chartArea.left, yFrom, chartArea.right - chartArea.left, yTo - yFrom)
    }
    // 임계치 라인
    const y = scales.y.getPixelForValue(options.threshold)
    ctx.strokeStyle = '#dc3545'
    ctx.setLineDash([6, 4])
    ctx.beginPath()
    ctx.moveTo(chartArea.left, y)
    ctx.lineTo(chartArea.right, y)
    ctx.stroke()
    ctx.setLineDash([])
    ctx.fillStyle = '#dc3545'
    ctx.font = '11px sans-serif'
    ctx.fillText(`임계치 ${options.threshold}`, chartArea.left + 6, y - 4)
    ctx.restore()
  },
}

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
    gradeBands: {
      threshold: props.threshold,
      cautionMin: props.cautionMin,
      warningMin: props.warningMin,
    },
    cleaningMarkers: { events: props.cleaningEvents },
    tooltip: {
      callbacks: {
        label(ctx) {
          if (ctx.datasetIndex !== 0) return `추세선 ${ctx.parsed.y?.toFixed(1)}`
          const point = props.points[ctx.dataIndex]
          const grade = GRADE[point?.grade]?.label ?? '–'
          return [
            `FI ${ctx.parsed.y?.toFixed(1)} (${grade})`,
            `표본 ${point?.sample_count?.toLocaleString('ko-KR') ?? '–'}`,
          ]
        },
      },
    },
  },
}))
</script>

<template>
  <div>
    <div style="height: 320px">
      <Line :data="chartData" :options="options" :plugins="[gradeBands, cleaningMarkers]" />
    </div>

    <!-- 차트는 대체 텍스트와 함께 데이터 표를 제공한다 (specs/16 §9, 접근성) -->
    <details class="mt-2">
      <summary class="small text-secondary">차트 데이터 표로 보기</summary>
      <div class="table-responsive mt-2" style="max-height: 240px">
        <table class="table table-sm">
          <thead>
            <tr><th scope="col">일자</th><th scope="col" class="text-end">FI</th><th scope="col">등급</th><th scope="col" class="text-end">표본</th></tr>
          </thead>
          <tbody>
            <tr v-for="p in points" :key="p.date">
              <td class="small">{{ p.date }}</td>
              <td class="small text-end">{{ p.fi_value?.toFixed(1) ?? '–' }}</td>
              <td class="small">{{ GRADE[p.grade]?.label ?? '–' }}</td>
              <td class="small text-end">{{ p.sample_count?.toLocaleString('ko-KR') }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </details>
  </div>
</template>
