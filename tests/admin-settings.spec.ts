/**
 * 관리자 — 분석 설정 · 편익 기본값 · 호기별 오버라이드 · 감사 로그 (specs/13 §4, AC-13-1).
 *
 * 분석 결과에 영향이 없는 "리포트 파일 보존 기간" 만 바꾸고, 끝나면 API 로 원래 값을 되돌린다.
 * "기본값으로 복원" 은 실행하지 않는다 — 배포본에서 조정해 둔 값(fuel_cost_ratio 0.792 등)까지
 * 시드값으로 되돌려 버린다.
 */
import { expect, test, type Page } from '@playwright/test';

import { Api, rows } from './support/api';
import { activateE2EUnit, deactivateE2EUnit } from './support/e2e-unit';
import { MUTATES } from './support/env';

const KEY = 'report_retention_days';
const LABEL = '리포트 파일 보존 기간';

test.describe.configure({ mode: 'serial' });

test.describe(`설정 ${MUTATES}`, () => {
  let admin: Api;
  let original: number;
  let e2eUnitId: number;

  async function currentValue(): Promise<number> {
    return (rows(await admin.get<any>('/api/settings/')) as any[]).find((s) => s.key === KEY).value;
  }

  test.beforeAll(async () => {
    admin = await Api.asAdmin();
    original = await currentValue();
    e2eUnitId = await activateE2EUnit(admin);
    await admin.delete(`/api/units/${e2eUnitId}/settings/${KEY}/`); // 직전 실행이 남긴 오버라이드
  });

  test.afterAll(async () => {
    await admin.patch('/api/settings/', { [KEY]: original });
    await admin.delete(`/api/units/${e2eUnitId}/settings/${KEY}/`);
    await deactivateE2EUnit(admin, e2eUnitId);
    await admin.dispose();
  });

  async function openSystemTab(page: Page) {
    await page.goto('/admin/settings');
    await page.getByRole('button', { name: '시스템', exact: true }).click();
    await expect(page.locator(`#set-${KEY}`)).toBeVisible();
  }

  test('값을 바꾸면 "변경됨" 과 저장 개수가 보이고, 저장하면 다음 분석부터 적용된다고 안내한다', async ({ page }) => {
    await openSystemTab(page);
    const next = original === 91 ? 92 : 91;

    await page.locator(`#set-${KEY}`).fill(String(next));
    const save = page.getByRole('button', { name: /저장 \(1개 변경\)/ });
    await expect(save).toBeEnabled();
    await save.click();

    await expect(page.getByText(/1개 항목을 저장했습니다\. 다음 분석부터 적용됩니다/)).toBeVisible();
    expect(await currentValue()).toBe(next);
  });

  test('허용 범위를 벗어나면 저장하지 않고 이유를 보여준다', async ({ page }) => {
    await openSystemTab(page);
    const before = await currentValue();

    await page.locator(`#set-${KEY}`).fill('0'); // 최소 1
    await page.getByRole('button', { name: /저장 \(1개 변경\)/ }).click();

    await expect(page.locator('.alert-danger')).toBeVisible();
    expect(await currentValue()).toBe(before);
  });

  test('설정 변경은 감사 로그에 변경 전후 값과 함께 남는다', async ({ page }) => {
    await page.goto('/admin/audit-logs');
    await page.getByLabel('대상').selectOption('Setting');
    await page.getByLabel('동작').selectOption('UPDATE');

    const row = page.locator('tbody tr').first();
    await expect(row).toContainText('관리자');
    await row.getByRole('button', { name: '변경 내역' }).click();
    await expect(page.getByText('변경 후')).toBeVisible();
    await expect(page.locator('pre').filter({ hasText: KEY }).first()).toBeVisible();
  });

  test('편익 기본값 화면에는 편익 항목만 나온다', async ({ page }) => {
    await page.goto('/admin/benefit-settings');

    await expect(page.getByRole('heading', { name: '편익 계산 기본값' })).toBeVisible();
    await expect(page.locator('#set-fuel_cost_ratio')).toBeVisible();
    await expect(page.locator(`#set-${KEY}`)).toHaveCount(0);
  });

  test('호기별 오버라이드를 저장하고 해제하면 전역값을 다시 상속한다', async ({ page }) => {
    await page.goto('/admin/settings');
    await page.getByRole('button', { name: '호기별 오버라이드' }).click();
    await page.getByLabel('호기', { exact: true }).selectOption(String(e2eUnitId));

    await page.getByLabel(`${LABEL} 오버라이드`).check();
    await page.getByLabel(`${LABEL} 호기값`).fill('30');
    await page.getByRole('button', { name: '호기별 설정 저장' }).click();

    await expect(page.getByText('호기별 설정을 저장했습니다.')).toBeVisible();
    const saved = await admin.get<any>(`/api/units/${e2eUnitId}/settings/`);
    expect(saved.settings.find((s: any) => s.key === KEY)).toMatchObject({ is_overridden: true, effective_value: 30 });

    const row = page.getByRole('row').filter({ hasText: LABEL });
    await row.getByRole('button', { name: '해제' }).click();

    await expect(page.getByText('오버라이드를 해제했습니다. 전역값을 상속합니다.')).toBeVisible();
    await expect(row).toContainText('전역값 상속');
  });
});
