/** 체크리스트 — 화면 진행률 규칙(서버 rules.py 와 같아야 함), 클립보드 대체 (specs/07). */
import { afterEach, describe, expect, it, vi } from 'vitest'

import { copyText } from '@/composables/useClipboard'
import { groupByCategory, progressOf } from '@/utils/checklist'

const item = (state, extra = {}) => ({ category: 'GT', category_label: '가스터빈', is_required: true, state, ...extra })

describe('진행률', () => {
  it('필수 항목 기준, 해당 없음은 분모에서 뺀다', () => {
    const result = progressOf([item('RECEIVED'), item('PENDING'), item('NOT_APPLICABLE'), item('RECEIVED', { is_required: false })])

    expect(result).toEqual({ received: 1, total: 2, percent: 50, complete: false })
  })

  it('필수 항목이 없으면 완료다', () => {
    expect(progressOf([item('PENDING', { is_required: false })])).toMatchObject({ percent: 100, complete: true })
  })

  it('분류 순서를 지키며 묶고 분류별 진행률을 붙인다', () => {
    const groups = groupByCategory([
      item('RECEIVED'),
      item('PENDING', { category: 'PINCH', category_label: '핀치·어프로치' }),
      item('PENDING'),
    ])

    expect(groups.map((g) => g.category)).toEqual(['GT', 'PINCH'])
    expect(groups[0].items).toHaveLength(2)
    expect(groups[0].progress.percent).toBe(50)
  })
})

describe('copyText', () => {
  const original = { secure: window.isSecureContext, clipboard: navigator.clipboard }

  afterEach(() => {
    Object.defineProperty(window, 'isSecureContext', { value: original.secure, configurable: true })
    Object.defineProperty(navigator, 'clipboard', { value: original.clipboard, configurable: true })
  })

  it('보안 컨텍스트에서는 클립보드에 쓴다', async () => {
    const writeText = vi.fn(() => Promise.resolve())
    Object.defineProperty(window, 'isSecureContext', { value: true, configurable: true })
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true })

    expect(await copyText('본문')).toBe(true)
    expect(writeText).toHaveBeenCalledWith('본문')
  })

  it('비보안 컨텍스트나 권한 거부면 false — 화면이 텍스트 상자를 펼친다', async () => {
    Object.defineProperty(window, 'isSecureContext', { value: false, configurable: true })
    expect(await copyText('x')).toBe(false)

    Object.defineProperty(window, 'isSecureContext', { value: true, configurable: true })
    Object.defineProperty(navigator, 'clipboard', { value: { writeText: () => Promise.reject(new Error('denied')) }, configurable: true })
    expect(await copyText('x')).toBe(false)
  })
})
