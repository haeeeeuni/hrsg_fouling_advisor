/**
 * 대시보드 — specs/11, AC-16-6.
 * 이미 분석이 끝난 호기를 골라 읽기만 한다. 분석된 호기가 없으면 건너뛴다(scenario.spec.ts 가 만든다).
 */
import { expect, test } from '@playwright/test';

import { Api, rows } from './support/api';
import { selectUnit } from './support/ui';

test.describe('최근 분석 결과', () => {
  let analyzedUnitId: number | null = null;

  test.beforeAll(async () => {
    const api = await Api.asAdmin();
    analyzedUnitId = await api.latestAnalyzedUnitId();
    await api.dispose();
  });

  test.beforeEach(async ({ page }) => {
    test.skip(analyzedUnitId === null, '성공한 분석이 있는 호기가 없다');
    await page.goto('/dashboard');
    await selectUnit(page, analyzedUnitId!);
    // 결과가 그려졌는지는 첫 KPI 카드로 판단한다.
    await expect(page.locator('.ui-stat-label', { hasText: '현재 오염도 지수' })).toBeVisible();
  });

  test('AC-11-1: KPI 4종이 모두 값과 함께 표시된다', async ({ page }) => {
    for (const label of ['현재 오염도 지수', '오염도 등급', '임계 도달 D-day', '예상 회수 편익']) {
      const card = page.locator('.card', { has: page.locator('.ui-stat-label', { hasText: label }) });
      await expect(card).toBeVisible();
      await expect(card.locator('.ui-stat-value')).not.toBeEmpty();
    }
  });

  test('AC-16-6: 도움말(?)이 클릭으로 열리고 Esc 로 닫힌다', async ({ page }) => {
    const help = page.getByRole('button', { name: '현재 오염도 지수 설명 열기' });
    await help.click();

    const note = page.getByRole('note');
    await expect(note).toContainText('청정 기준 기간 대비');

    await page.keyboard.press('Escape');
    await expect(note).toHaveCount(0);
  });

  test('AC-16-6: 도움말은 바깥을 클릭해도 닫힌다', async ({ page }) => {
    await page.getByRole('button', { name: '오염도 등급 설명 열기' }).click();
    await expect(page.getByRole('note')).toBeVisible();

    await page.locator('.ui-page-title').click();
    await expect(page.getByRole('note')).toHaveCount(0);
  });

  test('오염도 지수 시계열 차트가 그려진다', async ({ page }) => {
    const card = page.locator('.card', { hasText: '오염도 지수 시계열' });
    await expect(card.locator('canvas')).toBeVisible();
  });

  test('신호 진단 패널이 표시된다(specs/07 §8)', async ({ page }) => {
    const panel = page.locator('.card', { has: page.getByRole('heading', { name: '신호 진단' }) });
    await expect(panel).toBeVisible();
    await expect(panel).not.toContainText('진단 결과가 없습니다.');
  });
});

test.describe('호기 상태별 표시', () => {
  // beforeEach(최근 분석 호기 선택)와 무관하게 호기를 직접 고른다.
  let byGrade: Record<string, number> = {};
  let unanalyzedUnitId: number | null = null;

  test.beforeAll(async () => {
    const api = await Api.asAdmin();
    const active = rows(await api.get<any>('/api/units/?is_active=true')) as { id: number }[];
    const runs = rows(await api.get<any>('/api/analysis-runs/?status=SUCCESS&page_size=200')) as any[];
    await api.dispose();
    // 실행 이력은 최신순이다. 호기별 첫 번째가 대시보드에 보이는 결과다.
    const latest = new Map<number, any>();
    for (const r of runs) if (!latest.has(r.unit)) latest.set(r.unit, r);
    for (const u of active) {
      const run = latest.get(u.id);
      if (!run) unanalyzedUnitId ??= u.id;
      else byGrade[run.result_grade] ??= u.id;
    }
  });

  test('AC-11-3: 경고 등급이면 등급 카드에 빨간 "경고" 배지가 뜬다', async ({ page }) => {
    test.skip(!byGrade.WARNING, '최근 분석이 경고 등급인 활성 호기가 없다');
    await page.goto('/dashboard');
    await selectUnit(page, byGrade.WARNING);

    const card = page.locator('.card', { has: page.locator('.ui-stat-label', { hasText: '오염도 등급' }) });
    const badge = card.locator('.badge');
    await expect(badge).toHaveText('경고');
    await expect(badge).toHaveClass(/text-bg-danger/);
  });

  test('AC-11-4: 분석하지 않은 호기는 빈 화면이 아니라 안내와 분석 실행 버튼을 보여준다', async ({ page }) => {
    test.skip(unanalyzedUnitId === null, '분석하지 않은 활성 호기가 없다');
    await page.goto('/dashboard');
    await selectUnit(page, unanalyzedUnitId!);

    await expect(page.getByText('아직 분석 결과가 없습니다.')).toBeVisible();
    await page.getByRole('main').getByRole('link', { name: '분석 실행' }).last().click();
    await expect(page).toHaveURL(/\/analysis\/new$/);
  });
});
