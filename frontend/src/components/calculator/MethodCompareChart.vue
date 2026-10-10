<script setup>
/** 공법별 순편익 막대 (specs/05 CALC-3). 음수(손해)는 위험 색으로 구분하고 표에도 같은 값을 둔다. */
import { BarElement, CategoryScale, Chart as ChartJS, LinearScale, Tooltip } from 'chart.js'
import { computed } from 'vue'
import { Bar } from 'vue-chartjs'

import { baseChartOptions, useChartTheme } from '@/composables/useChartTheme'
import { formatWonShort } from '@/utils/format'

ChartJS.register(BarElement, CategoryScale, LinearScale, Tooltip)

const props = defineProps({
  rows: { type: Array, required: true },
})

const theme = useChartTheme()

const chartData = computed(() => ({
  labels: props.rows.map((r) => r.name),
  datasets: [
    {
      label: '순편익 (억 원)',
      data: props.rows.map((r) => r.net_benefit_won / 1e8),
      backgroundColor: props.rows.map((r) => (r.net_benefit_won >= 0 ? theme.value.success : theme.value.danger)),
      borderRadius: 6,
    },
  ],
}))

const options = computed(() => {
  const base = baseChartOptions(theme.value)
  return {
    ...base,
    plugins: {
      ...base.plugins,
      legend: { display: false },
      tooltip: { ...base.plugins.tooltip, callbacks: { label: (ctx) => formatWonShort(ctx.raw * 1e8) } },
    },
    scales: { ...base.scales, y: { ...base.scales.y, title: { display: true, text: '억 원', color: theme.value.muted } } },
  }
})
</script>

<template>
  <div class="ui-chart" role="img" aria-label="공법별 순편익 막대그래프 — 같은 값이 아래 표에 있습니다">
    <Bar :data="chartData" :options="options" />
  </div>
</template>
