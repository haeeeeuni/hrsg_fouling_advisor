/** 인증 흐름 — specs/01, specs/16 §3. 저장된 세션 없이 시작한다. */
import { expect, test } from '@playwright/test';

import { ADMIN } from './support/env';
import { loginViaForm, pageTitle } from './support/ui';

test.use({ storageState: { cookies: [], origins: [] } });

test('AC-01-4 · AC-16-1: 비로그인 접근은 로그인으로 보내고, 로그인 후 원래 경로로 돌아온다', async ({ page }) => {
  await page.goto('/maintenance');

  await expect(page).toHaveURL(/\/login\?redirect=(%2F|\/)maintenance$/);

  await loginViaForm(page, ADMIN);

  await expect(page).toHaveURL(/\/maintenance$/);
  await expect(pageTitle(page)).toHaveText('정비 이력');
});

test('AC-01-3: 성명이 틀리면 사번·비밀번호가 맞아도 로그인에 실패한다', async ({ page }) => {
  await page.goto('/login');

  await loginViaForm(page, { ...ADMIN, fullName: `${ADMIN.fullName}X` });

  await expect(page.getByRole('alert')).toBeVisible();
  await expect(page).toHaveURL(/\/login/);
});

test('로그아웃하면 로그인 화면으로 가고, 보호된 경로에 다시 들어갈 수 없다', async ({ page }) => {
  await page.goto('/login');
  await loginViaForm(page, ADMIN);
  await expect(page).toHaveURL(/\/dashboard$/);

  await page.getByRole('button', { name: new RegExp(`\\(${ADMIN.employeeNo}\\)`) }).click();
  await page.getByRole('button', { name: '로그아웃' }).click();

  await expect(page).toHaveURL(/\/login/);
  await page.goto('/dashboard');
  await expect(page).toHaveURL(/\/login\?redirect=(%2F|\/)dashboard$/);
});
