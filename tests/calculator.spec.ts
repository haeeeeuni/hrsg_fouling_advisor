/**
 * 계산기 (specs/05, 검수 시나리오 1·3). 관리자 세션으로 연다(계산기는 승인된 사용자 누구나).
 * 계산 결과의 정확도는 백엔드 단위 테스트(cases.json)가 맡고, 여기서는 화면 연결을 본다.
 */
import { expect, test } from '@playwright/test';

import { Api } from './support/api';

async function gtModelId(name: string): Promise<number> {
  const api = await Api.asAdmin();
  try {
    const { gt_models } = await api.get('/api/calculator/options/');
    return gt_models.find((m: any) => m.name === name).id;
  } finally {
    await api.dispose();
  }
}

test('배압을 바꾸면 정상 → 경보 → 트립으로 상태가 바로 바뀐다 (검수 3)', async ({ page }) => {
  const id = await gtModelId('가상 모델 A (F급)'); // 경보 4.5, 트립 5.5 kPa [임시값]
  await page.goto(`/calculator?gt=${id}`);
  const status = page.getByTestId('overall-status');
  await expect(status).toHaveText(/정상/);

  const backpressure = page.getByLabel('현재 배압');
  await backpressure.fill('4.6');
  await expect(status).toHaveText(/주의 — 경보 구간/);
  await expect(status).toHaveAttribute('data-level', 'CAUTION');

  await backpressure.fill('5.6');
  await expect(status).toHaveText(/위험 — 트립 구간/);
  await expect(status).toHaveAttribute('data-level', 'DANGER');

  await backpressure.fill('3.0');
  await expect(status).toHaveText(/정상/);
});

test('같은 입력은 항상 같은 결과다 (검수 1)', async ({ page }) => {
  const id = await gtModelId('가상 모델 A (F급)');
  const url = `/calculator?gt=${id}&bp=4.2&stk=101`;

  await page.goto(url);
  const first = await page.getByTestId('daily-loss').textContent();
  await page.reload();
  await expect(page.getByTestId('daily-loss')).toHaveText(first!);
});

test('입력값이 URL 에 남아 새로고침해도 복원된다', async ({ page }) => {
  const id = await gtModelId('가상 모델 B (H급)');
  await page.goto(`/calculator?gt=${id}`);

  await page.getByLabel('현재 굴뚝 온도').fill('104');
  await expect(page).toHaveURL(/stk=104/);
  await page.reload();

  await expect(page.getByLabel('현재 굴뚝 온도')).toHaveValue('104');
  await expect(page.getByLabel('GT 모델')).toHaveValue(String(id));
});

test('결과에 임시 참조값 안내와 SMP 기준일·출처가 붙는다', async ({ page }) => {
  await page.goto('/calculator');

  await expect(page.getByText('임시 참조값을 사용한 결과입니다.')).toBeVisible();
  await expect(page.getByTestId('smp-source')).toContainText('기준일');
  await expect(page.getByTestId('smp-source')).toContainText('추정');

  await page.getByLabel('SMP 직접 입력').check();
  await page.getByLabel('SMP', { exact: true }).fill('200');
  await expect(page.getByTestId('smp-source')).toContainText('사용자 입력');
});

test('손실이 없으면 회수 기간은 0 이 아니라 "회수 불가" 다', async ({ page }) => {
  const id = await gtModelId('가상 모델 A (F급)');
  await page.goto(`/calculator?gt=${id}`); // 설계값 그대로 = 손실 0

  await expect(page.getByTestId('payback')).toHaveText('회수 불가');
});

test('잘못된 입력은 해당 칸에 바로 표시된다', async ({ page }) => {
  await page.goto('/calculator');

  await page.getByLabel('현재 배압').fill('');
  await expect(page.getByText('값을 입력해 주세요.')).toBeVisible();

  await page.getByLabel('현재 배압').fill('80'); // 물리 범위 밖 — 서버가 칸 오류로 알린다
  await expect(page.locator('#cBp')).toHaveClass(/is-invalid/);
});

test('공법별 비교는 순편익 최대 공법을 표시한다', async ({ page }) => {
  const id = await gtModelId('가상 모델 A (F급)');
  await page.goto(`/calculator/methods?gt=${id}&bp=4&stk=100`);

  await expect(page.getByTestId('best-method')).toHaveText('드라이아이스 세정');
  await expect(page.getByRole('row', { name: /순편익 최대/ })).toContainText('드라이아이스 세정');
  await expect(page.getByRole('table')).not.toContainText('권장');
});

test('핀치·어프로치: 어프로치가 음수면 위험(스티밍 우려)', async ({ page }) => {
  await page.goto('/calculator/pinch');
  await expect(page.getByText('압력단 값을 입력하세요')).toBeVisible();

  await page.getByLabel('드럼 압력').fill('120');
  await page.getByLabel('증발기 출구 가스 온도').fill('338');
  await page.getByLabel('절탄기 출구 급수 온도').fill('327');

  await expect(page.getByTestId('pinch-overall')).toHaveText(/위험/);
  await expect(page.getByText('스티밍 우려')).toBeVisible();
});
