/**
 * 관리자 — 세정 이력 · 오염 키워드 (specs/10, specs/13 §3).
 *
 * 세정 이력은 E2E 호기에만 만들고, 비고에 표식을 달아 끝나면 그것만 지운다.
 * 키워드도 표식이 붙은 것만 만들고 지운다. "기본값 복원"·"재추출" 은 다른 호기의 정비 이력 분류를
 * 바꿀 수 있어 실행하지 않는다.
 */
import { expect, test, type Page } from '@playwright/test';

import { Api, rows } from './support/api';
import { activateE2EUnit, deactivateE2EUnit } from './support/e2e-unit';
import { MUTATES } from './support/env';

const MARK = 'E2E테스트';
const KEYWORD = 'e2e전용키워드';

test.describe.configure({ mode: 'serial' });

test.describe(`세정 이력 ${MUTATES}`, () => {
  let admin: Api;
  let unitId: number;

  async function removeTestEvents() {
    for (const e of rows(await admin.get<any>(`/api/cleaning-events/?unit_id=${unitId}&page_size=200`)) as any[]) {
      if ((e.note ?? '').includes(MARK)) await admin.delete(`/api/cleaning-events/${e.id}/`);
    }
  }

  test.beforeAll(async () => {
    admin = await Api.asAdmin();
    unitId = await activateE2EUnit(admin);
    await removeTestEvents();
  });

  test.afterAll(async () => {
    await removeTestEvents();
    await deactivateE2EUnit(admin, unitId);
    await admin.dispose();
  });

  async function openForm(page: Page) {
    await page.goto('/admin/cleaning-events');
    await page.getByLabel('호기', { exact: true }).selectOption(String(unitId));
    await page.getByRole('button', { name: '세정 이력 추가' }).click();
  }

  const eventRow = (page: Page, day: string) => page.getByRole('row').filter({ hasText: day });

  test('세정 이력을 추가하면 목록에 "수동 등록" 으로 나온다', async ({ page }) => {
    await openForm(page);
    await page.getByLabel('세정 일시').fill('2023-04-10T09:00');
    await page.getByLabel('세정 방법').selectOption({ label: '드라이아이스' });
    await page.getByLabel('비용 (원)').fill('25000000');
    await page.getByLabel('비고').fill(MARK);
    await page.getByRole('button', { name: '저장' }).click();

    await expect(page.getByText('저장했습니다.')).toBeVisible();
    await expect(eventRow(page, '2023-04-10')).toContainText('수동 등록');
  });

  test('같은 날짜에 또 추가하면 저장은 되지만 경고한다', async ({ page }) => {
    await openForm(page);
    await page.getByLabel('세정 일시').fill('2023-04-10T15:00');
    await page.getByLabel('비고').fill(MARK);
    await page.getByRole('button', { name: '저장' }).click();

    await expect(page.getByText('같은 호기에 동일 일자의 세정 이력이 이미 있습니다.')).toBeVisible();
    await expect(eventRow(page, '2023-04-10')).toHaveCount(2);
  });

  test('종료 일시가 세정 일시보다 빠르면 저장하지 않고 이유를 보여준다', async ({ page }) => {
    await openForm(page);
    await page.getByLabel('세정 일시').fill('2023-04-20T09:00');
    await page.getByLabel('종료 일시').fill('2023-04-19T09:00');
    await page.getByLabel('비고').fill(MARK);
    await page.getByRole('button', { name: '저장' }).click();

    await expect(page.locator('.alert-danger')).toContainText('종료 일자는 세정 일자보다 빠를 수 없습니다.');
    await expect(eventRow(page, '2023-04-20')).toHaveCount(0);
  });

  test('수정하면 비용이 바뀐다', async ({ page }) => {
    await page.goto('/admin/cleaning-events');
    await page.getByLabel('호기', { exact: true }).selectOption(String(unitId));
    await eventRow(page, '2023-04-10').first().getByRole('button', { name: '수정' }).click();

    await page.getByLabel('비용 (원)').fill('27000000');
    await page.getByRole('button', { name: '저장' }).click();

    await expect(eventRow(page, '2023-04-10').filter({ hasText: '27,000,000' })).toHaveCount(1);
  });

  test('삭제는 영향 범위를 알리는 확인을 받는다', async ({ page }) => {
    await page.goto('/admin/cleaning-events');
    await page.getByLabel('호기', { exact: true }).selectOption(String(unitId));
    page.once('dialog', (d) => {
      expect(d.message()).toContain('과거 분석 결과의 수치는 그대로 유지됩니다.');
      return d.accept();
    });

    await eventRow(page, '2023-04-10').first().getByRole('button', { name: '삭제' }).click();

    await expect(page.getByText('삭제했습니다.')).toBeVisible();
    await expect(eventRow(page, '2023-04-10')).toHaveCount(1);
  });
});

test.describe(`오염 키워드 ${MUTATES}`, () => {
  let admin: Api;

  async function removeTestKeyword() {
    for (const k of rows(await admin.get<any>('/api/fouling-keywords/?page_size=500')) as any[]) {
      if (k.keyword === KEYWORD) await admin.delete(`/api/fouling-keywords/${k.id}/`);
    }
  }

  test.beforeAll(async () => {
    admin = await Api.asAdmin();
    await removeTestKeyword();
  });

  test.afterAll(async () => {
    await removeTestKeyword();
    await admin.dispose();
  });

  const keywordRow = (page: Page) => page.getByRole('row').filter({ hasText: KEYWORD });

  test('키워드를 추가하고, 같은 분류로 또 추가하면 막는다', async ({ page }) => {
    await page.goto('/admin/keywords');
    const add = page.getByRole('button', { name: '추가', exact: true });
    await expect(add).toBeDisabled(); // 키워드가 비어 있으면 잠긴다

    await page.getByLabel('키워드', { exact: true }).fill(KEYWORD);
    await page.getByLabel('분류', { exact: true }).selectOption('CLEANING');
    await add.click();
    await expect(page.getByText('키워드를 추가했습니다. 다음 추출부터 반영됩니다.')).toBeVisible();
    await expect(keywordRow(page)).toHaveCount(1);

    await page.getByLabel('키워드', { exact: true }).fill(KEYWORD);
    await page.getByLabel('분류', { exact: true }).selectOption('CLEANING');
    await add.click();
    await expect(page.locator('.alert-danger')).toContainText('같은 분류에 이미 등록된 키워드입니다.');
    await expect(keywordRow(page)).toHaveCount(1);
  });

  test('가중치와 사용 여부를 바꾸면 저장된다', async ({ page }) => {
    await page.goto('/admin/keywords');

    await keywordRow(page).getByLabel(`${KEYWORD} 가중치`).fill('2.5');
    await keywordRow(page).getByLabel(`${KEYWORD} 가중치`).press('Tab'); // change 이벤트
    await expect(page.getByText('가중치를 저장했습니다.')).toBeVisible();

    await keywordRow(page).getByLabel(`${KEYWORD} 사용 여부`).uncheck();
    await expect
      .poll(async () => (rows(await admin.get<any>('/api/fouling-keywords/?page_size=500')) as any[]).find((k) => k.keyword === KEYWORD))
      .toMatchObject({ weight: 2.5, is_active: false });
  });

  test('삭제는 확인을 받고 목록에서 사라진다', async ({ page }) => {
    await page.goto('/admin/keywords');
    page.once('dialog', (d) => {
      expect(d.message()).toContain(KEYWORD);
      return d.accept();
    });

    await keywordRow(page).getByRole('button', { name: '삭제' }).click();

    await expect(keywordRow(page)).toHaveCount(0);
  });
});
