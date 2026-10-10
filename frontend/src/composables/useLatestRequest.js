/**
 * 디바운스 + 마지막 요청만 반영 (specs/05 CALC-6, specs/11 §5).
 *
 * 값을 연달아 바꾸면 응답이 보낸 순서와 다르게 도착할 수 있다. 늦게 도착한 옛 응답이
 * 최신 결과를 덮으면 화면이 잘못된 값을 보인다 — 이전 앱에서 같은 결함을 세 번 고쳤다.
 * 그래서 요청마다 번호를 매기고, 마지막 번호의 응답만 반영한다.
 *
 * 요청 중에도 이전 결과(data)는 유지한다 — 화면이 깜빡이지 않게.
 */
import { onScopeDispose, ref } from 'vue'

export const DEFAULT_DEBOUNCE_MS = 300

export function useLatestRequest(requestFn, { delay = DEFAULT_DEBOUNCE_MS } = {}) {
  const data = ref(null)
  const error = ref(null)
  const loading = ref(false)
  let seq = 0
  let timer = null

  async function runNow(...args) {
    clearTimeout(timer)
    const mine = ++seq
    loading.value = true
    try {
      const result = await requestFn(...args)
      if (mine !== seq) return // 더 새 요청이 있다 — 버린다
      data.value = result
      error.value = null
    } catch (err) {
      if (mine !== seq) return
      error.value = err?.parsed ?? { code: 'REQUEST_ERROR', message: '계산하지 못했습니다.', details: {} }
    } finally {
      if (mine === seq) loading.value = false
    }
  }

  function run(...args) {
    clearTimeout(timer)
    timer = setTimeout(() => runNow(...args), delay)
  }

  /** 입력이 잘못돼 요청하지 않을 때 — 대기 중인 요청을 취소하고 이후 응답도 무시한다. */
  function cancel() {
    clearTimeout(timer)
    seq += 1
    loading.value = false
  }

  // 화면을 떠나면 대기 중인 요청을 버린다(컴포넌트·effectScope 어디서 써도 동작).
  onScopeDispose(cancel)

  return { data, error, loading, run, runNow, cancel }
}
