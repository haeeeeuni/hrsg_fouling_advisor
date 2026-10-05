/**
 * 핵심 사용자 흐름 — 업로드 → 검증 → 적재 → 분석 → 대시보드 (specs/17 §6 의 화면판).
 *
 * 준비(호기 등록·컬럼 매핑)는 API 로 하고, 사용자가 실제로 하는 일만 화면으로 한다(support/e2e-unit.ts).
 * 두 번째 실행부터는 같은 시각이 이미 있어 적재 0행이 정상이다(AC-03-3, 중복 건너뛰기).
 */
import path from 'node:path';

import { expect, test } from '@playwright/test';

import { Api } from './support/api';
import { activateE2EUnit, deactivateE2EUnit } from './support/e2e-unit';
import { MUTATES } from './support/env';
import { ensureSampleCsv } from './support/sample-data';
import { kstDate, selectUnit } from './support/ui';

test.describe.configure({ mode: 'serial' });

test.describe(`업로드부터 대시보드까지 ${MUTATES}`, () => {
  let admin: Api;
  let unitId: number;
  let csvPath: string;

  test.beforeAll(async () => {
    csvPath = ensureSampleCsv();
    admin = await Api.asAdmin();
    unitId = await activateE2EUnit(admin);
  });

  test.afterAll(async () => {
    await deactivateE2EUnit(admin, unitId);
    await admin.dispose();
  });

  test('CSV 를 올려 검증하고 적재한다', async ({ page }) => {
    // 같은 파일을 다시 올리면 화면이 window.confirm 으로 확인을 받는다(재실행 시).
    // Playwright 는 대화상자를 기본으로 닫으므로 명시적으로 수락한다.
    page.on('dialog', (dialog) => dialog.accept());

    await page.goto('/upload');
    await page.getByLabel('호기', { exact: true }).selectOption(String(unitId));

    const chooser = page.waitForEvent('filechooser');
    await page.getByRole('button', { name: '파일 선택' }).click();
    await (await chooser).setFiles(csvPath);
    // 업로드 이력 표에도 같은 파일명이 있을 수 있어 검증 버튼 옆 표시로 좁힌다.
    const validate = page.getByRole('button', { name: '검증', exact: true });
    await expect(validate.locator('xpath=..')).toContainText(path.basename(csvPath));

    await validate.click();
    await expect(page.getByRole('heading', { name: '검증 결과' })).toBeVisible({ timeout: 60_000 });

    await page.getByLabel('중복 시각 처리').selectOption('SKIP');
    await page.getByRole('button', { name: '적재', exact: true }).click();
    await expect(page.getByText(/행을 적재했습니다\.$/)).toBeVisible({ timeout: 90_000 });

    // AC-03-5: 적재 결과가 업로드 이력에 남는다.
    const history = page.locator('table', { has: page.getByRole('columnheader', { name: '파일' }) });
    await expect(history.getByRole('cell', { name: path.basename(csvPath) }).first()).toBeVisible();
  });

  test('분석을 실행하면 대시보드로 이동해 결과를 보여준다', async ({ page }) => {
    test.slow(); // 분석은 로컬에서 수 초 ~ 수십 초 걸린다(specs/18 §1 기준 60초).

    const summary = await admin.get<any>(`/api/units/${unitId}/data-summary/`);
    const dataEnd = kstDate(summary.period.end);

    await page.goto('/analysis/new');
    await selectUnit(page, unitId);
    // 기본 기간이 "선택한 호기" 의 적재 기간으로 잡혀야 한다. 진입 직후 호기를 바꾸면
    // 이전 호기의 늦은 응답이 기간을 덮어써 분석이 INSUFFICIENT_DATA 로 실패하던 회귀를 막는다.
    await expect(page.getByLabel('분석 종료일')).toHaveValue(dataEnd);

    await page.getByRole('button', { name: '분석 실행' }).click();

    await expect(page).toHaveURL(/\/dashboard$/, { timeout: 120_000 });
    await expect(page.getByText('분석이 완료되었습니다.')).toBeVisible();
    await expect(page.getByLabel('호기 선택')).toHaveValue(String(unitId));

    for (const label of ['현재 오염도 지수', '오염도 등급', '임계 도달 D-day', '예상 회수 편익']) {
      await expect(page.locator('.ui-stat-label', { hasText: label })).toBeVisible();
    }
    // FI 는 0~100 (AC-07-4 의 화면판).
    const fi = Number(await page.locator('.card', { hasText: '현재 오염도 지수' }).locator('.ui-stat-value').innerText());
    expect(fi).toBeGreaterThanOrEqual(0);
    expect(fi).toBeLessThanOrEqual(100);
  });
});
