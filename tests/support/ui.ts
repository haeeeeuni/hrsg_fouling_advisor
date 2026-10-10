/** 여러 테스트가 같이 쓰는 화면 조작. 셀렉터는 역할·레이블 우선이다(specs/14 §4.3). */
import { expect, type Page } from '@playwright/test';

import type { Credentials } from './api';

/** 헤더 상단 우측 로그인 패널 (specs/01 AUTH-6). */
export function loginPanel(page: Page) {
  return page.getByRole('dialog', { name: '로그인' });
}

/** 헤더의 로그인 버튼을 눌러 패널을 열고 로그인한다. 패널이 이미 열려 있으면 바로 입력한다. */
export async function loginViaHeader(page: Page, creds: Credentials) {
  const panel = loginPanel(page);
  if (!(await panel.isVisible())) {
    await page.getByRole('banner').getByRole('button', { name: '로그인' }).click();
  }
  await panel.getByLabel('ID').fill(creds.username);
  await panel.getByLabel('비밀번호').fill(creds.password);
  await panel.getByRole('button', { name: '로그인' }).click();
}

/** 문서 전체에 가로 스크롤이 생겼는지 (specs/12 AC-12-3). 표처럼 스스로 스크롤하는 상자는 괜찮다. */
export async function expectNoHorizontalScroll(page: Page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow, '가로 스크롤이 생겼다').toBeLessThanOrEqual(0);
}

/** 테마를 지정한 채로 페이지를 연다. index.html 의 인라인 스크립트가 같은 키를 읽는다. */
export async function useTheme(page: Page, theme: 'light' | 'dark') {
  await page.addInitScript((value) => {
    try {
      window.localStorage.setItem('hrsg.theme', value);
    } catch {
      // 저장소를 못 쓰면 OS 설정을 따른다.
    }
  }, theme);
}

/**
 * 서버가 주는 UTC 시각을 화면 기준인 KST 날짜(YYYY-MM-DD)로 바꾼다.
 * ISO 문자열의 앞 10자를 자르면 KST 00~09시가 전날이 된다 — 이전 앱에서 같은 실수가 세 번 있었다.
 */
export function kstDate(iso: string): string {
  return new Date(new Date(iso).getTime() + 9 * 3600_000).toISOString().slice(0, 10);
}
