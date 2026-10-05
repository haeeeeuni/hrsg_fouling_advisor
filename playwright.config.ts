/**
 * Playwright E2E 설정 (specs/21).
 *
 * 대상 서버는 E2E_BASE_URL 로 고른다. 기본은 로컬 Vite(5173)이고, Vite 가 /api 를 Django(8000)로 넘긴다.
 * Django · Celery 는 직접 띄워 둬야 한다(specs/21 §3.2). Vite 만 webServer 로 자동 기동한다.
 */
import { defineConfig, devices } from '@playwright/test';

import { BASE_URL, IS_REMOTE, MUTATES, PATHS } from './tests/support/env';

// 기본은 설치된 Google Chrome. 없는 환경에서는 E2E_BROWSER=chromium 으로 Playwright 내장 Chromium 을 쓴다.
const channel = (process.env.E2E_BROWSER ?? 'chrome') === 'chrome' ? 'chrome' : undefined;

export default defineConfig({
  testDir: './tests',
  // 로그인 스로틀(IP 기준 분당 10회)과 호기당 분석 동시 1건 제약 때문에 병렬 실행을 하지 않는다.
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  timeout: 60_000,
  expect: { timeout: 10_000 },
  reporter: process.env.CI ? [['github'], ['html', { open: 'never' }]] : [['list'], ['html', { open: 'never' }]],
  // 배포본(원격)에서는 데이터를 바꾸는 테스트를 돌리지 않는다.
  grepInvert: IS_REMOTE ? new RegExp(MUTATES) : undefined,

  use: {
    baseURL: BASE_URL,
    locale: 'ko-KR',
    timezoneId: 'Asia/Seoul',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },

  projects: [
    {
      name: 'setup',
      testMatch: /auth\.setup\.ts/,
      use: { ...devices['Desktop Chrome'], channel },
    },
    {
      name: 'chrome',
      testIgnore: /auth\.setup\.ts/,
      dependencies: ['setup'],
      use: {
        ...devices['Desktop Chrome'],
        channel,
        // 최소 지원 해상도(specs/18 §6). 기기 프리셋(1280×720)을 덮어쓰므로 프로젝트에 둔다.
        viewport: { width: 1280, height: 800 },
        storageState: PATHS.adminState,
      },
    },
  ],

  webServer: IS_REMOTE
    ? undefined
    : {
        command: 'npm --prefix frontend run dev -- --port 5173 --strictPort',
        url: BASE_URL,
        reuseExistingServer: !process.env.CI,
        timeout: 60_000,
      },
});
