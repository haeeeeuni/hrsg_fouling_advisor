import { describe, expect, it } from 'vitest'

import {
  EMPTY,
  formatCount,
  formatCurrency,
  formatDate,
  formatDateTime,
  formatDday,
  formatDp,
  formatFi,
  formatPercent,
  formatPower,
  formatTemp,
} from '@/utils/format'

describe('formatFi', () => {
  it('소수 1자리로 표기한다', () => {
    expect(formatFi(62.44)).toBe('62.4')
    expect(formatFi(0)).toBe('0.0')
  })

  it('값이 없으면 하이픈, 0 과 구분한다', () => {
    expect(formatFi(null)).toBe(EMPTY)
    expect(formatFi(undefined)).toBe(EMPTY)
    expect(formatFi(0)).not.toBe(EMPTY)
  })
})

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
  it('차압은 소수 2자리 + kPa', () => {
    expect(formatDp(3.8249)).toBe('3.82 kPa')
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

describe('formatDday', () => {
  it('정상 추세는 D-N', () => {
    expect(formatDday(84, 'OK')).toBe('D-84')
  })

  it('이미 도달한 경우', () => {
    expect(formatDday(0, 'ALREADY_EXCEEDED')).toBe('이미 도달')
    expect(formatDday(0, 'OK')).toBe('이미 도달')
  })

  it('추세를 확인할 수 없으면 예측 불가', () => {
    expect(formatDday(null, 'NO_TREND')).toBe('예측 불가')
    expect(formatDday(null, 'INSUFFICIENT_DATA')).toBe('예측 불가')
  })

  it('예측 지평을 넘으면 별도 문구', () => {
    expect(formatDday(900, 'BEYOND_HORIZON')).toBe('2년 내 도달 예상 없음')
  })

  it('값이 없으면 하이픈', () => {
    expect(formatDday(null, undefined)).toBe(EMPTY)
  })

  it('상태 없이 일수만 줘도 동작한다', () => {
    expect(formatDday(84)).toBe('D-84')
    expect(formatDday(84.4)).toBe('D-84')
  })
})
