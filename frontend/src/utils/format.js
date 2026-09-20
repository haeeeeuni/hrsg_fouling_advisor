/**
 * 공통 포맷터 (specs/16 §7).
 * 모든 금액·지수 표기는 반드시 이 모듈을 거친다(AC-16-5).
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

/** 오염도 지수: 소수 1자리 → `62.4` */
export function formatFi(value) {
  if (isBlank(value)) return EMPTY
  return fixed(value, 1)
}

/** 금액: 천단위 구분 + 억 병기 → `768,200,000 원 (7.68억)` */
export function formatCurrency(value, { withEok = true } = {}) {
  if (isBlank(value)) return EMPTY
  const base = `${withThousands(Math.round(value))} 원`
  if (!withEok || Math.abs(value) < 1e8) return base
  return `${base} (${fixed(value / 1e8, 2)}억)`
}

/** 차압: 소수 2자리 + kPa → `3.82 kPa` */
export function formatDp(value) {
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

/**
 * D-day 표기 (specs/08 §5, specs/16 §7).
 * - 이미 임계치에 도달 → `이미 도달`
 * - 추세 미확인 / 예측 불가 → `예측 불가`
 * - 그 외 → `D-84`
 */
export function formatDday(days, status) {
  if (status === 'ALREADY_EXCEEDED') return '이미 도달'
  if (status === 'NO_TREND' || status === 'INSUFFICIENT_DATA') return '예측 불가'
  if (status === 'BEYOND_HORIZON') return '2년 내 도달 예상 없음'
  if (isBlank(days)) return EMPTY
  if (days <= 0) return '이미 도달'
  return `D-${Math.round(days)}`
}

/** 정수 건수: `52,560` */
export function formatCount(value) {
  if (isBlank(value)) return EMPTY
  return withThousands(value)
}
