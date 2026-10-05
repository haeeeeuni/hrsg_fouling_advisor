/**
 * 화면 순회 스모크 — 모든 라우트가 에러 없이 열리는지 (specs/16 §3, specs/13 §3).
 * 읽기만 하므로 배포본에도 돌릴 수 있다.
 */
import { expect, test } from '@playwright/test';

import { Api, rows } from './support/api';
import { pageTitle, selectUnit } from './support/ui';

const USER_PAGES: [string, string][] = [
  ['/dashboard', '대시보드'],
  ['/upload', '데이터 업로드'],
  ['/analysis/new', '분석 실행'],
  ['/comparison', '세정 전후 비교'],
  ['/maintenance', '정비 이력'],
  ['/reports', '리포트'],
  ['/profile', '내 정보'],
];

const ADMIN_PAGES: [string, string][] = [
  ['/admin/users', '사용자 관리'],
  ['/admin/units', '호기 관리'],
  ['/admin/column-mapping', '컬럼 매핑'],
  ['/admin/settings', '분석 설정'],
  ['/admin/benefit-settings', '편익 기본값'],
  ['/admin/cleaning-events', '세정 이력'],
  ['/admin/keywords', '오염 키워드'],
  ['/admin/models', '모델 관리'],
  ['/admin/run-history', '분석 실행 이력'],
  ['/admin/audit-logs', '감사 로그'],
  ['/admin/unit-comparison', '호기 간 비교'],
  ['/admin/backtest', '예측 정확도 검증'],
];

for (const [path, title] of [...USER_PAGES, ...ADMIN_PAGES]) {
  test(`${path} 화면이 에러 없이 열린다`, async ({ page }) => {
    const errors: string[] = [];
    page.on('pageerror', (err) => errors.push(err.message));
    page.on('response', (res) => {
      if (res.url().includes('/api/') && res.status() >= 500) errors.push(`${res.status()} ${res.url()}`);
    });

    await page.goto(path);

    await expect(pageTitle(page)).toHaveText(title);
    await expect(page.getByText('서버에 연결할 수 없습니다.')).toHaveCount(0);
    expect(errors, '페이지 스크립트 오류 또는 API 5xx').toEqual([]);
  });
}

test('관리자 콘솔 하위 화면에서도 사이드바의 관리자 콘솔 항목이 활성으로 남는다', async ({ page }) => {
  await page.goto('/admin/settings');

  const sidebar = page.locator('.ui-sidebar');
  await expect(sidebar.getByRole('link', { name: '관리자 콘솔' })).toHaveClass(/active/);
  await expect(sidebar.getByRole('link', { name: '분석 설정' })).toHaveClass(/active/);
});

test('AC-16-3: 호기 선택이 페이지 이동과 새로고침 후에도 유지된다', async ({ page }) => {
  const api = await Api.asAdmin();
  const list = rows(await api.get<any>('/api/units/?is_active=true')) as { id: number }[];
  await api.dispose();
  test.skip(list.length < 2, '활성 호기가 2개 이상 있어야 선택 유지를 확인할 수 있다');

  await page.goto('/dashboard');
  // 첫 번째가 아닌 호기를 골라야 "기본값으로 돌아가지 않음" 을 확인할 수 있다.
  const target = list[list.length - 1].id;
  await selectUnit(page, target);

  await page.getByRole('link', { name: '정비 이력' }).click();
  await expect(page.getByLabel('호기 선택')).toHaveValue(String(target));

  await page.reload();
  await expect(page.getByLabel('호기 선택')).toHaveValue(String(target));
});
