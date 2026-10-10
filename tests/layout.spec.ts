/**
 * 라이트/다크 × PC/모바일 (검수 시나리오 8, specs/12 AC-12-1·3).
 * 모든 화면에서 가로 스크롤이 없고, 테마가 문서에 적용되고, 새로고침 후에도 유지된다.
 */
import { expect, test } from '@playwright/test';

import { BASE_URL, VIEWPORTS } from './support/env';
import { expectNoHorizontalScroll, useTheme } from './support/ui';

const PUBLIC_PAGES = ['/', '/signup'];
const USER_PAGES = ['/home', '/profile', '/chat', '/calculator', '/checklist'];
const ADMIN_PAGES = ['/admin', '/admin/signups', '/admin/users', '/admin/settings', '/admin/audit-logs'];

for (const [device, viewport] of Object.entries(VIEWPORTS)) {
  for (const theme of ['light', 'dark'] as const) {
    test.describe(`${device} · ${theme}`, () => {
      test.use({ viewport });

      test.beforeEach(async ({ page }) => {
        await useTheme(page, theme);
      });

      test('관리자 화면과 사용자 화면에 가로 스크롤이 없다', async ({ page }) => {
        for (const path of [...USER_PAGES, ...ADMIN_PAGES]) {
          await page.goto(path);
          await expect(page.getByRole('main')).toBeVisible();
          // 목록이 그려진 뒤 잰다 — 로딩 중 상태는 폭이 좁다.
          await expect(page.getByRole('status')).toHaveCount(0);
          await expect(page.locator('html')).toHaveAttribute('data-bs-theme', theme);
          await expectNoHorizontalScroll(page);
        }
      });

      test.describe('비로그인', () => {
        test.use({ storageState: { cookies: [], origins: [] } });

        test('공개 화면에 가로 스크롤이 없다', async ({ page }) => {
          for (const path of PUBLIC_PAGES) {
            await page.goto(path);
            await expect(page.locator('html')).toHaveAttribute('data-bs-theme', theme);
            await expectNoHorizontalScroll(page);
          }
        });
      });
    });
  }
}

test.describe('테마 전환', () => {
  test.use({ storageState: { cookies: [], origins: [] } });

  // 저장값을 미리 넣지 않는다(useTheme 은 매 로드마다 다시 써서 새로고침 검증을 가린다).
  test.use({ colorScheme: 'light' });

  test('헤더 버튼으로 바꾼 테마가 새로고침 후에도 유지된다', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('html')).toHaveAttribute('data-bs-theme', 'light');

    await page.getByRole('button', { name: '다크 모드로 전환' }).click();
    await expect(page.locator('html')).toHaveAttribute('data-bs-theme', 'dark');

    await page.reload();
    await expect(page.locator('html')).toHaveAttribute('data-bs-theme', 'dark');
    await expect(page.getByRole('button', { name: '라이트 모드로 전환' })).toBeVisible();
  });

  test('저장된 선택이 없으면 OS 다크 설정을 따른다', async ({ browser }) => {
    const context = await browser.newContext({
      baseURL: BASE_URL,
      colorScheme: 'dark',
      storageState: { cookies: [], origins: [] },
    });
    const page = await context.newPage();
    await page.goto('/');

    await expect(page.locator('html')).toHaveAttribute('data-bs-theme', 'dark');
    await context.close();
  });
});
