/**
 * 정비 이력 — 업로드 · 세정 후보 검토 (specs/10).
 *
 * 정비 이력 업로드는 중복을 막지 않아 실행마다 7건이 쌓인다. 그래서 개수 대신
 * "이번에 올린 후보" 의 제목으로 확인한다. 승인으로 생긴 세정 이력(EXTRACTED)은 끝나면 지운다.
 * 추출된 후보는 승인 전까지 CleaningEvent 가 아니다(CLAUDE.md, 오탐 방지).
 */
import fs from 'node:fs';
import path from 'node:path';

import { expect, test, type Page } from '@playwright/test';

import { Api, rows } from './support/api';
import { activateE2EUnit, deactivateE2EUnit } from './support/e2e-unit';
import { MUTATES, PATHS } from './support/env';
import { ensureMaintenanceCsv } from './support/sample-data';

const WATER = 'HRSG 전열면 수세 시행';
const DRY_ICE = 'HRSG 전열면 드라이아이스 시행';

test.describe.configure({ mode: 'serial' });

test.describe(`정비 이력 ${MUTATES}`, () => {
  let admin: Api;
  let unitId: number;

  async function extractedEvents(): Promise<any[]> {
    return (rows(await admin.get<any>(`/api/cleaning-events/?unit_id=${unitId}&page_size=200`)) as any[]).filter(
      (e) => e.source === 'EXTRACTED',
    );
  }

  test.beforeAll(async () => {
    admin = await Api.asAdmin();
    unitId = await activateE2EUnit(admin);
  });

  test.afterAll(async () => {
    for (const e of await extractedEvents()) await admin.delete(`/api/cleaning-events/${e.id}/`);
    await deactivateE2EUnit(admin, unitId);
    await admin.dispose();
  });

  async function open(page: Page) {
    await page.goto('/maintenance');
    await page.getByLabel('호기', { exact: true }).selectOption(String(unitId));
  }

  async function upload(page: Page, file: string) {
    const chooser = page.waitForEvent('filechooser');
    await page.getByRole('button', { name: '파일 선택' }).click();
    await (await chooser).setFiles(file);
  }

  const tab = (page: Page, name: string) => page.locator('.nav-link').filter({ hasText: name });

  test('정비 이력 CSV 를 올리면 읽은 건수와 세정 후보 수를 알려주고, 후보는 아직 세정 이력이 아니다', async ({ page }) => {
    const before = (await extractedEvents()).length;
    await open(page);

    await upload(page, ensureMaintenanceCsv());

    await expect(page.getByText('7건을 읽어 2건의 세정 후보를 찾았습니다.')).toBeVisible({ timeout: 60_000 });
    await expect(page.getByRole('row').filter({ hasText: WATER }).first()).toBeVisible();
    await expect(page.getByRole('row').filter({ hasText: DRY_ICE }).first()).toBeVisible();
    expect((await extractedEvents()).length).toBe(before); // 승인 전에는 만들어지지 않는다
  });

  test('세정 후보를 승인하면 세정 이력이 생기고 "승인됨" 탭으로 옮겨진다', async ({ page }) => {
    const before = (await extractedEvents()).length;
    await open(page);
    page.once('dialog', (d) => {
      expect(d.message()).toContain(WATER);
      return d.accept();
    });

    await page.getByRole('row').filter({ hasText: WATER }).first().getByRole('button', { name: '세정으로 등록' }).click();

    await expect(page.getByText('세정 이력으로 등록했습니다.')).toBeVisible();
    expect((await extractedEvents()).length).toBe(before + 1);
    await tab(page, '승인됨').click();
    await expect(page.getByRole('row').filter({ hasText: WATER }).first()).toBeVisible();
  });

  test('무시하면 "무시됨" 탭으로 옮겨지고 세정 이력은 생기지 않는다', async ({ page }) => {
    const before = (await extractedEvents()).length;
    await open(page);

    await page.getByRole('row').filter({ hasText: DRY_ICE }).first().getByRole('button', { name: '무시' }).click();

    await expect(page.getByText('무시 처리했습니다.')).toBeVisible();
    expect((await extractedEvents()).length).toBe(before);
    await tab(page, '무시됨').click();
    await expect(page.getByRole('row').filter({ hasText: DRY_ICE }).first()).toBeVisible();
  });

  test('"전체" 탭에는 세정과 무관한 정비 이력도 나온다', async ({ page }) => {
    await open(page);
    await tab(page, '전체').click();

    await expect(page.getByRole('row').filter({ hasText: '급수펌프 씰 교체' }).first()).toBeVisible();
  });

  test('CSV·엑셀이 아닌 파일은 거부하고 이유를 보여준다', async ({ page }) => {
    const file = path.join(PATHS.data, 'maintenance.txt');
    fs.writeFileSync(file, '작업일,제목\n2023-01-01,테스트\n');
    await open(page);

    await upload(page, file);

    await expect(page.locator('.alert-danger')).toContainText('CSV 또는 엑셀');
  });
});
