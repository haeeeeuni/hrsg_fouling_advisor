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
    const active = new Set(rows(await api.get<any>('/api/units/?is_active=true')).map((u: any) => u.id));
    const analyzed = new Set(
      (rows(await api.get<any>('/api/analysis-runs/?status=SUCCESS&page_size=200')) as any[]).map((r) => r.unit),
    );
    const events = rows(await api.get<any>('/api/cleaning-events/?page_size=200')) as any[];
    eventUnitId = events.map((e) => e.unit).find((u) => active.has(u) && analyzed.has(u)) ?? null;
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
