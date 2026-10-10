/**
 * 소개 화면 · 회원가입 · 헤더 로그인 · 로그아웃 (specs/01, specs/11 AC-11-1·2·4).
 *
 * 로그인 스로틀(IP 분당 10회)을 아끼려고 폼 로그인은 꼭 필요한 시나리오에서만 한다.
 */
import { expect, test } from '@playwright/test';

import { Api, uniqueUsername } from './support/api';
import { MUTATES } from './support/env';
import { loginPanel, loginViaHeader } from './support/ui';

test.describe('비로그인', () => {
  test.use({ storageState: { cookies: [], origins: [] } });

  test('소개 화면은 로그인 없이 열리고 세 기능과 사용 방법을 보여 준다', async ({ page }) => {
    await page.goto('/');

    await expect(page.getByRole('heading', { name: 'HRSG 레퍼런스 앱', level: 1 })).toBeVisible();
    for (const title of ['질의응답', '계산기', '플랜트 데이터 요청 체크리스트']) {
      await expect(page.getByRole('heading', { name: title, level: 3 })).toBeVisible();
    }
    await expect(page.getByRole('heading', { name: '사용 방법' })).toBeVisible();
  });

  test('로그인 버튼은 헤더 상단 우측에 있다', async ({ page }) => {
    await page.goto('/');
    const button = page.getByRole('banner').getByRole('button', { name: '로그인' });
    const box = await button.boundingBox();
    const viewport = page.viewportSize()!;

    expect(box!.x + box!.width).toBeGreaterThan(viewport.width * 0.8);
    expect(box!.y).toBeLessThan(80);
  });

  test('보호 경로로 오면 소개 화면에서 로그인 패널이 열린다', async ({ page }) => {
    await page.goto('/calculator');

    await expect(page).toHaveURL(/\/$/);
    await expect(loginPanel(page)).toBeVisible();
    await expect(loginPanel(page).getByLabel('ID')).toBeFocused();
  });

  test('틀린 비밀번호는 계정 존재 여부를 알리지 않는다', async ({ page }) => {
    await page.goto('/');
    await loginViaHeader(page, { username: 'admin', password: 'wrong-pass-1' });

    await expect(loginPanel(page).getByRole('alert')).toHaveText('ID 또는 비밀번호가 올바르지 않습니다.');
  });

  test(`가입 신청 → 승인 대기 로그인 거부 → 승인 후 원래 경로로 로그인 ${MUTATES}`, async ({ page }) => {
    const username = uniqueUsername('signup');
    const password = 'e2e-pass-123';

    await page.goto('/signup');
    await page.getByLabel('ID').fill(username);
    await page.getByLabel('ID').blur();
    await expect(page.getByText('사용할 수 있는 ID 입니다.')).toBeVisible();
    await page.getByRole('textbox', { name: '비밀번호', exact: true }).fill(password);
    await page.getByLabel('비밀번호 확인').fill(password);
    await page.getByLabel('성명').fill('가입 테스트');
    await page.getByLabel('소속').fill('E2E 협력사');
    await page.getByRole('button', { name: '가입 신청' }).click();

    await expect(page.getByRole('heading', { name: '가입 신청이 접수되었습니다' })).toBeVisible();

    // 승인 전: 맞는 비밀번호여도 들어갈 수 없다(AC-01-1).
    await page.goto('/checklist');
    await loginViaHeader(page, { username, password });
    await expect(loginPanel(page).getByRole('alert')).toContainText('승인 대기');

    // 관리자가 승인하면 같은 패널에서 바로 로그인되고, 원래 가려던 경로로 돌아간다(AC-11-1).
    const admin = await Api.asAdmin();
    const [user] = (await admin.get(`/api/admin/users/?search=${username}`)).results;
    expect((await admin.post(`/api/admin/users/${user.id}/approve/`)).status()).toBe(200);
    await admin.dispose();

    await loginPanel(page).getByRole('button', { name: '로그인' }).click();
    await expect(page).toHaveURL(/\/checklist$/);
    await expect(page.getByRole('heading', { name: '플랜트 데이터 요청 체크리스트' })).toBeVisible();

    // 새로고침해도 로그인이 유지된다(AC-11-4).
    await page.reload();
    await expect(page.getByRole('banner').getByRole('button', { name: /가입 테스트/ })).toBeVisible();
  });

  test('비밀번호 확인이 다르면 가입 신청을 막는다', async ({ page }) => {
    await page.goto('/signup');
    await page.getByRole('textbox', { name: '비밀번호', exact: true }).fill('e2e-pass-123');
    await page.getByLabel('비밀번호 확인').fill('different-1');

    await expect(page.getByText('비밀번호가 일치하지 않습니다.')).toBeVisible();
    await expect(page.getByRole('button', { name: '가입 신청' })).toBeDisabled();
  });
});

test.describe('로그인한 일반 사용자', () => {
  test.use({ storageState: { cookies: [], origins: [] } });

  test(`관리자 메뉴가 없고 관리자 경로로 가면 홈으로 돌아간다, 로그아웃 ${MUTATES}`, async ({ page }) => {
    const user = await Api.approvedUser({ fullName: '일반 사용자' });
    await page.goto('/');
    await loginViaHeader(page, user);
    await expect(page).toHaveURL(/\/home$/);

    const menu = page.getByRole('banner').getByRole('button', { name: /일반 사용자/ });
    await menu.click();
    await expect(page.getByRole('link', { name: '관리자 모드' })).toHaveCount(0);

    await page.goto('/admin/users');
    await expect(page).toHaveURL(/\/home$/);
    await expect(page.getByText('관리자 권한이 필요합니다.')).toBeVisible();

    await page.getByRole('banner').getByRole('button', { name: /일반 사용자/ }).click();
    await page.getByRole('button', { name: '로그아웃' }).click();
    await expect(page).toHaveURL(/\/$/);
    await expect(page.getByRole('banner').getByRole('button', { name: '로그인' })).toBeVisible();
  });
});

test.describe('관리자', () => {
  test('홈에 세 기능 카드가 있고, 준비 중 기능은 안내를 보인다', async ({ page }) => {
    await page.goto('/home');

    for (const title of ['질의응답', '계산기', '플랜트 데이터 요청 체크리스트']) {
      await expect(page.getByRole('link', { name: new RegExp(title) }).first()).toBeVisible();
    }
    await page.getByRole('main').getByRole('link', { name: /체크리스트/ }).click();
    await expect(page).toHaveURL(/\/checklist$/);
    await expect(page.getByText('준비 중인 기능입니다')).toBeVisible();
  });
});
