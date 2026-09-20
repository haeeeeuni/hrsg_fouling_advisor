import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/api/jobs', () => ({
  fetchJob: vi.fn(),
  cancelJob: vi.fn(),
}))

import { cancelJob, fetchJob } from '@/api/jobs'
import { recallJobId, useJobPolling } from '@/composables/useJobPolling'

function job(status, extra = {}) {
  return { data: { job_id: 'j1', status, progress: 0, stage: '', result: null, error: null, ...extra } }
}

describe('useJobPolling', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    sessionStorage.clear()
    fetchJob.mockReset()
    cancelJob.mockReset()
  })
  afterEach(() => vi.useRealTimers())

  it('성공하면 결과를 돌려주고 폴링을 멈춘다', async () => {
    fetchJob.mockResolvedValue(job('SUCCESS', { progress: 100, result: { row_loaded: 3 } }))
    const polling = useJobPolling()

    const outcome = await polling.start('j1')

    expect(outcome.status).toBe('SUCCESS')
    expect(outcome.result.row_loaded).toBe(3)
    expect(polling.progress.value).toBe(100)
  })

  it('진행 중이면 간격을 두고 다시 조회한다', async () => {
    fetchJob
      .mockResolvedValueOnce(job('RUNNING', { progress: 40, stage: '값 검증' }))
      .mockResolvedValueOnce(job('SUCCESS', { result: {} }))
    const polling = useJobPolling()

    const done = polling.start('j1')
    await vi.advanceTimersByTimeAsync(0)
    expect(polling.stage.value).toBe('값 검증')
    expect(polling.progress.value).toBe(40)

    await vi.advanceTimersByTimeAsync(1000)
    await done

    expect(fetchJob).toHaveBeenCalledTimes(2)
  })

  it('실패하면 error 를 채운다', async () => {
    fetchJob.mockResolvedValue(
      job('FAILED', { error: { code: 'JOB_FAILED', message: '작업이 실패했습니다.' } }),
    )
    const polling = useJobPolling()

    const outcome = await polling.start('j1')

    expect(outcome.status).toBe('FAILED')
    expect(polling.error.value.code).toBe('JOB_FAILED')
  })

  it('AC-16-4: 실행 중 job_id 를 저장했다가 재진입 시 이어받는다', async () => {
    fetchJob.mockResolvedValue(job('RUNNING', { progress: 10 }))
    const polling = useJobPolling({ key: 'upload.validate' })

    polling.start('j-restore')
    await vi.advanceTimersByTimeAsync(0)

    expect(recallJobId('upload.validate')).toBe('j-restore')

    polling.stop()
    const resumed = useJobPolling({ key: 'upload.validate' })
    fetchJob.mockResolvedValue(job('SUCCESS', { result: {} }))
    const promise = resumed.resume()

    expect(promise).not.toBeNull()
    await promise
    expect(resumed.jobId.value).toBe('j-restore')
  })

  it('완료되면 저장된 job_id 를 지운다', async () => {
    fetchJob.mockResolvedValue(job('SUCCESS', { result: {} }))
    const polling = useJobPolling({ key: 'upload.commit' })

    await polling.start('j1')

    expect(recallJobId('upload.commit')).toBeNull()
  })

  it('저장된 job 이 없으면 resume 은 null 을 돌려준다', () => {
    expect(useJobPolling({ key: 'nothing' }).resume()).toBeNull()
  })

  it('취소하면 상태가 CANCELED 가 된다', async () => {
    fetchJob.mockResolvedValue(job('RUNNING'))
    cancelJob.mockResolvedValue({})
    const polling = useJobPolling()

    polling.start('j1')
    await vi.advanceTimersByTimeAsync(0)
    await polling.cancel()

    expect(polling.status.value).toBe('CANCELED')
    expect(cancelJob).toHaveBeenCalledWith('j1')
  })
})
