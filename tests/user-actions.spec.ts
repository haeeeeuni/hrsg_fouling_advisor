/**
 * 사용자 화면의 보조 기능 — 편익 재계산, 알림, 새 호기 안내, 세정 전후 비교 옵션.
 * 기존 스펙이 화면을 여는 데서 멈춘 기능들이다.
 */
import fs from 'node:fs';

import { expect, test } from '@playwright/test';

import { Api, rows } from './support/api';
import { activateE2EUnit, deactivateE2EUnit, ensureE2EAnalysis } from './support/e2e-unit';
import { MUTATES } from './support/env';
import { selectUnit } from './support/ui';

test.describe.configure({ mode: 'serial' });

test.describe(`편익 재계산 ${MUTATES}`, () => {
  let admin: Api;
  let unitId: number;

  test.beforeAll(async () => {
    test.setTimeout(180_000);
    admin = await Api.asAdmin();
    unitId = await activateE2EUnit(admin);
    await ensureE2EAnalysis(admin, unitId);
  });

  test.afterAll(async () => {
    await deactivateE2EUnit(admin, unitId);
    await admin.dispose();
  });

  test('파라미터를 바꿔 재계산하면 순편익이 바뀌고, 관리자 기본값은 그대로다', async ({ page }) => {
    const defaultsBefore = (rows(await admin.get<any>('/api/settings/')) as any[]).find((s) => s.key === 'cleaning_cost').value;
    await page.goto('/dashboard');
    await selectUnit(page, unitId);
    const net = page.locator('.card', { has: page.locator('.ui-stat-label', { hasText: '예상 회수 편익' }) }).locator('.ui-stat-value');
    await expect(net).not.toBeEmpty();
    const before = await net.innerText();

    await page.getByRole('button', { name: '파라미터 조정' }).click();
    const recalc = page.getByRole('button', { name: '재계산' });
    await expect(recalc).toBeDisabled(); // 바꾼 값이 없으면 잠긴다
    const cost = page.locator('#bp-cleaning_cost');
    const current = Number(await cost.inputValue());
    await cost.fill(String(current * 3)); // 세정비를 크게 올리면 순편익은 반드시 줄어든다
    await expect(page.locator('label[for="bp-cleaning_cost"]')).toContainText('변경');
    await recalc.click();

    await expect(page.getByText('편익을 재계산했습니다. 관리자 기본값은 변경되지 않았습니다.')).toBeVisible();
    await expect(net).not.toHaveText(before);
    const defaultsAfter = (rows(await admin.get<any>('/api/settings/')) as any[]).find((s) => s.key === 'cleaning_cost').value;
    expect(defaultsAfter).toBe(defaultsBefore);
  });
});

test.describe('알림', () => {
  test('알림 벨을 열면 목록이나 "새 알림이 없습니다" 가 나온다', async ({ page }) => {
    await page.goto('/dashboard');
    const bell = page.getByRole('button', { name: /^알림 \d+건$/ });

    await bell.click();

    const menu = page.locator('.dropdown-menu.show');
    await expect(menu).toBeVisible();
    await expect(menu.getByText('불러오는 중…')).toHaveCount(0);
    const empty = menu.getByText('새 알림이 없습니다.');
    const items = menu.locator('.badge').filter({ hasText: /경고|정보/ });
    await expect(empty.or(items.first())).toBeVisible();
  });

  // 등급 상승 알림은 분석 결과에 따라 생겨 테스트에서 일부러 만들기 어렵다. 응답을 주입해 화면 동작만 본다.
  const ALERT = {
    id: 9101,
    level: 'WARNING',
    title: 'E2E 등급 상승 알림',
    message: '오염도 등급이 주의에서 경고로 올라갔습니다.',
    created_at: '2026-10-07T09:00:00+09:00',
    is_read: false,
  };

  test('읽지 않은 알림이 있으면 개수를 보여주고, 모두 읽음을 누르면 0 이 된다', async ({ page }) => {
    let readAll = 0;
    await page.route('**/api/notifications/**', (route) => {
      const url = route.request().url();
      if (url.includes('/read-all/')) {
        readAll += 1;
        return route.fulfill({ json: { updated: 1 } });
      }
      if (url.includes('unread=true')) return route.fulfill({ json: { count: 0, results: [] } }); // 대시보드 배너
      return route.fulfill({ json: { count: 1, unread_count: readAll ? 0 : 1, results: [{ ...ALERT, is_read: readAll > 0 }] } });
    });
    await page.goto('/dashboard');

    await page.getByRole('button', { name: '알림 1건' }).click();
    await expect(page.locator('.dropdown-menu.show')).toContainText(ALERT.title);
    await page.getByRole('button', { name: '모두 읽음' }).click();

    await expect(page.getByRole('button', { name: '알림 0건' })).toBeVisible();
    expect(readAll).toBe(1);
  });

  test('대시보드 상단의 등급 상승 배너는 "알림 확인" 으로 닫고 읽음 처리한다', async ({ page }) => {
    const api = await Api.asAdmin();
    const unit = rows(await api.get<any>('/api/units/?is_active=true'))[0] as any;
    await api.dispose();
    test.skip(!unit, '활성 호기가 없다');

    const read: string[] = [];
    await page.route('**/api/notifications/**', (route) => {
      const url = route.request().url();
      if (route.request().method() === 'POST') {
        read.push(url);
        return route.fulfill({ json: {} });
      }
      if (url.includes('unread=true')) return route.fulfill({ json: { count: 1, results: [{ ...ALERT, unit: unit.id }] } });
      return route.fulfill({ json: { count: 0, unread_count: 0, results: [] } });
    });
    await page.goto('/dashboard');
    await selectUnit(page, unit.id);

    const banner = page.getByRole('alert').filter({ hasText: ALERT.title });
    await expect(banner).toBeVisible();
    await banner.getByRole('button', { name: '알림 확인' }).click();

    await expect(banner).toHaveCount(0);
    expect(read.some((u) => u.includes(`/notifications/${ALERT.id}/read/`))).toBe(true);
  });
});

test.describe(`새 호기 데이터 올리기 안내 ${MUTATES}`, () => {
  const CODE = 'E2ENEW';
  let admin: Api;

  async function removeUnit() {
    for (const u of rows(await admin.get<any>('/api/units/')) as any[]) if (u.code === CODE) await admin.delete(`/api/units/${u.id}/`);
  }

  test.beforeAll(async () => {
    admin = await Api.asAdmin();
    await removeUnit();
    const res = await admin.post('/api/units/', { code: CODE, name: '매핑 전 호기', rated_power_mw: 160, min_load_mw: 60 });
    expect(res.status(), await res.text()).toBe(201);
  });

  test.afterAll(async () => {
    await removeUnit();
    await admin.dispose();
  });

  test('매핑이 끝나지 않은 호기와 빠진 항목을 보여주고, 관리 화면으로 보낸다', async ({ page }) => {
    await page.goto('/upload');
    await page.getByRole('tab', { name: '새 호기 데이터 올리기' }).click();

    const pending = page.locator('.alert-warning', { hasText: '매핑이 끝나지 않은 호기' });
    await expect(pending).toContainText(`${CODE} — 매핑 전 호기`);
    await expect(pending).toContainText('필수 표준 항목이 매핑되지 않았습니다.');

    await page.getByRole('link', { name: '호기 관리로 이동' }).click();
    await expect(page).toHaveURL(/\/admin\/units$/);
  });
});

test.describe(`세정 전후 비교 옵션 ${MUTATES}`, () => {
  let unitId: number | null = null;

  test.beforeAll(async () => {
    const api = await Api.asAdmin();
    const active = new Set((rows(await api.get<any>('/api/units/?is_active=true')) as any[]).map((u) => u.id));
    const events = rows(await api.get<any>('/api/cleaning-events/?page_size=200')) as any[];
    unitId = events.map((e) => e.unit).find((u) => active.has(u)) ?? null;
    await api.dispose();
  });

  test('비교 윈도를 바꾸면 그 길이로 비교하고, 이력에서 다시 열고, 엑셀로 내려받는다', async ({ page }) => {
    test.skip(unitId === null, '세정 이력이 있는 활성 호기가 없다');
    test.slow();
    await page.goto('/comparison');
    await selectUnit(page, unitId!);

    await page.getByLabel('비교 윈도(일)').fill('14');
    await page.getByRole('button', { name: '비교 생성' }).click();

    const result = page.locator('.card', { has: page.getByRole('heading', { name: '비교 결과' }) });
    await expect(result).toBeVisible({ timeout: 60_000 });
    const range = await result.getByText(/세정 전 \d{4}-\d{2}-\d{2} ~/).innerText();
    const [, from, to] = range.match(/세정 전 (\d{4}-\d{2}-\d{2}) ~ (\d{4}-\d{2}-\d{2})/)!;
    const days = (Date.parse(to) - Date.parse(from)) / 86_400_000;
    expect(days).toBeGreaterThanOrEqual(13);
    expect(days).toBeLessThanOrEqual(15);

    // 이력의 첫 줄(방금 만든 비교)을 다시 연다.
    const history = page.locator('table', { has: page.getByRole('columnheader', { name: '회복률' }) });
    await history.locator('tbody tr').first().getByRole('button', { name: '보기' }).click();
    await expect(result).toBeVisible();

    const pending = page.waitForEvent('download', { timeout: 60_000 });
    await result.getByRole('button', { name: '엑셀', exact: true }).click();
    const download = await pending;
    expect(download.suggestedFilename()).toMatch(/\.xlsx$/);
    expect(fs.readFileSync(await download.path()).subarray(0, 2).toString('latin1')).toBe('PK');
  });
});
