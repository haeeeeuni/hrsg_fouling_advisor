/**
 * 분석 실행 화면의 비동기 처리 — specs/16 §6, AC-16-4, specs/15 §1(202 + job_id).
 *
 * 분석은 로컬에서 약 8초 걸린다. 그 사이에 사용자가 하는 일(중복 클릭, 다른 화면 이동, 새로고침)이
 * 작업을 잃거나 두 번 실행하지 않는지 본다.
 */
import { expect, test, type Page } from '@playwright/test';

import { Api } from './support/api';
import { activateE2EUnit, deactivateE2EUnit, ensureE2EData } from './support/e2e-unit';
import { MUTATES } from './support/env';
import { kstDate, selectUnit } from './support/ui';

test.describe.configure({ mode: 'serial' });

test.describe(`분석 실행 ${MUTATES}`, () => {
  let admin: Api;
  let unitId: number;

  test.beforeAll(async () => {
    test.setTimeout(180_000); // 빈 DB 라면 시나리오 CSV 를 먼저 적재한다
    admin = await Api.asAdmin();
    unitId = await activateE2EUnit(admin);
    await ensureE2EData(admin, unitId);
  });

  test.afterAll(async () => {
    await deactivateE2EUnit(admin, unitId);
    await admin.dispose();
  });

  async function openRunPage(page: Page) {
    const summary = await admin.get<any>(`/api/units/${unitId}/data-summary/`);
    await page.goto('/analysis/new');
    await selectUnit(page, unitId);
    await expect(page.getByLabel('분석 종료일')).toHaveValue(kstDate(summary.period.end));
  }

  test('적재 기간과 기본 분석 기간이 KST 날짜로 잡힌다', async ({ page }) => {
    // 시나리오 데이터는 KST 2023-01-01 00:00 에 시작한다 = UTC 2022-12-31 15:00.
    // UTC 날짜를 쓰면 시작일이 하루 앞당겨지고, 오전 9시 전에 끝나는 데이터는 마지막 날이 빠진다(specs/21 §9).
    const summary = await admin.get<any>(`/api/units/${unitId}/data-summary/`);
    const start = kstDate(summary.period.start);
    const end = kstDate(summary.period.end);
    expect(start).toBe('2023-01-01');

    await openRunPage(page);

    await expect(page.getByText(`이 호기에 적재된 기간: ${start} ~ ${end}`)).toBeVisible();
    await page.getByRole('button', { name: '최근 12개월' }).click();
    await expect(page.getByLabel('분석 시작일')).toHaveValue(start); // 6개월치라 적재 시작일에서 멈춘다
    await expect(page.getByLabel('분석 종료일')).toHaveValue(end);
  });

  const runButton = (page: Page) => page.getByRole('button', { name: '분석 실행' });
  // 분석 진행 표시만 가리킨다. 대시보드에도 .progress-bar 가 여럿 있어 그냥 쓰면 이동 후 오인한다.
  const progress = (page: Page) => page.locator('.progress-bar-animated');

  test('분석 실행 버튼을 연달아 눌러도 요청은 한 번만 간다', async ({ page }) => {
    test.slow();
    const posts: string[] = [];
    page.on('request', (req) => {
      if (req.method() === 'POST' && /\/api\/analysis-runs\/$/.test(req.url())) posts.push(req.url());
    });
    await openRunPage(page);

    await runButton(page).dblclick();

    await expect(page).toHaveURL(/\/dashboard$/, { timeout: 120_000 });
    expect(posts).toHaveLength(1);
  });

  test('AC-16-4: 분석 중 다른 화면에 갔다 돌아와도 진행 상태가 복원되고 끝까지 간다', async ({ page }) => {
    test.slow();
    await openRunPage(page);
    const before = (await admin.get<any>(`/api/analysis-runs/?unit_id=${unitId}&status=SUCCESS`)).count;

    await runButton(page).click();
    await expect(progress(page)).toBeVisible();

    await page.locator('.ui-sidebar').getByRole('link', { name: '정비 이력' }).click();
    await expect(page).toHaveURL(/\/maintenance$/);
    await page.locator('.ui-sidebar').getByRole('link', { name: '분석 실행' }).click();

    // 돌아오면 진행 표시가 다시 보이고, 실행 버튼은 잠겨 있어야 한다(두 번째 실행 방지).
    await expect(progress(page)).toBeVisible();
    await expect(runButton(page)).toBeDisabled();

    // 끝나면 진행 표시가 사라지고 버튼이 다시 풀린다.
    await expect(progress(page)).toHaveCount(0, { timeout: 120_000 });
    await expect(runButton(page)).toBeEnabled();
    await expect
      .poll(async () => (await admin.get<any>(`/api/analysis-runs/?unit_id=${unitId}&status=SUCCESS`)).count)
      .toBe(before + 1);
  });

  test('AC-16-4: 분석 중 새로고침해도 진행 상태가 복원된다', async ({ page }) => {
    test.slow();
    await openRunPage(page);

    await runButton(page).click();
    await expect(progress(page)).toBeVisible();

    await page.reload();

    await expect(progress(page)).toBeVisible();
    await expect(progress(page)).toHaveCount(0, { timeout: 120_000 });
    await expect(page.getByRole('alert')).toHaveCount(0);
  });

  test('분석이 진행 중인 호기에 또 실행하면 이미 실행 중이라고 안내한다', async ({ page }) => {
    test.slow();
    await openRunPage(page);

    // 다른 탭(같은 세션)에서 같은 호기를 먼저 돌린다. 탭마다 sessionStorage 가 달라 진행 상태를 공유하지 않는다.
    const other = await page.context().newPage();
    await openRunPage(other);
    await runButton(other).click();
    await expect(progress(other)).toBeVisible();

    await runButton(page).click();

    // 호기당 분석 동시 1건 — 409 ANALYSIS_ALREADY_RUNNING (specs/15 §1).
    await expect(page.getByRole('alert')).toBeVisible();
    await expect(page).toHaveURL(/\/analysis\/new$/);

    await expect(page.getByRole('alert')).toContainText('진행 중인 분석이 있습니다');
    // 먼저 실행한 탭은 끝나면 대시보드로 간다.
    await expect(other).toHaveURL(/\/dashboard$/, { timeout: 120_000 });
    await other.close();
  });
});
