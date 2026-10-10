/**
 * 관리자 — 모델 관리 (specs/06, AC-06-5).
 *
 * 재학습한 모델은 비활성으로 저장되고, 관리자가 신·구 지표를 비교한 뒤 활성화해야 쓰인다.
 * 테스트 전용 E2E 호기에서만 한다. 추가한 청정 기준 기간은 끝나면 지운다.
 */
import { expect, test, type Page } from '@playwright/test';

import { Api, rows } from './support/api';
import { activateE2EUnit, deactivateE2EUnit, ensureE2EData } from './support/e2e-unit';
import { MUTATES } from './support/env';

const NOTE = 'E2E테스트 기준기간';

test.describe.configure({ mode: 'serial' });

test.describe(`모델 관리 ${MUTATES}`, () => {
  let admin: Api;
  let unitId: number;

  async function removeTestPeriods() {
    for (const p of rows(await admin.get<any>(`/api/clean-baseline-periods/?unit_id=${unitId}`)) as any[]) {
      if ((p.note ?? '') === NOTE) await admin.delete(`/api/clean-baseline-periods/${p.id}/`);
    }
  }

  async function versions(target: string): Promise<any[]> {
    // 재학습을 거듭하면 버전이 한 페이지를 넘는다. 개수가 아니라 최신 버전 번호로 비교한다.
    return rows(await admin.get<any>(`/api/model-versions/?unit_id=${unitId}&target=${target}&page_size=1000`)) as any[];
  }
  const latestVersion = (list: any[]) => Math.max(0, ...list.map((v) => v.version));

  test.beforeAll(async () => {
    test.setTimeout(180_000);
    admin = await Api.asAdmin();
    unitId = await activateE2EUnit(admin);
    await ensureE2EData(admin, unitId);
    await removeTestPeriods();
  });

  test.afterAll(async () => {
    await removeTestPeriods();
    await deactivateE2EUnit(admin, unitId);
    await admin.dispose();
  });

  async function open(page: Page) {
    await page.goto('/admin/models');
    await page.getByLabel('호기', { exact: true }).selectOption(String(unitId));
  }

  const periodCard = (page: Page) => page.locator('.card', { has: page.getByRole('heading', { name: '청정 기준 기간' }) });

  test('청정 기준 기간을 추가하고 미리보기로 유효 포인트를 확인한다', async ({ page }) => {
    await open(page);
    const add = periodCard(page).getByRole('button', { name: '추가' });
    await expect(add).toBeDisabled(); // 시작·종료가 있어야 한다

    await page.getByLabel('시작', { exact: true }).fill('2023-01-01T00:00');
    await page.getByLabel('종료', { exact: true }).fill('2023-01-31T23:00');
    await page.getByLabel('비고', { exact: true }).fill(NOTE);
    await add.click();
    await expect(page.getByText('청정 기준 기간을 추가했습니다.')).toBeVisible();

    const row = periodCard(page).getByRole('row').filter({ hasText: '2023-01-01' }).first();
    await row.getByRole('button', { name: '미리보기' }).click();
    await expect(page.getByText(/유효 포인트 [\d,]+ · 평균 차압/)).toBeVisible();
  });

  test('재학습하면 새 버전이 "대기"(비활성)로 생기고, 기존 활성 모델은 그대로다', async ({ page }) => {
    test.slow();
    const activeBefore = (await versions('DP')).find((v) => v.is_active)?.id ?? null;
    const latestBefore = latestVersion(await versions('DP'));
    await open(page);

    await page.getByRole('button', { name: '재학습 실행' }).click();

    await expect(page.getByText('재학습 완료. 승인(활성화) 전까지 기존 활성 모델이 그대로 사용됩니다.')).toBeVisible({ timeout: 120_000 });
    const after = await versions('DP');
    expect(latestVersion(after)).toBe(latestBefore + 1);
    expect(after.find((v) => v.version === latestBefore + 1)?.is_active).toBe(false);
    expect(after.find((v) => v.is_active)?.id ?? null).toBe(activeBefore); // AC-06-5
  });

  test('신·구 모델을 비교한 뒤 활성화하면 이후 분석부터 새 모델을 쓴다', async ({ page }) => {
    await open(page);
    const latest = (await versions('DP')).filter((v) => !v.is_active).sort((a, b) => b.version - a.version)[0];
    // "차압 모델" 제목을 감싼 블록 안의 표. 바깥 div 로 잡으면 청정 기준 기간 표까지 걸린다.
    const table = page.getByRole('heading', { name: '차압 모델', exact: true }).locator('xpath=..').locator('table');
    const row = table.getByRole('row').filter({ hasText: `v${latest.version}` });

    await row.getByRole('button', { name: '비교' }).click();
    const compare = page.locator('.card', { has: page.getByRole('heading', { name: '신·구 모델 비교' }) });
    await expect(compare).toContainText('후보');

    page.once('dialog', (d) => {
      expect(d.message()).toContain(`v${latest.version}`);
      return d.accept();
    });
    await compare.getByRole('button', { name: '이 모델로 교체' }).click();

    await expect(page.getByText('활성 모델을 교체했습니다.')).toBeVisible();
    expect((await versions('DP')).find((v) => v.is_active)?.id).toBe(latest.id);
  });

  test('청정 기준 기간 삭제는 확인을 받는다', async ({ page }) => {
    await open(page);
    page.once('dialog', (d) => d.accept());
    const row = periodCard(page).getByRole('row').filter({ hasText: '2023-01-01' }).first();

    await row.getByRole('button', { name: '삭제' }).click();

    await expect
      .poll(async () => (rows(await admin.get<any>(`/api/clean-baseline-periods/?unit_id=${unitId}`)) as any[]).filter((p) => p.note === NOTE).length)
      .toBe(0);
  });
});
