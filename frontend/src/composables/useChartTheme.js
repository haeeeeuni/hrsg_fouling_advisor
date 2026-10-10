/**
 * Chart.js 색을 테마에 맞춘다 (specs/12 §2.1).
 * Chart.js 는 CSS 변수를 따라가지 않으므로, 테마가 바뀔 때마다 계산된 색을 다시 읽는다.
 */
import { computed } from 'vue'

import { useUiStore } from '@/stores/ui'

function cssVar(name, fallback) {
  try {
    const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
    return value || fallback
  } catch {
    return fallback
  }
}

export function useChartTheme() {
  const ui = useUiStore()

  return computed(() => {
    // ui.theme 을 읽어 테마가 바뀌면 다시 계산되게 한다.
    const dark = ui.theme === 'dark'
    return {
      text: cssVar('--admin-text', dark ? '#e5e7eb' : '#1f2937'),
      muted: cssVar('--admin-muted', dark ? '#a3acb9' : '#6b7280'),
      grid: cssVar('--admin-border', dark ? '#2c3a52' : '#dbe4ef'),
      surface: cssVar('--admin-surface', dark ? '#172033' : '#ffffff'),
      primary: cssVar('--admin-primary', '#2563eb'),
      success: cssVar('--bs-success', '#198754'),
      warning: cssVar('--bs-warning', '#ffc107'),
      danger: cssVar('--bs-danger', '#dc3545'),
      secondary: cssVar('--bs-secondary', '#6c757d'),
    }
  })
}

/** 공통 축·범례·툴팁 옵션 */
export function baseChartOptions(theme) {
  return {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    plugins: {
      legend: { labels: { color: theme.text } },
      tooltip: { backgroundColor: theme.surface, titleColor: theme.text, bodyColor: theme.text, borderColor: theme.grid, borderWidth: 1 },
    },
    scales: {
      x: { ticks: { color: theme.muted }, grid: { color: theme.grid } },
      y: { ticks: { color: theme.muted }, grid: { color: theme.grid } },
    },
  }
}
