/**
 * 체크리스트 진행률 — 화면에서 체크할 때 분류별 막대를 바로 갱신하려고 둔다.
 * 규칙은 서버(checklist/rules.py)와 같다: 필수 항목 기준, '해당 없음'은 분모에서 뺀다(specs/07 CHK-3).
 * 전체 진행률과 완료 판정은 서버 응답을 정본으로 쓴다.
 */
export function progressOf(items) {
  const required = items.filter((i) => i.is_required && i.state !== 'NOT_APPLICABLE')
  const received = required.filter((i) => i.state === 'RECEIVED').length
  const total = required.length
  return { received, total, percent: total === 0 ? 100 : Math.round((received / total) * 100), complete: received === total }
}

/** 분류 순서를 지키며 묶는다(서버가 이미 순서대로 준다). */
export function groupByCategory(items) {
  const groups = []
  const index = new Map()
  for (const item of items) {
    if (!index.has(item.category)) {
      index.set(item.category, groups.length)
      groups.push({ category: item.category, label: item.category_label, items: [] })
    }
    groups[index.get(item.category)].items.push(item)
  }
  return groups.map((g) => ({ ...g, progress: progressOf(g.items) }))
}
