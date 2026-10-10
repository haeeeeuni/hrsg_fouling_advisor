/**
 * 리포트 내려받기 · 세정 전후 비교 — specs/12, specs/10 §5.
 *
 * 파일이 "내려받아졌다" 에서 멈추지 않고, 열 수 있는 PDF/엑셀인지 시그니처로 확인한다.
 * 한글 깨짐(폰트) 같은 내용 검증은 backend 의 PDF 테스트가 맡는다(specs/18 §8).
 * 리포트·비교 기록이 DB 에 남으므로 로컬에서만 돈다.
 */
import fs from 'node:fs';

import { expect, test, type Page } from '@playwright/test';

import { Api, rows } from './support/api';
import { MUTATES } from './support/env';
import { selectUnit } from './support/ui';

const PDF_MAGIC = '%PDF-';
const XLSX_MAGIC = 'PK'; // xlsx 는 zip 이다

function head(path: string, n: number) {
  return fs.readFileSync(path).subarray(0, n).toString('latin1');
}

async function saveDownload(page: Page, click: () => Promise<void>) {
  const pending = page.waitForEvent('download', { timeout: 60_000 });
  await click();
  const download = await pending;
  const path = await download.path();
  expect(fs.statSync(path).size).toBeGreaterThan(1000);
  return { download, path };
}

test.describe(`리포트 ${MUTATES}`, () => {
  let unitId: number | null = null;
  let eventUnitId: number | null = null;

  test.beforeAll(async () => {
    const api = await Api.asAdmin();
    unitId = await api.latestAnalyzedUnitId();
    // 세정 전후 비교에는 세정 이력과 분석이 모두 있는 활성 호기가 필요하다.
    const latest = await api.latestRunByActiveUnit();
    const analyzed = new Set([...latest].filter(([, run]) => run).map(([unit]) => unit));
    for (const unit of analyzed) {
      if (rows(await api.get<any>(`/api/cleaning-events/?unit_id=${unit}&page_size=1`)).length) {
        eventUnitId = unit;
        break;
      }
    }
    await api.dispose();
  });

  test('대시보드에서 PDF 를 내려받으면 열 수 있는 PDF 파일이다', async ({ page }) => {
    test.skip(unitId === null, '성공한 분석이 있는 호기가 없다');
    await page.goto('/dashboard');
    await selectUnit(page, unitId!);

    const { download, path } = await saveDownload(page, () =>
      page.getByRole('button', { name: 'PDF 다운로드' }).click(),
    );

    expect(download.suggestedFilename()).toMatch(/\.pdf$/);
    expect(head(path, 5)).toBe(PDF_MAGIC);
    await expect(page.getByText('리포트를 내려받았습니다.')).toBeVisible();
  });

  test('대시보드에서 엑셀을 내려받으면 xlsx 파일이다', async ({ page }) => {
    test.skip(unitId === null, '성공한 분석이 있는 호기가 없다');
    await page.goto('/dashboard');
    await selectUnit(page, unitId!);

    const { download, path } = await saveDownload(page, () =>
      page.getByRole('button', { name: '엑셀 다운로드' }).click(),
    );

    expect(download.suggestedFilename()).toMatch(/\.xlsx$/);
    expect(head(path, 2)).toBe(XLSX_MAGIC);
  });

  test('리포트 생성 중에는 다운로드 버튼이 잠긴다(중복 생성 방지)', async ({ page }) => {
    test.skip(unitId === null, '성공한 분석이 있는 호기가 없다');
    await page.goto('/dashboard');
    await selectUnit(page, unitId!);
    // 응답을 잠깐 붙잡아 "생성 중" 상태를 관찰한다.
    await page.route('**/api/analysis-runs/*/export/', async (route) => {
      await new Promise((r) => setTimeout(r, 1500));
      await route.continue();
    });

    const pending = page.waitForEvent('download', { timeout: 60_000 });
    await page.getByRole('button', { name: 'PDF 다운로드' }).click();

    await expect(page.getByRole('button', { name: 'PDF 다운로드' })).toBeDisabled();
    await expect(page.getByRole('button', { name: '엑셀 다운로드' })).toBeDisabled();
    await pending;
    await expect(page.getByRole('button', { name: 'PDF 다운로드' })).toBeEnabled();
  });

  test('리포트 화면의 PDF 버튼은 생성 중임을 보여주고 PDF 를 내려받는다', async ({ page }) => {
    test.skip(unitId === null, '성공한 분석이 있는 호기가 없다');
    await page.goto('/reports');
    // 느린 서버(Render 무료 CPU)를 흉내 내 "생성 중" 상태를 관찰한다. 표시가 없으면 멈춘 것처럼 보인다.
    await page.route('**/api/analysis-runs/*/export/', async (route) => {
      await new Promise((r) => setTimeout(r, 1500));
      await route.continue();
    });
    const firstRow = page.locator('table').first().locator('tbody tr').first();

    const { download, path } = await saveDownload(page, async () => {
      await firstRow.getByRole('button', { name: 'PDF', exact: true }).click();
      await expect(firstRow.getByRole('button', { name: '생성 중' })).toBeVisible();
    });

    expect(download.suggestedFilename()).toMatch(/\.pdf$/);
    expect(head(path, 5)).toBe(PDF_MAGIC);
    await expect(firstRow.getByRole('button', { name: 'PDF', exact: true })).toBeEnabled();
  });

  test('세정 전후 비교를 만들고 결과를 PDF 로 내려받는다', async ({ page }) => {
    test.skip(eventUnitId === null, '세정 이력과 분석이 모두 있는 활성 호기가 없다');
    await page.goto('/comparison');
    await selectUnit(page, eventUnitId!);

    await page.getByRole('button', { name: '비교 생성' }).click();

    await expect(page.getByRole('heading', { name: '비교 결과' })).toBeVisible({ timeout: 60_000 });
    // 비교 가능하면 지표 표, 아니면 사유가 나온다. 어느 쪽이든 빈 카드여서는 안 된다(specs/10 §5).
    const table = page.getByRole('columnheader', { name: '개선율' });
    const reason = page.locator('.alert-warning');
    await expect(table.or(reason).first()).toBeVisible();

    const { path } = await saveDownload(page, () => page.getByRole('button', { name: 'PDF', exact: true }).click());
    expect(head(path, 5)).toBe(PDF_MAGIC);
  });
});

test('회복률을 계산할 수 없는 비교는 0 % 가 아니라 "비교 불가/계산 불가" 로 보인다', async ({ page }) => {
  // 서버는 공통 군집이 없거나 세정 전 FI 가 0 이면 recovery_ratio 를 null 로 준다(specs/12 §2.5).
  // 화면이 null 을 0 % 로 바꿔 "회복이 전혀 안 됨" 처럼 보이던 문제의 회귀 테스트다. 데이터와 무관하게 응답을 주입한다.
  const api = await Api.asAdmin();
  const unit = rows(await api.get<any>('/api/units/?is_active=true'))[0];
  await api.dispose();
  test.skip(!unit, '활성 호기가 없다');

  const base = { unit: unit.id, unit_code: unit.code, method_label: '드라이아이스', created_at: '2026-10-05T00:00:00+09:00',
    cleaned_at: '2024-07-25T00:00:00+09:00', warnings: [], metrics: { rows: [], n_before: 0, n_after: 0 } };
  const reports = [
    { ...base, id: 9001, common_clusters: [], is_comparable: false, recovery_ratio: null },
    { ...base, id: 9002, common_clusters: ['L3-SU'], is_comparable: true, recovery_ratio: null },
    { ...base, id: 9003, common_clusters: ['L3-SU'], is_comparable: true, recovery_ratio: 0.5 },
  ];
  await page.route('**/api/cleaning-events/**', (route) =>
    route.fulfill({ json: { count: 1, results: [{ id: 1, unit: unit.id, cleaned_at: base.cleaned_at, method_label: '드라이아이스' }] } }),
  );
  await page.route('**/api/comparisons/?**', (route) =>
    route.fulfill({ json: { count: reports.length, next: null, previous: null, results: reports } }),
  );

  await page.goto('/comparison');
  await selectUnit(page, unit.id);

  const history = page.locator('table', { has: page.getByRole('columnheader', { name: '회복률' }) });
  // 4번째 칸이 회복률이다. 값이 있는 행만 % 로 나온다.
  await expect(history.locator('tbody tr td:nth-child(4)')).toHaveText(['비교 불가', '계산 불가', '50.0 %']);
});
