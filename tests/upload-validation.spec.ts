/**
 * 업로드 검증의 오류 경로 — specs/03 §4.
 *
 * 구조 오류(컬럼 누락)는 적재를 막고, 행 단위 오류는 그 행만 빼고 진행한다(§4.4).
 * 어느 쪽이든 사용자가 "무엇이 왜" 문제인지 화면에서 알 수 있어야 한다.
 * 검증만 하고 적재하지 않으므로 Measurement 는 늘지 않지만, 업로드 배치 기록은 남는다.
 */
import fs from 'node:fs';
import path from 'node:path';

import { expect, test } from '@playwright/test';

import { Api } from './support/api';
import { activateE2EUnit, deactivateE2EUnit } from './support/e2e-unit';
import { MUTATES, PATHS } from './support/env';
import { dropColumn, ensureSampleCsv, replaceCells, writeCsvVariant } from './support/sample-data';
import { chooseAndValidate } from './support/ui';

test.describe.configure({ mode: 'serial' });

test.describe(`업로드 검증 오류 ${MUTATES}`, () => {
  let admin: Api;
  let unitId: number;

  test.beforeAll(async () => {
    ensureSampleCsv();
    admin = await Api.asAdmin();
    unitId = await activateE2EUnit(admin);
  });

  test.afterAll(async () => {
    await deactivateE2EUnit(admin, unitId);
    await admin.dispose();
  });

  test.beforeEach(async ({ page }) => {
    // 같은 내용의 파일을 재실행마다 다시 올리므로 "같은 파일" 확인을 수락한다.
    page.on('dialog', (dialog) => dialog.accept());
  });

  test('업로드 전에 이 호기가 찾는 컬럼명과 필수 여부를 보여준다', async ({ page }) => {
    await page.goto('/upload');
    await page.getByLabel('호기', { exact: true }).selectOption(String(unitId));

    const guide = page.locator('.card', { has: page.getByRole('heading', { name: /이 호기가 찾는 컬럼명/ }) });
    await expect(guide).toBeVisible();
    // E2E 호기는 영문 헤더 매핑이다(support/sample-data.ts). 매핑된 9개가 모두 나온다.
    const stack = guide.getByRole('row').filter({ has: page.locator('code', { hasText: /^stack_temp_c$/ }) });
    await expect(stack).toContainText('필수');
    const st = guide.getByRole('row').filter({ has: page.locator('code', { hasText: /^st_power_mw$/ }) });
    await expect(st).toContainText('선택');
    await expect(guide.locator('tbody tr')).toHaveCount(9);
    // 관리자에게는 매핑 화면으로 가는 링크를 준다.
    await expect(guide.getByRole('link', { name: '컬럼 매핑' })).toBeVisible();
  });

  test('AC-03-1: 필수 컬럼이 빠지면 어떤 항목이 어떤 원본 컬럼을 못 찾았는지 보여주고 적재를 막는다', async ({ page }) => {
    const file = writeCsvVariant('missing_stack_temp.csv', dropColumn('stack_temp_c'));

    await chooseAndValidate(page, unitId, file);

    const blocking = page.getByRole('alert').filter({ hasText: '적재할 수 없습니다.' });
    await expect(blocking).toBeVisible({ timeout: 60_000 });
    await expect(blocking).toContainText('stack_temp_c ← "stack_temp_c"');
    await expect(page.getByRole('button', { name: '적재', exact: true })).toBeDisabled();
    // 막혔을 때가 컬럼명 안내가 가장 필요한 순간이다 — 검증 결과와 함께 남아 있어야 한다.
    await expect(page.getByRole('heading', { name: /이 호기가 찾는 컬럼명/ })).toBeVisible();
  });

  test('AC-03-2: 타임스탬프를 해석할 수 없는 행은 제외되고 건수가 표시된다', async ({ page }) => {
    const badRows = [10, 20, 30, 40, 50];
    const file = writeCsvVariant('bad_timestamps.csv', replaceCells('timestamp', badRows, 'not-a-date'));

    await chooseAndValidate(page, unitId, file);

    const rowErrors = page.getByRole('alert').filter({ hasText: '일부 행이 제외됩니다.' });
    await expect(rowErrors).toBeVisible({ timeout: 60_000 });
    await expect(rowErrors).toContainText(`${badRows.length}건`);
    // 행 단위 오류는 적재를 막지 않는다(specs/03 §4.4).
    await expect(page.getByRole('button', { name: '적재', exact: true })).toBeEnabled();
    await page.getByRole('button', { name: '폐기' }).click(); // 검증 상태 배치를 남기지 않는다
  });

  test('숫자 칸의 문자열은 경고로 집계되고 적재는 가능하다', async ({ page }) => {
    const file = writeCsvVariant('bad_numbers.csv', replaceCells('gt_power_mw', [5, 6, 7], 'Bad'));

    await chooseAndValidate(page, unitId, file);

    await expect(page.getByRole('heading', { name: '검증 결과' })).toBeVisible({ timeout: 60_000 });
    const issues = page.getByRole('alert').filter({ hasText: /3건/ });
    await expect(issues.first()).toBeVisible();
    await expect(page.getByRole('button', { name: '적재', exact: true })).toBeEnabled();
    await page.getByRole('button', { name: '폐기' }).click(); // 검증 상태 배치를 남기지 않는다
  });

  test('검증 결과를 폐기하면 결과 카드가 사라지고 안내가 뜬다', async ({ page }) => {
    const file = writeCsvVariant('discard_me.csv', (h, r) => ({ header: h, rows: r }), 100);

    await chooseAndValidate(page, unitId, file);
    await expect(page.getByRole('heading', { name: '검증 결과' })).toBeVisible({ timeout: 60_000 });

    await page.getByRole('button', { name: '폐기' }).click();

    await expect(page.getByText('검증 결과를 폐기했습니다.')).toBeVisible();
    await expect(page.getByRole('heading', { name: '검증 결과' })).toHaveCount(0);
  });

  test('CSV 가 아닌 파일은 화면이 깨지지 않고 오류를 안내한다', async ({ page }) => {
    // 사용자가 실수로 고를 법한 이미지 파일. PNG 시그니처만 있는 바이너리를 만든다.
    const file = path.join(PATHS.data, 'not_a_csv.png');
    fs.writeFileSync(file, Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0, 0, 0, 0]));

    const errors: string[] = [];
    page.on('pageerror', (err) => errors.push(err.message));

    await chooseAndValidate(page, unitId, file);

    // 오류 안내든 차단 리포트든 사용자에게 무언가 알려야 한다. 조용히 멈추면 안 된다.
    await expect(page.getByRole('alert').first()).toBeVisible({ timeout: 60_000 });
    await expect(page.getByRole('button', { name: '적재', exact: true })).toHaveCount(0);
    expect(errors).toEqual([]);
  });

  test('적재한 파일을 다시 올리면 확인을 묻고, 취소하면 검증하지 않고 이유를 보여준다', async ({ page }) => {
    // 확인은 "적재까지 마친" 파일에만 뜬다. 검증 후 폐기한 파일은 해당하지 않는다.
    // 원본 앞 100행이라 시나리오 파일과 시각이 겹치지만, 시나리오는 중복을 건너뛰므로 영향이 없다.
    const file = writeCsvVariant('reupload.csv', (h, r) => ({ header: h, rows: r }), 100);

    await chooseAndValidate(page, unitId, file); // 재실행이면 여기서 확인이 뜨고 beforeEach 가 수락한다
    await expect(page.getByRole('heading', { name: '검증 결과' })).toBeVisible({ timeout: 60_000 });
    await page.getByRole('button', { name: '적재', exact: true }).click();
    await expect(page.getByText(/행을 적재했습니다\.$/)).toBeVisible({ timeout: 60_000 });

    page.removeAllListeners('dialog');
    let asked = '';
    page.on('dialog', (dialog) => {
      asked = dialog.message();
      return dialog.dismiss();
    });

    await chooseAndValidate(page, unitId, file);

    await expect(page.getByRole('alert').filter({ hasText: '같은 파일' })).toBeVisible();
    expect(asked).toContain('계속 진행할까요?');
    await expect(page.getByRole('heading', { name: '검증 결과' })).toHaveCount(0);
  });
});
