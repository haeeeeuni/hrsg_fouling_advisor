/**
 * 공통 포맷터 (specs/11 §7).
 * 모든 금액·수치 표기는 반드시 이 모듈을 거친다.
 */
import dayjs from 'dayjs'

/** 값이 없음을 나타내는 표기. 0 과 구분한다. */
export const EMPTY = '–'

const isBlank = (value) =>
  value === null || value === undefined || value === '' || (typeof value === 'number' && Number.isNaN(value))

function fixed(value, digits) {
  return Number(value).toFixed(digits)
}

function withThousands(value, digits = 0) {
  return Number(value).toLocaleString('ko-KR', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })
}

/** 금액: 천단위 구분 + 억 병기 → `768,200,000 원 (7.68억)` */
export function formatCurrency(value, { withEok = true } = {}) {
  if (isBlank(value)) return EMPTY
  const base = `${withThousands(Math.round(value))} 원`
  if (!withEok || Math.abs(value) < 1e8) return base
  return `${base} (${fixed(value / 1e8, 2)}억)`
}

/** 압력: 소수 2자리 + kPa → `3.82 kPa` */
export function formatKpa(value) {
  if (isBlank(value)) return EMPTY
  return `${fixed(value, 2)} kPa`
}

/** 온도: 소수 1자리 + ℃ → `112.4 ℃` */
export function formatTemp(value) {
  if (isBlank(value)) return EMPTY
  return `${fixed(value, 1)} ℃`
}

/** 출력: 소수 1자리 + MW → `148.2 MW` */
export function formatPower(value) {
  if (isBlank(value)) return EMPTY
  return `${fixed(value, 1)} MW`
}

/** 비율: 소수 1자리 + % → `59.4 %` */
export function formatPercent(value) {
  if (isBlank(value)) return EMPTY
  return `${fixed(value, 1)} %`
}

/** 날짜: `YYYY-MM-DD` */
export function formatDate(value) {
  if (isBlank(value)) return EMPTY
  const d = dayjs(value)
  return d.isValid() ? d.format('YYYY-MM-DD') : EMPTY
}

/** 일시: `YYYY-MM-DD HH:mm` */
export function formatDateTime(value) {
  if (isBlank(value)) return EMPTY
  const d = dayjs(value)
  return d.isValid() ? d.format('YYYY-MM-DD HH:mm') : EMPTY
}

/** 정수 건수: `52,560` */
export function formatCount(value) {
  if (isBlank(value)) return EMPTY
  return withThousands(value)
}
