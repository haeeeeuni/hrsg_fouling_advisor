<script setup>
/** 손실 구성(GT·ST, MW) 막대 (specs/05 CALC-5). */
import { BarElement, CategoryScale, Chart as ChartJS, LinearScale, Tooltip } from 'chart.js'
import { computed } from 'vue'
import { Bar } from 'vue-chartjs'

import { baseChartOptions, useChartTheme } from '@/composables/useChartTheme'

ChartJS.register(BarElement, CategoryScale, LinearScale, Tooltip)

const props = defineProps({
  gtMw: { type: Number, required: true },
  stMw: { type: Number, required: true },
})

const theme = useChartTheme()

const chartData = computed(() => ({
  labels: ['GT 출력 손실 (배압)', 'ST 출력 손실 (굴뚝 온도)'],
  datasets: [
    {
      label: '손실 출력 (MW)',
      data: [props.gtMw, props.stMw],
      backgroundColor: [theme.value.primary, theme.value.warning],
      borderRadius: 6,
    },
  ],
}))

const options = computed(() => {
  const base = baseChartOptions(theme.value)
  return {
    ...base,
    indexAxis: 'y',
    plugins: { ...base.plugins, legend: { display: false } },
    scales: { ...base.scales, x: { ...base.scales.x, beginAtZero: true, title: { display: true, text: 'MW', color: theme.value.muted } } },
  }
})
</script>

<template>
  <div class="ui-chart ui-chart--short" role="img" :aria-label="`GT 손실 ${gtMw.toFixed(2)} MW, ST 손실 ${stMw.toFixed(2)} MW`">
    <Bar :data="chartData" :options="options" />
  </div>
</template>
