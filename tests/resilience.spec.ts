/**
 * 비정상 상황에서의 화면 — 세션 만료, 없는 경로, 서버 오류, 입력 실수.
 * 정상 경로만 보면 놓치는 "조용히 깨지는" 경우를 잡는다. 읽기만 하므로 배포본에도 돌릴 수 있다.
 */
import { expect, test, type Route } from '@playwright/test';

import { Api, rows } from './support/api';
import { BASE_URL } from './support/env';
import { pageTitle, selectUnit } from './support/ui';

test('세션이 만료되면 다음 동작에서 로그인 화면으로 보낸다', async ({ page }) => {
  await page.goto('/dashboard');
  await expect(pageTitle(page)).toHaveText('대시보드');
  // 진행 중인 요청의 응답이 세션 쿠키를 다시 심으므로, 요청이 모두 끝난 뒤에 지워야 만료가 재현된다.
  await page.waitForLoadState('networkidle');

  // 서버 세션 만료와 같은 효과 — 이 브라우저 컨텍스트의 쿠키만 지운다(저장된 관리자 세션은 그대로).
  await page.context().clearCookies();
  // 클라이언트는 API 가 401 을 줄 때 만료를 안다. 호기가 없으면 API 를 부르지 않는 화면도 있어(빈 DB 의 CI),
  // 데이터와 무관하게 항상 목록을 읽는 사용자 관리 화면으로 간다.
  await page.locator('.ui-sidebar').getByRole('link', { name: '관리자 콘솔' }).click();

  // 401 을 받으면 로그인으로 보낸다(specs/16 §6). 빈 화면이나 오류 토스트에 멈추면 안 된다.
  await expect(page).toHaveURL(/\/login\?redirect=(%2F|\/)admin(%2F|\/)users$/);
});

test('없는 경로는 404 화면을 보여주고 대시보드로 돌아갈 수 있다', async ({ page }) => {
  await page.goto('/no-such-page');

  await expect(page.getByText('페이지를 찾을 수 없습니다.')).toBeVisible();
  await page.getByRole('link', { name: '대시보드로 이동' }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
});

test('관리자 콘솔의 없는 하위 경로도 404 로 떨어진다', async ({ page }) => {
  await page.goto('/admin/no-such-page');
  await expect(page.getByText('페이지를 찾을 수 없습니다.')).toBeVisible();
});

test('비밀번호 변경에서 새 비밀번호 확인이 다르면 서버에 보내지 않고 안내한다', async ({ page }) => {
  const sent: string[] = [];
  page.on('request', (req) => {
    if (req.url().includes('/api/auth/change-password/')) sent.push(req.url());
  });
  await page.goto('/profile');

  await page.getByLabel('현재 비밀번호').fill('anything');
  await page.getByLabel('새 비밀번호', { exact: true }).fill('new-pass-1234');
  await page.getByLabel('새 비밀번호 확인').fill('new-pass-9999');
  await page.getByRole('button', { name: /변경/ }).click();

  await expect(page.getByRole('alert')).toContainText('새 비밀번호가 서로 일치하지 않습니다.');
  expect(sent).toEqual([]);
});

const serverError = (route: Route) =>
  route.fulfill({
    status: 500,
    contentType: 'application/json',
    body: JSON.stringify({ error: { code: 'INTERNAL_ERROR', message: '테스트용 서버 오류' } }),
  });

test('대시보드가 결과를 못 읽으면 "분석 결과 없음" 이 아니라 오류와 다시 시도를 보여준다', async ({ page }) => {
  const api = await Api.asAdmin();
  const unitId = await api.latestAnalyzedUnitId();
  await api.dispose();
  test.skip(unitId === null, '성공한 분석이 있는 호기가 없다');

  const errors: string[] = [];
  page.on('pageerror', (err) => errors.push(err.message));
  await page.goto('/dashboard');
  await selectUnit(page, unitId!);
  await page.waitForLoadState('networkidle');
  await page.route('**/api/analysis-runs/**', serverError);

  await page.reload();

  // 결과가 있는 호기인데 서버가 실패했다. "아직 분석 결과가 없습니다" 로 보이면 장애를 데이터 부재로 오인한다.
  const alert = page.getByRole('alert').filter({ hasText: '분석 결과를 불러오지 못했습니다.' });
  await expect(alert).toBeVisible();
  await expect(page.getByText('아직 분석 결과가 없습니다.')).toHaveCount(0);

  // 서버가 돌아오면 다시 시도로 회복된다.
  await page.unroute('**/api/analysis-runs/**');
  await alert.getByRole('button', { name: '다시 시도' }).click();
  await expect(page.locator('.ui-stat-label', { hasText: '현재 오염도 지수' })).toBeVisible();

  // 사이드바·내비바는 살아 있고, 처리되지 않은 스크립트 오류가 없어야 한다.
  await page.locator('.ui-sidebar').getByRole('link', { name: '정비 이력' }).click();
  await expect(pageTitle(page)).toHaveText('정비 이력');
  expect(errors, '처리되지 않은 스크립트 오류').toEqual([]);
});

test('호기를 바꿨는데 새 호기 결과를 못 읽으면 이전 호기 결과를 남겨 두지 않는다', async ({ page }) => {
  const api = await Api.asAdmin();
  const active = new Set(rows(await api.get<any>('/api/units/?is_active=true')).map((u: any) => u.id));
  const runs = rows(await api.get<any>('/api/analysis-runs/?status=SUCCESS&page_size=200')) as any[];
  await api.dispose();
  const analyzed = [...new Set(runs.map((r) => r.unit).filter((u) => active.has(u)))];
  test.skip(analyzed.length < 2, '분석이 있는 활성 호기가 2개 이상 필요하다');
  const [a, b] = analyzed;

  await page.goto('/dashboard');
  await selectUnit(page, a);
  await expect(page.locator('.ui-stat-label', { hasText: '현재 오염도 지수' })).toBeVisible();
  await page.waitForLoadState('networkidle');

  await page.route('**/api/analysis-runs/**', serverError);
  await selectUnit(page, b);

  // A 호기 KPI 가 B 호기 이름 아래에 그대로 보이면 잘못된 판단으로 이어진다.
  await expect(page.getByRole('alert').filter({ hasText: '분석 결과를 불러오지 못했습니다.' })).toBeVisible();
  await expect(page.locator('.ui-stat-label', { hasText: '현재 오염도 지수' })).toHaveCount(0);
});

test('서버에 연결할 수 없으면 로그인 화면이 이유를 알려준다', async ({ browser }) => {
  const context = await browser.newContext({ baseURL: BASE_URL, storageState: { cookies: [], origins: [] } });
  const page = await context.newPage();
  await page.route('**/api/auth/login/', (route) => route.abort('connectionrefused'));

  await page.goto('/login');
  await page.getByLabel('성명').fill('아무개');
  await page.getByLabel('사번').fill('X01');
  await page.getByLabel('비밀번호').fill('x');
  await page.getByRole('button', { name: '로그인' }).click();

  await expect(page.getByRole('alert')).toContainText('서버에 연결할 수 없습니다.');
  await expect(page.getByRole('button', { name: '로그인' })).toBeEnabled(); // 다시 시도할 수 있다
  await context.close();
});
