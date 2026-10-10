/**
 * 관리자 — 분석 실행 이력 · 감사 로그 · 호기 간 비교 (specs/13 §3, specs/19 §3).
 * 읽기 전용이라 배포본에서도 돈다. 분석 이력이 없으면 해당 테스트를 건너뛴다.
 */
import fs from 'node:fs';

import { expect, test } from '@playwright/test';

import { Api, rows } from './support/api';

let successRuns: any[] = [];
let analyzedActiveUnits = 0;

test.beforeAll(async () => {
  const api = await Api.asAdmin();
  successRuns = rows(await api.get<any>('/api/analysis-runs/?status=SUCCESS&page_size=1')) as any[];
  analyzedActiveUnits = [...(await api.latestRunByActiveUnit()).values()].filter(Boolean).length;
  await api.dispose();
});

test.describe('분석 실행 이력', () => {
  test('상태 필터로 거르고, 상세를 열면 모델 버전과 설정 스냅샷이 보인다', async ({ page }) => {
    test.skip(!successRuns.length, '성공한 분석이 없다');
    await page.goto('/admin/run-history');

    await page.getByLabel('상태').selectOption('SUCCESS');
    const firstRow = page.locator('tbody tr').first();
    await expect(firstRow).toContainText('SUCCESS');
    await expect(page.locator('tbody tr').filter({ hasText: 'FAILED' })).toHaveCount(0);

    await firstRow.getByRole('button', { name: '상세' }).click();
    const detail = page.locator('.card', { has: page.getByRole('heading', { name: /실행 #\d+ 상세/ }) });
    await expect(detail).toContainText('모델 버전');
    await expect(detail).toContainText('적용 설정값 스냅샷'); // 재현성(시스템 불변식 3)

    await detail.getByRole('button', { name: '닫기' }).click();
    await expect(detail).toHaveCount(0);
  });

  test('실행 방식 필터 "자동" 은 자동 실행만 남긴다', async ({ page }) => {
    await page.goto('/admin/run-history');
    await page.getByLabel('실행 방식').selectOption('true');

    const bodyRows = page.locator('tbody tr');
    const empty = page.getByText('분석 실행 이력이 없습니다.');
    await expect(bodyRows.first().or(empty)).toBeVisible();
    if (await empty.isVisible()) return;
    const count = await bodyRows.count();
    await expect(bodyRows.filter({ hasText: '자동' })).toHaveCount(count);
  });

  test('엑셀로 내보내면 xlsx 파일을 받는다', async ({ page }) => {
    await page.goto('/admin/run-history');
    const pending = page.waitForEvent('download');

    await page.getByRole('button', { name: '엑셀 내보내기' }).click();

    const download = await pending;
    expect(download.suggestedFilename()).toBe('분석실행이력.xlsx');
    expect(fs.readFileSync(await download.path()).subarray(0, 2).toString('latin1')).toBe('PK');
  });
});

test.describe('감사 로그', () => {
  test('대상·동작으로 거른다', async ({ page }) => {
    await page.goto('/admin/audit-logs');

    // 목록을 다 읽기 전에는 빈 상태 문구가 잠깐 보인다. 필터 요청의 응답을 기다린 뒤 판단한다.
    const loaded = page.waitForResponse((r) => r.url().includes('/api/audit-logs/') && r.url().includes('target_type=User'));
    await page.getByLabel('대상').selectOption('User');
    const body = await (await loaded).json();
    test.skip(!(body.results ?? body).length, '사용자 관련 감사 로그가 없다');
    const empty = page.getByText('감사 로그가 없습니다.');
    await expect(page.locator('tbody tr').first()).toBeVisible();

    // 대상 열에는 고른 대상만 나온다.
    const targets = await page.locator('tbody tr td code').allInnerTexts();
    expect(new Set(targets)).toEqual(new Set(['User']));

    const filtered = page.waitForResponse((r) => r.url().includes('action=ACTIVATE'));
    await page.getByLabel('동작').selectOption('ACTIVATE'); // 사용자에는 활성화 동작이 없다
    await filtered;
    await expect(empty).toBeVisible();
  });
});

test.describe('호기 간 비교', () => {
  test('상대 순위라는 안내와 함께 호기별 우선순위가 나온다', async ({ page }) => {
    test.skip(analyzedActiveUnits < 2, '분석이 있는 활성 호기가 2개 이상 필요하다');
    await page.goto('/admin/unit-comparison');

    await expect(page.getByText('점수는 비교 대상 호기들 사이의 상대 순위이며, 절대적인 오염 정도가 아닙니다.')).toBeVisible();
    await expect(page.locator('tbody tr').first()).toBeVisible();
    await expect(page.locator('canvas').first()).toBeVisible(); // 호기별 오염도 추이

    await page.getByRole('button', { name: '새로고침' }).click();
    await expect(page.locator('.alert-danger')).toHaveCount(0);
  });
});
