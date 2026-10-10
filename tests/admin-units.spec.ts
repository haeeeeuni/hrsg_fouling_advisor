/**
 * 관리자 — 호기 관리 · 자동 재계산 · 컬럼 매핑 (specs/02, specs/13 §3, specs/19 §2).
 *
 * 호기 생성·수정·삭제는 데이터가 없는 임시 호기(E2EUI)로 한다. 매핑과 자동 재계산은
 * 테스트 전용 E2E 호기에 같은 값을 다시 저장하므로 다른 호기에 영향이 없다.
 */
import { expect, test, type Page } from '@playwright/test';

import { Api, rows } from './support/api';
import { activateE2EUnit, deactivateE2EUnit, ensureE2EData } from './support/e2e-unit';
import { MUTATES } from './support/env';
import { ensureSampleCsv } from './support/sample-data';
import { selectUnit } from './support/ui';

const TEMP_CODE = 'E2EUI';

test.describe.configure({ mode: 'serial' });

test.describe(`호기 관리 ${MUTATES}`, () => {
  let admin: Api;
  let e2eUnitId: number;

  async function removeTempUnit() {
    for (const u of rows(await admin.get<any>('/api/units/')) as any[]) {
      if (u.code === TEMP_CODE) await admin.delete(`/api/units/${u.id}/`);
    }
  }

  test.beforeAll(async () => {
    test.setTimeout(180_000);
    admin = await Api.asAdmin();
    await removeTempUnit();
    e2eUnitId = await activateE2EUnit(admin);
    await ensureE2EData(admin, e2eUnitId);
  });

  test.afterAll(async () => {
    await removeTempUnit();
    await deactivateE2EUnit(admin, e2eUnitId);
    await admin.dispose();
  });

  // 자동 재계산 카드에도 "저장" 버튼이 있어 호기 폼 카드로 범위를 좁힌다.
  const unitForm = (page: Page) => page.locator('.card', { has: page.getByLabel('호기 코드') });

  const unitRow = (page: Page, code: string) =>
    page.getByRole('row').filter({ has: page.getByRole('cell', { name: code, exact: true }) });

  test('호기를 추가하면 목록에 "매핑 미완료" 로 나온다', async ({ page }) => {
    await page.goto('/admin/units');
    await page.getByRole('button', { name: '호기 추가' }).click();

    await page.getByLabel('호기 코드').fill(TEMP_CODE);
    await page.getByLabel('호기명').fill('E2E 화면 생성 호기');
    await unitForm(page).getByRole('button', { name: '저장' }).click();

    await expect(page.getByText('저장했습니다.')).toBeVisible();
    await expect(unitRow(page, TEMP_CODE)).toContainText('미완료');
  });

  test('수정하면 호기 코드는 잠겨 있고 이름이 바뀐다', async ({ page }) => {
    await page.goto('/admin/units');
    await unitRow(page, TEMP_CODE).getByRole('button', { name: '수정' }).click();

    await expect(page.getByLabel('호기 코드')).toBeDisabled();
    await page.getByLabel('호기명').fill('E2E 화면 수정 호기');
    await unitForm(page).getByRole('button', { name: '저장' }).click();

    await expect(unitRow(page, TEMP_CODE)).toContainText('E2E 화면 수정 호기');
  });

  test('데이터가 있는 호기는 삭제를 거부하고 비활성화를 안내한다', async ({ page }) => {
    await page.goto('/admin/units');
    page.once('dialog', (d) => d.accept());

    await unitRow(page, 'E2E').getByRole('button', { name: '삭제' }).click();

    await expect(page.getByText('데이터가 있는 호기는 삭제할 수 없습니다.')).toBeVisible();
    await expect(unitRow(page, 'E2E')).toHaveCount(1);
  });

  test('데이터가 없는 호기는 확인 후 삭제된다', async ({ page }) => {
    await page.goto('/admin/units');
    page.once('dialog', (d) => {
      expect(d.message()).toContain(TEMP_CODE);
      return d.accept();
    });

    await unitRow(page, TEMP_CODE).getByRole('button', { name: '삭제' }).click();

    await expect(page.getByText('삭제했습니다.')).toBeVisible();
    await expect(unitRow(page, TEMP_CODE)).toHaveCount(0);
  });

  test('자동 재계산 설정을 저장한다(기본 꺼짐 유지)', async ({ page }) => {
    await page.goto('/admin/units');
    await selectUnit(page, e2eUnitId);
    const card = page.locator('.card', { hasText: '자동 재계산' });

    // 기본은 꺼짐이다(CLAUDE.md — 모델 자동 재학습은 기본 꺼짐). 값을 바꾸지 않고 저장만 확인한다.
    await expect(card.getByLabel('기대값 모델도 자동으로 재학습')).not.toBeChecked();
    await card.getByRole('button', { name: '저장' }).click();

    await expect(page.getByText('자동 재계산 설정을 저장했습니다.')).toBeVisible();
  });

  test('컬럼 매핑: 샘플 CSV 를 올리면 미리보기와 원본 컬럼 선택지가 나오고, 저장하면 버전이 오른다', async ({ page }) => {
    // 이력 API 는 최근 일부만 준다. 개수가 아니라 최신 버전 번호로 비교한다.
    const before = Math.max(0, ...(await admin.get<any[]>(`/api/units/${e2eUnitId}/column-mappings/versions/`)).map((v) => v.version));
    const stackLabel = (await admin.get<any[]>('/api/standard-fields/')).find((f) => f.key === 'stack_temp_c').label;

    await page.goto('/admin/column-mapping');
    await page.getByLabel('호기', { exact: true }).selectOption(String(e2eUnitId));
    await expect(page.getByRole('status')).toContainText('필수 충족 규칙 통과');

    const chooser = page.waitForEvent('filechooser');
    await page.getByRole('button', { name: '파일 선택' }).click();
    await (await chooser).setFiles(ensureSampleCsv());

    await expect(page.getByText(/변환 미리보기/)).toBeVisible();
    const stackSource = page.getByLabel(`${stackLabel} 원본 컬럼`);
    await expect(stackSource).toHaveValue('stack_temp_c'); // 파일 헤더가 선택지가 된다

    // 필수 항목을 비우면 저장 전에도 배지가 바로 바뀐다(specs/02 §5.3).
    await stackSource.selectOption({ label: '(매핑 안 함)' });
    await expect(page.getByRole('status')).toContainText('필수 충족 규칙 미통과');
    await stackSource.selectOption('stack_temp_c');
    await expect(page.getByRole('status')).toContainText('필수 충족 규칙 통과');

    await page.getByRole('button', { name: '매핑 저장' }).click();

    await expect(page.getByText(`매핑을 저장했습니다. (버전 ${before + 1})`)).toBeVisible();
    await expect(page.getByRole('row').filter({ hasText: `v${before + 1}` }).or(
      page.getByRole('row').filter({ has: page.getByRole('cell', { name: String(before + 1), exact: true }) }),
    ).first()).toBeVisible();
  });
});
