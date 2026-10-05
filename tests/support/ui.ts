/** 여러 테스트가 같이 쓰는 화면 조작. 셀렉터는 역할·레이블 우선이다(specs/21 §5.1). */
import { expect, type Page } from '@playwright/test';

import type { Credentials } from './api';

export async function loginViaForm(page: Page, creds: Credentials) {
  await page.getByLabel('성명').fill(creds.fullName);
  await page.getByLabel('사번').fill(creds.employeeNo);
  await page.getByLabel('비밀번호').fill(creds.password);
  await page.getByRole('button', { name: '로그인' }).click();
}

/** 상단 내비바의 호기 선택. 선택값은 localStorage 에 남는다(AC-16-3). */
export async function selectUnit(page: Page, unitId: number) {
  const select = page.getByLabel('호기 선택');
  await select.selectOption(String(unitId));
  await expect(select).toHaveValue(String(unitId));
}

/** 페이지 제목(내비바 h1). 라우트 meta.title 과 같다. */
export function pageTitle(page: Page) {
  return page.locator('.ui-page-title');
}

/** 업로드 화면에서 호기를 고르고 파일을 선택한 뒤 검증을 누른다. */
export async function chooseAndValidate(page: Page, unitId: number, filePath: string) {
  await page.goto('/upload');
  await page.getByLabel('호기', { exact: true }).selectOption(String(unitId));
  const chooser = page.waitForEvent('filechooser');
  await page.getByRole('button', { name: '파일 선택' }).click();
  await (await chooser).setFiles(filePath);
  await page.getByRole('button', { name: '검증', exact: true }).click();
}

/**
 * 서버가 주는 UTC 시각을 화면 기준인 KST 날짜(YYYY-MM-DD)로 바꾼다(specs/18 §5).
 * ISO 문자열의 앞 10자를 자르면 KST 00~09시가 전날이 된다 — 화면이 같은 실수를 했던 적이 있다(specs/21 §9).
 */
export function kstDate(iso: string): string {
  return new Date(new Date(iso).getTime() + 9 * 3600_000).toISOString().slice(0, 10);
}
