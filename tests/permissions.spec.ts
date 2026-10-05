/**
 * 권한 — 일반 사용자에게 관리자 기능이 보이지도, 열리지도 않는다 (AC-16-2, AC-01-5).
 * 테스트용 일반 사용자를 만들고 끝나면 지우므로 로컬에서만 돈다.
 */
import { expect, test } from '@playwright/test';

import { Api, rows } from './support/api';
import { MUTATES } from './support/env';
import { loginViaForm } from './support/ui';

const USER = { fullName: 'E2E사용자', employeeNo: 'E2EUSER01', password: 'e2e-pass-1234' };

test.describe(`일반 사용자 권한 ${MUTATES}`, () => {
  test.use({ storageState: { cookies: [], origins: [] } });

  let admin: Api;

  async function removeUser() {
    const found = rows(await admin.get<any>(`/api/users/?search=${USER.employeeNo}`));
    for (const u of found.filter((u: any) => u.employee_no === USER.employeeNo)) {
      await admin.delete(`/api/users/${u.id}/?hard=true`);
    }
  }

  test.beforeAll(async () => {
    admin = await Api.asAdmin();
    await removeUser(); // 직전 실행이 중간에 끊겼을 때를 대비한다.
    const res = await admin.post('/api/users/', {
      full_name: USER.fullName,
      employee_no: USER.employeeNo,
      role: 'USER',
      initial_password: USER.password,
    });
    expect(res.status(), await res.text()).toBe(201);
  });

  test.afterAll(async () => {
    await removeUser();
    await admin.dispose();
  });

  test('AC-16-2: 관리자 메뉴가 보이지 않고, URL 로 직접 들어가도 대시보드로 돌려보낸다', async ({ page }) => {
    await page.goto('/login');
    await loginViaForm(page, USER);
    await expect(page).toHaveURL(/\/dashboard$/);

    await expect(page.locator('.ui-sidebar').getByRole('link', { name: '관리자 콘솔' })).toHaveCount(0);

    await page.goto('/admin/users');
    await expect(page).toHaveURL(/\/dashboard$/);
    await expect(page.getByText('권한이 없습니다.')).toBeVisible();
  });

  test('일반 사용자도 업로드 화면에서 호기가 찾는 컬럼명을 본다(매핑 조회만 허용)', async ({ page }) => {
    await page.goto('/login');
    await loginViaForm(page, USER);
    await expect(page).toHaveURL(/\/dashboard$/);

    await page.goto('/upload');
    const guide = page.locator('.card', { has: page.getByRole('heading', { name: /이 호기가 찾는 컬럼명/ }) });
    const unitSelect = page.getByLabel('호기', { exact: true });
    // 호기 목록을 다 읽은 뒤에 판단한다(읽는 동안은 로딩 표시만 나온다).
    await expect(unitSelect.or(page.getByText('업로드 가능한 호기가 없습니다.'))).toBeVisible();
    test.skip((await unitSelect.count()) === 0, '업로드 가능한 호기가 없다');

    await expect(guide.locator('tbody tr').first()).toBeVisible();
    await expect(guide).not.toContainText('컬럼 정보를 불러오지 못했습니다.');
    // 수정 권한은 없으므로 링크 대신 요청 안내가 나온다.
    await expect(guide.getByRole('link', { name: '컬럼 매핑' })).toHaveCount(0);
    await expect(guide).toContainText('관리자에게 컬럼 매핑 변경을 요청하세요.');
  });

  test('AC-01-5: 일반 사용자가 관리자 API 를 부르면 403 을 받는다', async () => {
    const user = await Api.login(USER);
    const res = await user.post('/api/units/', { code: 'NOPE', name: 'x', rated_power_mw: 1, min_load_mw: 1 });
    expect(res.status()).toBe(403);
    // 매핑은 조회만 열려 있고 수정은 여전히 관리자 전용이다.
    const unit = rows(await user.get<any>('/api/units/?is_active=true'))[0];
    if (unit) {
      expect((await user.put(`/api/units/${unit.id}/column-mappings/`, { mappings: [] })).status()).toBe(403);
    }
    await user.dispose();
  });
});
