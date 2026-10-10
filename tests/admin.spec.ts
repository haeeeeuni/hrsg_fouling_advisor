/**
 * 관리자 모드 — 가입 승인 · 사용자 · 설정 · 감사 로그 (specs/01 §4·§7, specs/08).
 * 관리자 세션(auth.setup.ts)으로 시작한다.
 */
import { expect, test } from '@playwright/test';

import { Api } from './support/api';
import { BASE_URL, MUTATES } from './support/env';
import { loginPanel, loginViaHeader } from './support/ui';

test(`가입 신청을 사유와 함께 반려하면 그 사유가 로그인 때 보인다 ${MUTATES}`, async ({ page, browser }) => {
  const user = await Api.signup({ fullName: '반려 대상' });

  await page.goto('/admin/signups');
  const card = page.getByRole('article', { name: `반려 대상(${user.username}) 가입 신청` });
  await card.getByRole('button', { name: '반려' }).click();
  await card.getByLabel(/반려 사유/).fill('소속을 확인할 수 없습니다');
  await card.getByRole('button', { name: '반려 확정' }).click();
  await expect(page.getByText(`${user.username}) 님의 가입을 반려했습니다.`)).toBeVisible();
  await expect(card).toHaveCount(0);

  await page.getByRole('button', { name: '반려', exact: true }).click();
  await expect(page.getByRole('article', { name: `반려 대상(${user.username}) 가입 신청` })).toContainText(
    '소속을 확인할 수 없습니다',
  );

  // 반려된 사용자는 로그인 시 사유를 본다(AC-01-3). 관리자 세션을 건드리지 않게 빈 컨텍스트로 연다.
  const guest = await browser.newContext({ baseURL: BASE_URL, storageState: { cookies: [], origins: [] } });
  const guestPage = await guest.newPage();
  await guestPage.goto('/');
  await loginViaHeader(guestPage, user);
  await expect(loginPanel(guestPage).getByRole('alert')).toContainText('소속을 확인할 수 없습니다');
  await guest.close();
});

test(`가입 승인 화면에서 승인하면 대기 목록과 배지에서 빠진다 ${MUTATES}`, async ({ page }) => {
  const user = await Api.signup({ fullName: '승인 대상' });

  await page.goto('/admin/signups');
  const card = page.getByRole('article', { name: `승인 대상(${user.username}) 가입 신청` });
  await expect(card).toContainText(user.username);
  await card.getByRole('button', { name: '승인' }).click();

  await expect(page.getByText(`${user.username}) 님을 승인했습니다.`)).toBeVisible();
  await expect(card).toHaveCount(0);

  await page.getByRole('link', { name: '사용자', exact: true }).click();
  await page.getByLabel('검색 (ID·성명·소속)').fill(user.username);
  await page.getByRole('button', { name: '검색' }).click();
  await expect(page.getByRole('row', { name: new RegExp(user.username) })).toContainText('승인');
});

test(`사용자 정보를 고치면 저장되고 감사 로그에 남는다 ${MUTATES}`, async ({ page }) => {
  const user = await Api.approvedUser({ organization: '수정 전 소속' });

  await page.goto('/admin/users');
  await page.getByLabel('검색 (ID·성명·소속)').fill(user.username);
  await page.getByRole('button', { name: '검색' }).click();
  await page.getByRole('row', { name: new RegExp(user.username) }).getByRole('button', { name: '수정' }).click();
  await page.getByLabel('소속').last().fill('수정 후 소속');
  await page.getByRole('button', { name: '저장' }).click();

  await expect(page.getByRole('row', { name: new RegExp(user.username) })).toContainText('수정 후 소속');

  await page.getByRole('link', { name: '감사 로그' }).click();
  await expect(page.getByRole('row', { name: new RegExp(user.username) }).first()).toBeVisible();
});

test('마지막 관리자는 비활성화 버튼이 자기 자신에게 보이지 않는다', async ({ page }) => {
  await page.goto('/admin/users');

  const self = page.getByRole('row', { name: /^admin 관리자/ });
  await expect(self).toBeVisible();
  await expect(self.getByRole('button', { name: '비활성화' })).toHaveCount(0);
});

test(`설정은 범위를 벗어나면 저장되지 않고, 바꾼 값은 기본값으로 되돌릴 수 있다 ${MUTATES}`, async ({ page }) => {
  await page.goto('/admin/settings');
  const input = page.getByLabel(/로그인 잠금 시간/);

  await input.fill('99999');
  await page.getByRole('button', { name: /저장/ }).click();
  await expect(page.getByRole('main').getByRole('alert')).toContainText('최댓값');

  await input.fill('7');
  await page.getByRole('button', { name: /저장/ }).click();
  await expect(page.getByText('1개 항목을 저장했습니다.')).toBeVisible();
  await expect(page.getByText('기본값과 다름')).toBeVisible();

  page.once('dialog', (dialog) => dialog.accept());
  await page.getByRole('button', { name: '기본값으로 되돌리기' }).click();
  await expect(page.getByText('기본값으로 되돌렸습니다.')).toBeVisible();
  await expect(input).toHaveValue('5');
});

test('개요에서 승인 대기 건수를 누르면 가입 승인 화면으로 간다', async ({ page }) => {
  await page.goto('/admin');

  await expect(page.getByTestId('pending-signups')).toBeVisible();
  await page.getByRole('link', { name: /승인 대기 가입 신청/ }).click();
  await expect(page).toHaveURL(/\/admin\/signups$/);
});
