/**
 * 데이터를 바꾸는 테스트가 같이 쓰는 E2E 호기 (specs/21 §4.6).
 *
 * 호기 코드 E2E 를 매 실행 재사용한다. 데이터가 있는 호기는 삭제할 수 없으므로(specs/02 §2)
 * 쓰는 동안만 활성화하고, 끝나면 비활성화해 다른 화면의 호기 목록을 어지럽히지 않는다.
 */
import fs from 'node:fs';
import path from 'node:path';

import { expect } from '@playwright/test';

import { Api, rows } from './api';
import { E2E_MAPPING, E2E_UNIT_CODE, ensureSampleCsv } from './sample-data';

/** E2E 호기를 활성 상태로 준비하고 id 를 돌려준다. 매핑도 매번 맞춰 둔다. */
export async function activateE2EUnit(admin: Api): Promise<number> {
  let unitId: number;
  const existing = rows(await admin.get<any>('/api/units/')).find((u: any) => u.code === E2E_UNIT_CODE);
  if (existing) {
    unitId = existing.id;
    await admin.patch(`/api/units/${unitId}/`, { is_active: true });
  } else {
    const res = await admin.post('/api/units/', {
      code: E2E_UNIT_CODE,
      name: 'E2E 테스트 호기',
      rated_power_mw: 160,
      rated_st_power_mw: 80,
      min_load_mw: 60,
      sampling_interval_min: 30,
    });
    expect(res.status(), await res.text()).toBe(201);
    unitId = (await res.json()).id;
  }

  const res = await admin.put(`/api/units/${unitId}/column-mappings/`, { mappings: E2E_MAPPING });
  expect(res.ok(), await res.text()).toBeTruthy();
  return unitId;
}

export async function deactivateE2EUnit(admin: Api, unitId: number | undefined) {
  if (unitId) await admin.patch(`/api/units/${unitId}/`, { is_active: false });
}

/**
 * E2E 호기에 시나리오 CSV 가 적재돼 있게 한다. 이미 있으면 아무것도 하지 않는다.
 * 파일 실행 순서와 무관하게 분석 화면 테스트가 돌 수 있게 하는 준비 단계다 — 업로드 화면 자체는 scenario.spec.ts 가 검증한다.
 */
export async function ensureE2EData(admin: Api, unitId: number) {
  const summary = await admin.get<any>(`/api/units/${unitId}/data-summary/`);
  if (summary.row_count > 1000) return;

  const csv = ensureSampleCsv();
  const res = await admin.postMultipart('/api/uploads/operation/validate/', {
    unit_id: String(unitId),
    confirm_duplicate_file: 'true',
    file: { name: path.basename(csv), mimeType: 'text/csv', buffer: fs.readFileSync(csv) },
  });
  expect(res.status(), await res.text()).toBe(202);
  const { batch_id: batchId, job_id: validateJob } = await res.json();
  await admin.waitForJob(validateJob);

  const commit = await admin.post(`/api/uploads/${batchId}/commit/`, { duplicate_policy: 'SKIP' });
  expect(commit.status(), await commit.text()).toBe(202);
  await admin.waitForJob((await commit.json()).job_id);
}

/**
 * E2E 호기의 성공한 분석 id. 없으면 적재 기간 전체로 분석을 돌려 만든다.
 * 분석 결과가 있어야 하는 화면(편익 재계산, 실행 이력 상세 등)의 준비 단계다.
 */
export async function ensureE2EAnalysis(admin: Api, unitId: number): Promise<number> {
  const runs = rows(await admin.get<any>(`/api/analysis-runs/?unit_id=${unitId}&status=SUCCESS`));
  if (runs.length) return runs[0].id;

  await ensureE2EData(admin, unitId);
  const { period } = await admin.get<any>(`/api/units/${unitId}/data-summary/`);
  const res = await admin.post('/api/analysis-runs/', {
    unit_id: unitId,
    period_start: period.start,
    period_end: period.end,
  });
  expect(res.status(), await res.text()).toBe(202);
  const { job_id: jobId, analysis_run_id: runId } = await res.json();
  await admin.waitForJob(jobId);
  return runId;
}
