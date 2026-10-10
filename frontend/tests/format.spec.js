import { describe, expect, it } from 'vitest'

import {
  EMPTY,
  formatCount,
  formatCurrency,
  formatDate,
  formatDateTime,
  formatKpa,
  formatPercent,
  formatPower,
  formatTemp,
} from '@/utils/format'

describe('formatCurrency', () => {
  it('천단위 구분과 억을 함께 표기한다', () => {
    expect(formatCurrency(768200000)).toBe('768,200,000 원 (7.68억)')
  })

  it('1억 미만이면 억을 병기하지 않는다', () => {
    expect(formatCurrency(5712000)).toBe('5,712,000 원')
  })

  it('음수도 억을 병기한다', () => {
    expect(formatCurrency(-250000000)).toBe('-250,000,000 원 (-2.50억)')
  })

  it('withEok=false 이면 억을 생략한다', () => {
    expect(formatCurrency(768200000, { withEok: false })).toBe('768,200,000 원')
  })
})

describe('단위 포맷터', () => {
  it('압력은 소수 2자리 + kPa', () => {
    expect(formatKpa(3.8249)).toBe('3.82 kPa')
  })

  it('온도는 소수 1자리 + ℃', () => {
    expect(formatTemp(112.44)).toBe('112.4 ℃')
  })

  it('출력은 소수 1자리 + MW', () => {
    expect(formatPower(148.23)).toBe('148.2 MW')
  })

  it('비율은 소수 1자리 + %', () => {
    expect(formatPercent(59.44)).toBe('59.4 %')
  })

  it('건수는 천단위 구분', () => {
    expect(formatCount(52560)).toBe('52,560')
  })
})

describe('날짜 포맷터', () => {
  it('날짜는 YYYY-MM-DD', () => {
    expect(formatDate('2025-09-20T14:02:11+09:00')).toBe('2025-09-20')
  })

  it('일시는 YYYY-MM-DD HH:mm', () => {
    expect(formatDateTime('2025-09-20T14:02:11')).toBe('2025-09-20 14:02')
  })

  it('잘못된 값은 하이픈', () => {
    expect(formatDate('not-a-date')).toBe(EMPTY)
    expect(formatDateTime(null)).toBe(EMPTY)
  })
})

describe('계산기 표기', () => {
  it('큰 금액은 억·만 단위로 줄인다', async () => {
    const { formatWonShort } = await import('@/utils/format')
    expect(formatWonShort(592_110_000)).toBe('5.92억 원')
    expect(formatWonShort(5_921_100)).toBe('592만 원')
    expect(formatWonShort(8000)).toBe('8,000 원')
    expect(formatWonShort(-180_773_356)).toBe('−1.81억 원')
  })

  it('null 은 0 이 아니라 계산 불가 · 회수 불가', async () => {
    const { formatMw, formatPayback, formatWonShort, NOT_COMPUTABLE } = await import('@/utils/format')
    expect(formatWonShort(null)).toBe(NOT_COMPUTABLE)
    expect(formatMw(undefined)).toBe(NOT_COMPUTABLE)
    expect(formatPayback(null)).toBe('회수 불가')
    expect(formatPayback(0)).toBe('0일')
    expect(formatPayback(108.4)).toBe('108일')
  })
})
