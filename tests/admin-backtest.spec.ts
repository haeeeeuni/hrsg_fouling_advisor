/**
 * 관리자 — 예측 정확도 백테스트 (specs/19 §2, AC-19-4·6).
 *
 * 세정 이력이 2회 이상이어야 실행할 수 있다. 실제 호기를 건드리지 않도록 E2E 호기에 운전 데이터의
 * 실제 세정 시점(수세 2023-03-16, 드라이아이스 2023-05-13)으로 세정 이력 2건을 임시로 넣고, 끝나면 지운다.
 */
import { expect, test } from '@playwright/test';

import { Api, rows } from './support/api';
import { activateE2EUnit, deactivateE2EUnit, ensureE2EData } from './support/e2e-unit';
import { MUTATES } from './support/env';
import { selectUnit } from './support/ui';

const MARK = 'E2E테스트 백테스트';

test.describe(`예측 정확도 백테스트 ${MUTATES}`, () => {
  let admin: Api;
  let unitId: number;

  async function removeTestEvents() {
    for (const e of rows(await admin.get<any>(`/api/cleaning-events/?unit_id=${unitId}&page_size=200`)) as any[]) {
      if ((e.note ?? '') === MARK) await admin.delete(`/api/cleaning-events/${e.id}/`);
    }
  }

  test.beforeAll(async () => {
    test.setTimeout(180_000);
    admin = await Api.asAdmin();
    unitId = await activateE2EUnit(admin);
    await ensureE2EData(admin, unitId);
    await removeTestEvents();
  });

  test.afterAll(async () => {
    await removeTestEvents();
    await deactivateE2EUnit(admin, unitId);
    await admin.dispose();
  });

  test('세정 이력이 2회 미만이면 실행 버튼이 잠기고 이유를 보여준다', async ({ page }) => {
    const events = rows(await admin.get<any>(`/api/cleaning-events/?unit_id=${unitId}`));
    test.skip(events.length >= 2, 'E2E 호기에 이미 세정 이력이 2회 이상 있다');
    await page.goto('/admin/backtest');
    await selectUnit(page, unitId);

    await expect(page.getByRole('button', { name: '백테스트 실행' })).toBeDisabled();
    await expect(page.getByText('세정 이력이 2회 이상이어야 합니다.')).toBeVisible();
  });

  test('세정 이력이 2회 이상이면 실행하고, 예측 오차 표를 보여준다', async ({ page }) => {
    test.slow();
    for (const cleanedAt of ['2023-03-16T09:00:00+09:00', '2023-05-13T09:00:00+09:00']) {
      const res = await admin.post('/api/cleaning-events/', { unit: unitId, cleaned_at: cleanedAt, method: 'CHEMICAL', note: MARK });
      expect(res.status(), await res.text()).toBe(201);
    }
    await page.goto('/admin/backtest'); // 가용 여부는 화면을 열 때 읽는다
    await selectUnit(page, unitId);
    await page.getByLabel('컷오프 선행 일수').selectOption({ label: '세정 30일 전' });

    const run = page.getByRole('button', { name: '백테스트 실행' });
    await expect(run).toBeEnabled();
    await run.click();
    await expect(page.getByRole('button', { name: '실행 중…' })).toBeVisible();

    await expect(page.getByText('백테스트가 완료되었습니다.')).toBeVisible({ timeout: 150_000 });
    await expect(page.getByText('평균 절대 오차')).toBeVisible();
    await expect(page.getByRole('columnheader', { name: '실제 세정일' })).toBeVisible();
  });
});
