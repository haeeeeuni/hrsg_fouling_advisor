/**
 * 테스트 준비·정리용 API 헬퍼.
 *
 * 화면으로 검증할 대상이 아닌 준비 작업(가입 신청, 승인)은 API 로 빠르게 처리한다.
 * 인증은 세션 쿠키 + CSRF 다(specs/10 §1). 변경 요청에는 csrftoken 쿠키 값을
 * X-CSRFToken 헤더로 실어야 한다.
 */
import { expect, request, type APIRequestContext } from '@playwright/test';

import { ADMIN, BASE_URL, PATHS } from './env';

export type Credentials = { username: string; password: string };

export type TestUser = Credentials & { id: number; fullName: string; organization: string };

/** 실행마다 겹치지 않는 ID. 규칙: 영문 소문자·숫자·._- 4~30자(specs/01 §2). */
export function uniqueUsername(prefix = 'e2e'): string {
  return `${prefix}.${Date.now().toString(36)}${Math.floor(Math.random() * 1e4)}`.slice(0, 30);
}

export class Api {
  private constructor(private readonly ctx: APIRequestContext) {}

  /**
   * auth.setup.ts 가 저장한 관리자 세션을 재사용한다.
   * 새로 로그인하지 않으므로 로그인 스로틀(분당 10회)을 쓰지 않는다.
   */
  static async asAdmin(): Promise<Api> {
    return new Api(await request.newContext({ baseURL: BASE_URL, storageState: PATHS.adminState }));
  }

  /** 로그인하지 않은 컨텍스트. 가입 신청처럼 공개 API 를 부를 때 쓴다. */
  static async anonymous(): Promise<Api> {
    // 반드시 빈 쿠키로 시작한다. 테스트 안에서 만든 컨텍스트는 그 테스트의 storageState(관리자 세션)를
    // 물려받는데, 그 상태로 다른 사용자가 로그인하면 Django 가 기존 세션을 폐기한다
    // → 모든 테스트가 같이 쓰는 관리자 세션이 끊겨 이후 테스트가 전부 401 이 된다.
    const ctx = await request.newContext({ baseURL: BASE_URL, storageState: { cookies: [], origins: [] } });
    await ctx.get('/api/auth/csrf/');
    return new Api(ctx);
  }

  /** 새로 로그인한 API 컨텍스트. 로그인 스로틀을 쓰므로 꼭 필요할 때만. */
  static async login(creds: Credentials = ADMIN): Promise<Api> {
    const api = await Api.anonymous();
    const res = await api.post('/api/auth/login/', creds);
    expect(res.status(), `로그인 실패: ${await res.text()}`).toBe(200);
    return api;
  }

  /** 가입 신청만 한다(승인 대기). */
  static async signup(overrides: Partial<TestUser> = {}): Promise<TestUser> {
    const user = {
      username: overrides.username ?? uniqueUsername(),
      password: overrides.password ?? 'e2e-pass-123',
      fullName: overrides.fullName ?? 'E2E 사용자',
      organization: overrides.organization ?? 'E2E 테스트',
    };
    const anon = await Api.anonymous();
    try {
      const res = await anon.post('/api/auth/signup/', {
        username: user.username,
        password: user.password,
        password_confirm: user.password,
        full_name: user.fullName,
        organization: user.organization,
        signup_reason: 'E2E 자동 테스트',
      });
      expect(res.status(), `가입 실패: ${await res.text()}`).toBe(201);
    } finally {
      await anon.dispose();
    }
    const admin = await Api.asAdmin();
    try {
      const found = rows(await admin.get<any>(`/api/admin/users/?search=${user.username}`));
      return { ...user, id: found.find((u: any) => u.username === user.username).id };
    } finally {
      await admin.dispose();
    }
  }

  /** 가입 신청 + 관리자 승인까지 마친 일반 사용자. */
  static async approvedUser(overrides: Partial<TestUser> = {}): Promise<TestUser> {
    const user = await Api.signup(overrides);
    const admin = await Api.asAdmin();
    try {
      const res = await admin.post(`/api/admin/users/${user.id}/approve/`);
      expect(res.status(), await res.text()).toBe(200);
    } finally {
      await admin.dispose();
    }
    return user;
  }

  private async csrfHeaders(): Promise<Record<string, string>> {
    const { cookies } = await this.ctx.storageState();
    const token = cookies.find((c) => c.name === 'csrftoken')?.value ?? '';
    // Django 는 HTTPS 에서 Referer 도 검사한다(배포본 대비).
    return { 'X-CSRFToken': token, Referer: `${BASE_URL}/` };
  }

  async get<T = any>(url: string): Promise<T> {
    const res = await this.ctx.get(url);
    expect(res.ok(), `GET ${url} → ${res.status()} ${await res.text()}`).toBeTruthy();
    return res.json();
  }

  async post(url: string, data?: unknown) {
    return this.ctx.post(url, { data, headers: await this.csrfHeaders() });
  }

  async patch(url: string, data: unknown) {
    return this.ctx.patch(url, { data, headers: await this.csrfHeaders() });
  }

  async delete(url: string) {
    return this.ctx.delete(url, { headers: await this.csrfHeaders() });
  }

  /** 202 + job_id 작업이 끝날 때까지 기다린다(specs/10 §1). 준비 단계에서만 쓴다. */
  async waitForJob(jobId: string, timeoutMs = 120_000): Promise<any> {
    let job: any;
    await expect
      .poll(
        async () => {
          job = await this.get(`/api/jobs/${jobId}/`);
          return job.status;
        },
        { timeout: timeoutMs, intervals: [500, 1000] },
      )
      .toMatch(/SUCCESS|FAILED|CANCELED/);
    expect(job.status, JSON.stringify(job.error ?? job)).toBe('SUCCESS');
    return job;
  }

  async dispose() {
    await this.ctx.dispose();
  }
}

/** 페이지네이션 응답과 배열 응답을 같이 다룬다. */
export function rows<T>(body: T[] | { results: T[] }): T[] {
  return Array.isArray(body) ? body : body.results;
}
