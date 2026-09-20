/**
 * 비동기 job 진행률 폴링 (specs/15 §1, specs/16 §6).
 *
 * 장시간 작업은 페이지를 이탈했다 돌아와도 상태가 복원돼야 하므로,
 * job_id 를 sessionStorage 에 남겨 둔다(AC-16-4).
 */
import { onUnmounted, ref } from 'vue'

import { cancelJob, fetchJob } from '@/api/jobs'

const DEFAULT_INTERVAL_MS = 1000
const STORAGE_PREFIX = 'hrsg.job.'

function remember(key, jobId) {
  if (!key) return
  try {
    if (jobId) sessionStorage.setItem(STORAGE_PREFIX + key, jobId)
    else sessionStorage.removeItem(STORAGE_PREFIX + key)
  } catch {
    // 프라이빗 모드 등에서 실패할 수 있다. 폴링 자체에는 영향이 없다.
  }
}

export function recallJobId(key) {
  try {
    return sessionStorage.getItem(STORAGE_PREFIX + key)
  } catch {
    return null
  }
}

export function useJobPolling({ key = '', intervalMs = DEFAULT_INTERVAL_MS } = {}) {
  const jobId = ref(null)
  const status = ref(null) // RUNNING | SUCCESS | FAILED | CANCELED
  const progress = ref(0)
  const stage = ref('')
  const result = ref(null)
  const error = ref(null)

  let timer = null
  let resolveDone = null

  function stop() {
    if (timer) {
      clearTimeout(timer)
      timer = null
    }
  }

  function reset() {
    stop()
    jobId.value = null
    status.value = null
    progress.value = 0
    stage.value = ''
    result.value = null
    error.value = null
  }

  async function tick() {
    try {
      const { data } = await fetchJob(jobId.value)
      status.value = data.status
      progress.value = data.progress ?? 0
      stage.value = data.stage ?? ''

      if (data.status === 'SUCCESS') {
        result.value = data.result
        remember(key, null)
        stop()
        resolveDone?.({ status: data.status, result: data.result })
        return
      }
      if (data.status === 'FAILED' || data.status === 'CANCELED') {
        error.value = data.error
        remember(key, null)
        stop()
        resolveDone?.({ status: data.status, error: data.error })
        return
      }
      timer = setTimeout(tick, intervalMs)
    } catch (err) {
      error.value = err.parsed ?? { message: '작업 상태를 확인할 수 없습니다.' }
      status.value = 'FAILED'
      stop()
      resolveDone?.({ status: 'FAILED', error: error.value })
    }
  }

  /** 폴링을 시작하고 완료 시 resolve 되는 Promise 를 돌려준다. */
  function start(id) {
    reset()
    jobId.value = id
    status.value = 'RUNNING'
    remember(key, id)
    const done = new Promise((resolve) => {
      resolveDone = resolve
    })
    tick()
    return done
  }

  /** 페이지 재진입 시 저장된 job 을 이어서 폴링한다. */
  function resume() {
    const saved = recallJobId(key)
    return saved ? start(saved) : null
  }

  async function cancel() {
    if (!jobId.value) return
    await cancelJob(jobId.value)
    status.value = 'CANCELED'
    remember(key, null)
    stop()
  }

  onUnmounted(stop)

  return { jobId, status, progress, stage, result, error, start, resume, cancel, reset, stop }
}
