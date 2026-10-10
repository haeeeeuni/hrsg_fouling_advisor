/**
 * 내 정보 — 비밀번호 변경 (specs/01 §5).
 *
 * 관리자 비밀번호를 바꾸면 모든 테스트가 같이 쓰는 세션이 깨지므로 전용 사용자로 한다.
 * 로그인 스로틀(분당 10회)을 아끼려고 한 번 로그인한 페이지를 이 파일의 테스트가 함께 쓴다.
 */
import { expect, test, type Page } from '@playwright/test';

import { Api, rows } from './support/api';
import { BASE_URL, MUTATES } from './support/env';
import { loginViaForm } from './support/ui';

const USER = { fullName: 'E2E내정보', employeeNo: 'E2EPROF01', password: 'e2e-first-pass' };
const NEW_PASSWORD = 'e2e-second-pass';

test.describe.configure({ mode: 'serial' });

test.describe(`비밀번호 변경 ${MUTATES}`, () => {
  let admin: Api;
  let page: Page;

  async function removeUser() {
    for (const u of rows(await admin.get<any>(`/api/users/?search=${USER.employeeNo}`)) as any[]) {
      if (u.employee_no === USER.employeeNo) await admin.delete(`/api/users/${u.id}/?hard=true`);
    }
  }

  test.beforeAll(async ({ browser }) => {
    admin = await Api.asAdmin();
    await removeUser();
    const res = await admin.post('/api/users/', {
      full_name: USER.fullName,
      employee_no: USER.employeeNo,
      role: 'USER',
      initial_password: USER.password,
    });
    expect(res.status(), await res.text()).toBe(201);

    const context = await browser.newContext({ baseURL: BASE_URL, storageState: { cookies: [], origins: [] } });
    page = await context.newPage();
    await page.goto('/login');
    await loginViaForm(page, USER);
    await expect(page).toHaveURL(/\/dashboard$/);
  });

  test.afterAll(async () => {
    await page?.context().close();
    await removeUser();
    await admin.dispose();
  });

  async function submit(current: string, next: string, confirm = next) {
    await page.goto('/profile');
    await page.getByLabel('현재 비밀번호').fill(current);
    await page.getByLabel('새 비밀번호', { exact: true }).fill(next);
    await page.getByLabel('새 비밀번호 확인').fill(confirm);
    await page.getByRole('button', { name: '변경', exact: true }).click();
  }

  test('계정 정보가 보이고, 초기 비밀번호면 대시보드가 변경을 권한다', async () => {
    await page.goto('/profile');
    await expect(page.locator('dd').filter({ hasText: USER.employeeNo })).toBeVisible();

    await page.goto('/dashboard');
    await expect(page.getByText('초기 비밀번호를 변경해 주세요.')).toBeVisible();
    await page.getByRole('link', { name: '비밀번호 변경' }).click();
    await expect(page).toHaveURL(/\/profile$/);
  });

  test('현재 비밀번호가 틀리면 바꾸지 않는다', async () => {
    await submit('wrong-current', NEW_PASSWORD);

    await expect(page.locator('.alert-danger')).toContainText('현재 비밀번호가 올바르지 않습니다.');
  });

  test('기존과 같은 비밀번호로는 바꿀 수 없다', async () => {
    await submit(USER.password, USER.password);

    await expect(page.locator('.alert-danger')).toContainText('기존 비밀번호와 다른 값을 입력해 주세요.');
  });

  test('바꾸면 입력란이 비워지고, 대시보드의 변경 권고가 사라지며, 새 비밀번호로 로그인된다', async () => {
    await submit(USER.password, NEW_PASSWORD);

    await expect(page.getByText('비밀번호가 변경되었습니다.')).toBeVisible();
    await expect(page.getByLabel('현재 비밀번호')).toHaveValue('');

    await page.goto('/dashboard');
    await expect(page.getByText('초기 비밀번호를 변경해 주세요.')).toHaveCount(0);

    const relogin = await Api.login({ ...USER, password: NEW_PASSWORD });
    await relogin.dispose();
  });
});
