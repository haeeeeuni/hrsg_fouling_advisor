/**
 * 플랜트 데이터 요청 체크리스트 (specs/07 AC-07-1~7).
 * 요청 건은 본인 것만 보이므로, 관리자 세션으로 만든 요청 건은 테스트가 끝나며 지운다.
 */
import { expect, test, type Page } from '@playwright/test';

import { Api } from './support/api';
import { BASE_URL, MUTATES, VIEWPORTS } from './support/env';

async function createRequest(page: Page, title: string) {
  await page.goto('/checklist');
  await page.getByLabel('새 요청 건 이름').fill(title);
  await page.getByRole('button', { name: '요청 건 만들기' }).click();
  await expect(page.getByRole('heading', { name: title, level: 1 })).toBeVisible();
  return Number(page.url().split('/').pop());
}

async function deleteRequest(id: number) {
  const api = await Api.asAdmin();
  await api.delete(`/api/checklist/requests/${id}/`);
  await api.dispose();
}

function stateGroup(page: Page, itemName: string) {
  return page.getByRole('radiogroup', { name: `${itemName} 수신 상태` });
}

test(`새 요청 건은 항목이 복사되고 0 % 에서 시작한다 ${MUTATES}`, async ({ page }) => {
  const id = await createRequest(page, `E2E 요청 ${Date.now()}`);

  await expect(page.getByTestId('progress-text').first()).toContainText('· 0%');
  await expect(page.getByRole('heading', { name: '핀치·어프로치', level: 2 })).toBeVisible();
  await expect(page.getByRole('heading', { name: '일정·현장 조건', level: 2 })).toBeVisible();
  await expect(page.getByText('계산기 입력').first()).toBeVisible();
  await deleteRequest(id);
});

test(`필수 항목을 모두 받거나 해당 없음이면 완료가 된다 ${MUTATES}`, async ({ page }) => {
  const id = await createRequest(page, `E2E 완료 ${Date.now()}`);
  const api = await Api.asAdmin();
  const detail = await api.get(`/api/checklist/requests/${id}/`);
  const required = detail.items.filter((i: any) => i.is_required);
  // 마지막 하나만 남기고 API 로 받음 처리 — 화면에서는 마지막 항목을 '해당 없음' 으로 바꾼다.
  for (const item of required.slice(0, -1)) {
    await api.patch(`/api/checklist/requests/${id}/items/${item.id}/`, { state: 'RECEIVED' });
  }
  await api.dispose();
  await page.reload();
  await expect(page.getByTestId('request-status')).toHaveText('진행 중');

  const last = required[required.length - 1].name_ko;
  await stateGroup(page, last).getByRole('radio', { name: '해당 없음' }).click();

  await expect(page.getByTestId('request-status')).toHaveText('완료');
  await expect(page.getByTestId('progress-text').first()).toContainText('100%');
  await deleteRequest(id);
});

test(`받음·메모가 저장되어 새로고침 후에도 남는다 ${MUTATES}`, async ({ page }) => {
  const id = await createRequest(page, `E2E 메모 ${Date.now()}`);

  await stateGroup(page, 'GT 출력').getByRole('radio', { name: '받음' }).click();
  await expect(stateGroup(page, 'GT 출력').getByRole('radio', { name: '받음' })).toHaveAttribute('aria-checked', 'true');
  const memo = page.getByLabel('GT 출력 메모');
  await memo.fill('10/15 메일로 받음');
  await memo.blur();
  await page.waitForResponse((r) => r.url().includes(`/items/`) && r.request().method() === 'PATCH');

  await page.reload();
  await expect(stateGroup(page, 'GT 출력').getByRole('radio', { name: '받음' })).toHaveAttribute('aria-checked', 'true');
  await expect(page.getByLabel('GT 출력 메모')).toHaveValue('10/15 메일로 받음');
  await deleteRequest(id);
});

test(`미수신 항목을 이메일 본문으로 복사한다 — 한국어·영어 ${MUTATES}`, async ({ page, context }) => {
  await context.grantPermissions(['clipboard-read', 'clipboard-write'], { origin: BASE_URL });
  const id = await createRequest(page, `E2E 복사 ${Date.now()}`);
  await stateGroup(page, 'GT 출력').getByRole('radio', { name: '받음' }).click();
  await expect(stateGroup(page, 'GT 출력').getByRole('radio', { name: '받음' })).toHaveAttribute('aria-checked', 'true');

  await page.getByRole('button', { name: '이메일 본문 복사' }).click();
  await page.getByRole('button', { name: '미수신 항목 — 한국어' }).click();
  await expect(page.getByText('미수신 항목을 한국어 이메일 본문으로 복사했습니다.')).toBeVisible();
  const korean = await page.evaluate(() => navigator.clipboard.readText());
  expect(korean).toContain('[가스터빈]');
  expect(korean).toContain('[필수]');
  expect(korean).not.toContain('- GT 출력 (MW)');

  await page.getByRole('button', { name: '이메일 본문 복사' }).click();
  await page.getByRole('button', { name: '미수신 항목 — English' }).click();
  await expect(page.getByText('영어 이메일 본문으로 복사했습니다.')).toBeVisible();
  const english = await page.evaluate(() => navigator.clipboard.readText());
  expect(english).toContain('[Gas Turbine]');
  expect(english).toContain('[Required]');
  await deleteRequest(id);
});

test(`관리자가 템플릿을 바꿔도 기존 요청 건은 그대로고, 새 항목은 고를 때만 추가된다 ${MUTATES}`, async ({ page }) => {
  const id = await createRequest(page, `E2E 템플릿 ${Date.now()}`);
  const api = await Api.asAdmin();
  const name = `E2E 새 항목 ${Date.now()}`;
  const created = await (await api.post('/api/admin/checklist-items/', { category: 'GT', name_ko: name, name_en: 'E2E item' })).json();

  await page.reload();
  await expect(page.getByText(name)).toHaveCount(0);
  await page.getByRole('button', { name: '새 항목 추가하기' }).click();
  await expect(page.getByText(name)).toBeVisible();

  await api.delete(`/api/admin/checklist-items/${created.id}/`); // 사용 중지 — 다른 테스트에 영향 없게
  await api.dispose();
  await deleteRequest(id);
});

test(`다른 사용자의 요청 건은 보이지 않는다 ${MUTATES}`, async ({ page, browser }) => {
  const id = await createRequest(page, `E2E 비공개 ${Date.now()}`);
  const user = await Api.approvedUser();
  const other = await browser.newContext({ baseURL: BASE_URL, storageState: { cookies: [], origins: [] } });
  const otherPage = await other.newPage();
  await otherPage.goto('/');
  await otherPage.getByRole('banner').getByRole('button', { name: '로그인' }).click();
  await otherPage.getByRole('dialog', { name: '로그인' }).getByLabel('ID').fill(user.username);
  await otherPage.getByRole('dialog', { name: '로그인' }).getByLabel('비밀번호').fill(user.password);
  await otherPage.getByRole('dialog', { name: '로그인' }).getByRole('button', { name: '로그인' }).click();
  await expect(otherPage).toHaveURL(/\/home$/);

  await otherPage.goto(`/checklist/${id}`);
  await expect(otherPage.getByText('요청 건을 찾을 수 없습니다.')).toBeVisible();
  await other.close();
  await deleteRequest(id);
});

test.describe('모바일', () => {
  test.use({ viewport: VIEWPORTS.mobile });

  test(`360~390px 폭에서도 체크·메모·복사가 된다 ${MUTATES}`, async ({ page, context }) => {
    await context.grantPermissions(['clipboard-read', 'clipboard-write'], { origin: BASE_URL });
    const id = await createRequest(page, `E2E 모바일 ${Date.now()}`);

    await stateGroup(page, 'GT 출력').getByRole('radio', { name: '받음' }).click();
    await expect(stateGroup(page, 'GT 출력').getByRole('radio', { name: '받음' })).toHaveAttribute('aria-checked', 'true');
    await page.getByLabel('GT 출력 메모').fill('모바일 메모');
    await page.getByRole('button', { name: '이메일 본문 복사' }).click();
    await page.getByRole('button', { name: '전체 항목 — 한국어 (처음 요청)' }).click();
    await expect(page.getByText('전체 항목을 한국어 이메일 본문으로 복사했습니다.')).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)).toBeLessThanOrEqual(0);
    await deleteRequest(id);
  });
});
