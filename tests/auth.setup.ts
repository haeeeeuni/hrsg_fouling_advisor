/**
 * 관리자 로그인 세션을 한 번 만들어 저장한다 (specs/14 §4.3).
 *
 * 다른 테스트와 API 헬퍼(Api.asAdmin)는 이 storageState 로 시작하므로 매번 로그인하지 않는다.
 * 로그인 스로틀(IP 기준 분당 10회)에 걸리지 않게 하는 장치이기도 하다.
 * 직전 실행이 저장한 세션이 아직 살아 있으면 다시 로그인하지 않는다.
 */
import fs from 'node:fs';

import { expect, request, test as setup } from '@playwright/test';

import { ADMIN, BASE_URL, PATHS } from './support/env';
import { loginViaHeader } from './support/ui';

async function savedSessionIsValid(): Promise<boolean> {
  if (!fs.existsSync(PATHS.adminState)) return false;
  const ctx = await request.newContext({ baseURL: BASE_URL, storageState: PATHS.adminState });
  try {
    const res = await ctx.get('/api/auth/me/');
    const body = res.ok() ? await res.json() : null;
    return Boolean(body?.authenticated && body.user?.username === ADMIN.username);
  } finally {
    await ctx.dispose();
  }
}

setup('관리자 세션 저장', async ({ page }) => {
  if (await savedSessionIsValid()) return;

  await page.goto('/');
  await loginViaHeader(page, ADMIN);
  await expect(page).toHaveURL(/\/home$/);
  await page.context().storageState({ path: PATHS.adminState });
});
