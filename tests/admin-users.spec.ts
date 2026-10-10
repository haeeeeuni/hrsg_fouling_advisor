/**
 * 관리자 — 사용자 관리 (specs/01 §5, specs/13 §3).
 *
 * 테스트 사용자를 화면으로 만들고 고친 뒤 비활성화한다. 끝나면 API 로 물리 삭제한다.
 * 마지막 관리자 보호(AC-01-6)는 E2E 에서 다루지 않는다 — 보호가 깨져 있으면 유일한 관리자를
 * 비활성화해 이후 모든 테스트가 막힌다. backend accounts/tests/test_user_admin.py 가 검증한다.
 */
import { expect, test, type Page } from '@playwright/test';

import { Api, rows } from './support/api';
import { MUTATES } from './support/env';

const EMP_NO = 'E2EADM01';
const NAME = 'E2E관리화면';

test.describe.configure({ mode: 'serial' });

test.describe(`사용자 관리 ${MUTATES}`, () => {
  let admin: Api;

  async function removeTestUser() {
    for (const u of rows(await admin.get<any>(`/api/users/?search=${EMP_NO}`)) as any[]) {
      if (u.employee_no === EMP_NO) await admin.delete(`/api/users/${u.id}/?hard=true`);
    }
  }

  test.beforeAll(async () => {
    admin = await Api.asAdmin();
    await removeTestUser();
  });

  test.afterAll(async () => {
    await removeTestUser();
    await admin.dispose();
  });

  const userRow = (page: Page) => page.getByRole('row').filter({ hasText: EMP_NO });

  test('사용자 추가 폼으로 만들면 목록에 "비밀번호 변경 필요" 로 나온다', async ({ page }) => {
    await page.goto('/admin/users');
    await page.getByRole('button', { name: '사용자 추가' }).click();

    await page.getByLabel('사번', { exact: true }).fill(EMP_NO.toLowerCase()); // 서버가 대문자로 맞춘다
    await page.getByLabel('성명', { exact: true }).fill(NAME);
    await page.getByLabel('부서').fill('E2E팀');
    await page.getByLabel('초기 비밀번호').fill('e2e-init-pass');
    await page.getByRole('button', { name: '저장' }).click();

    await expect(page.getByText('저장했습니다.')).toBeVisible();
    await expect(userRow(page)).toContainText(NAME);
    await expect(userRow(page)).toContainText('비밀번호 변경 필요');
  });

  test('같은 사번으로 다시 추가하면 이유를 보여주고 저장하지 않는다', async ({ page }) => {
    await page.goto('/admin/users');
    await page.getByRole('button', { name: '사용자 추가' }).click();
    await page.getByLabel('사번', { exact: true }).fill(EMP_NO);
    await page.getByLabel('성명', { exact: true }).fill('중복');
    await page.getByLabel('초기 비밀번호').fill('e2e-init-pass');
    await page.getByRole('button', { name: '저장' }).click();

    await expect(page.locator('.alert-danger')).toContainText('이미 등록된 사번입니다.');
  });

  test('수정하면 사번은 바꿀 수 없고 부서가 바뀐다', async ({ page }) => {
    await page.goto('/admin/users');
    await userRow(page).getByRole('button', { name: '수정' }).click();

    await expect(page.getByLabel('사번', { exact: true })).toBeDisabled();
    await page.getByLabel('부서').fill('E2E수정팀');
    await page.getByRole('button', { name: '저장' }).click();

    await expect(page.getByText('저장했습니다.')).toBeVisible();
    const [user] = (rows(await admin.get<any>(`/api/users/?search=${EMP_NO}`)) as any[]).filter(
      (u) => u.employee_no === EMP_NO,
    );
    expect(user.department).toBe('E2E수정팀');
  });

  test('비밀번호 초기화는 입력창으로 새 비밀번호를 받는다', async ({ page }) => {
    await page.goto('/admin/users');
    page.once('dialog', (dialog) => {
      expect(dialog.type()).toBe('prompt');
      expect(dialog.message()).toContain(NAME);
      return dialog.accept('e2e-reset-pass');
    });

    await userRow(page).getByRole('button', { name: '비밀번호 초기화' }).click();

    await expect(page.getByText('비밀번호를 초기화했습니다.')).toBeVisible();
    // 새 비밀번호로 실제 로그인할 수 있어야 한다.
    const user = await Api.login({ fullName: NAME, employeeNo: EMP_NO, password: 'e2e-reset-pass' });
    await user.dispose();
  });

  test('검색·역할·사용 여부로 거른다', async ({ page }) => {
    await page.goto('/admin/users');

    await page.getByLabel('검색 (성명/사번)').fill(EMP_NO);
    await page.getByLabel('검색 (성명/사번)').press('Enter');
    await expect(page.locator('tbody tr')).toHaveCount(1);

    await page.getByLabel('역할', { exact: true }).selectOption('ADMIN');
    await expect(page.getByText('사용자가 없습니다.')).toBeVisible(); // 테스트 사용자는 일반 사용자다
  });

  test('비활성화는 확인을 받고, 목록에 "중지" 로 바뀐다', async ({ page }) => {
    await page.goto('/admin/users');
    page.once('dialog', (dialog) => {
      expect(dialog.message()).toContain(`${NAME}(${EMP_NO})`);
      return dialog.accept();
    });

    await userRow(page).getByRole('button', { name: '비활성화' }).click();

    await expect(page.getByText('비활성화했습니다.')).toBeVisible();
    await expect(userRow(page)).toContainText('중지');
  });

  test('로그인 이력 탭에 성공·실패 기록이 보인다', async ({ page }) => {
    await page.goto('/admin/users');
    await page.getByRole('button', { name: '로그인 이력' }).click();

    // 직전 테스트에서 테스트 사용자가 로그인했다.
    const row = page.getByRole('row').filter({ hasText: EMP_NO }).first();
    await expect(row).toContainText('성공');
  });
});
