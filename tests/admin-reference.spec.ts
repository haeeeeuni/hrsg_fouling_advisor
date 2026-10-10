/**
 * 관리자 — 참조 데이터·계산 파라미터 (specs/06). 데이터를 바꾸는 테스트는 끝나며 원래대로 돌려놓는다
 * (같은 DB 를 쓰는 다른 테스트가 시드값을 전제로 한다).
 */
import { expect, test } from '@playwright/test';

import { Api } from './support/api';
import { MUTATES } from './support/env';

test('GT 한계표에서 경보가 트립보다 크면 저장되지 않는다', async ({ page }) => {
  await page.goto('/admin/gt-models');
  await expect(page.getByText('임시값').first()).toBeVisible();

  await page.getByRole('row', { name: /가상 모델 A/ }).getByRole('button', { name: '수정' }).click();
  await page.getByLabel('배압 경보').fill('9');
  await page.getByRole('button', { name: '저장' }).click();

  await expect(page.getByRole('main').getByRole('alert')).toContainText('트립 한계는 경보 한계보다 커야');
  await page.getByRole('button', { name: '취소' }).click();
});

test(`파라미터를 바꾸면 새 버전이 활성화되고 이전 버전으로 되돌릴 수 있다 ${MUTATES}`, async ({ page }) => {
  await page.goto('/admin/calc-parameters');
  const before = await page.getByTestId('active-version').textContent();

  await page.getByLabel(/이용률/).fill('0.9');
  await page.getByRole('button', { name: '미리보기' }).click();
  await expect(page.getByTestId('preview')).toContainText('변경안');

  page.once('dialog', (dialog) => dialog.accept());
  await page.getByRole('button', { name: /새 버전으로 저장/ }).click();
  await expect(page.getByTestId('active-version')).not.toHaveText(before!);

  // 계산기 결과에 새 버전이 찍힌다(재현성).
  const created = (await page.getByTestId('active-version').textContent())!.trim();
  await page.goto('/calculator');
  await expect(page.getByText(`계산 파라미터 ${created}`)).toBeVisible();

  // 원래 버전으로 되돌린다.
  await page.goto('/admin/calc-parameters');
  page.once('dialog', (dialog) => dialog.accept());
  await page.getByRole('listitem').filter({ hasText: before!.trim() }).getByRole('button', { name: '이 버전으로 되돌리기' }).click();
  await expect(page.getByTestId('active-version')).toHaveText(before!.trim());
});

test(`SMP 를 등록하면 계산기 기본값과 출처가 바뀐다 ${MUTATES}`, async ({ page }) => {
  const asOf = '2099-12-31'; // 시드·다른 실행보다 항상 최신
  await page.goto('/admin/smp');
  await page.getByLabel('SMP (원/kWh)').fill('171.5');
  await page.getByLabel('기준일').fill(asOf);
  await page.getByLabel('출처').fill('E2E 테스트 값');
  await page.getByRole('button', { name: '등록' }).click();
  await expect(page.getByRole('row', { name: /E2E 테스트 값/ }).first()).toContainText('계산기 기본값');

  await page.goto('/calculator');
  await expect(page.getByTestId('registered-smp')).toContainText('171.5');
  await expect(page.getByTestId('registered-smp')).toContainText('E2E 테스트 값');

  // 정리 — 등록한 SMP 를 지운다.
  const api = await Api.asAdmin();
  const { results } = await api.get('/api/admin/smp-prices/?page_size=100');
  for (const row of results.filter((r: any) => r.source === 'E2E 테스트 값')) {
    await api.delete(`/api/admin/smp-prices/${row.id}/`);
  }
  await api.dispose();
});

test(`체크리스트 항목 — 임시값 안내가 보이고 같은 분류 안에서 순서를 바꿀 수 있다 ${MUTATES}`, async ({ page }) => {
  await page.goto('/admin/checklist-items');
  await expect(page.getByText(/임시값 항목이 \d+개 있습니다/)).toBeVisible();

  const pinch = page.getByRole('region', { name: '핀치·어프로치' });
  const firstName = async () => (await pinch.locator('tbody tr').first().locator('.fw-semibold').textContent())!.trim();
  const before = await firstName();

  await pinch.getByRole('button', { name: `${before} 아래로` }).click();
  await expect.poll(firstName).not.toBe(before);

  // 원래 순서로 되돌린다.
  await pinch.getByRole('button', { name: `${before} 위로` }).click();
  await expect.poll(firstName).toBe(before);
});
