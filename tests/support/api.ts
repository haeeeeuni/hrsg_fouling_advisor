/**
 * 테스트 준비·정리용 API 헬퍼.
 *
 * 화면으로 검증할 대상이 아닌 준비 작업(호기 등록, 매핑, 사용자 생성)은 API 로 빠르게 처리한다.
 * 인증은 세션 쿠키 + CSRF 다(specs/15 §1). 변경 요청에는 csrftoken 쿠키 값을
 * X-CSRFToken 헤더로 실어야 한다.
 */
import { expect, request, type APIRequestContext } from '@playwright/test';

import { ADMIN, BASE_URL, PATHS } from './env';

export type Credentials = { fullName: string; employeeNo: string; password: string };

export class Api {
  private constructor(private readonly ctx: APIRequestContext) {}

  /**
   * auth.setup.ts 가 저장한 관리자 세션을 재사용한다.
   * 새로 로그인하지 않으므로 로그인 스로틀(분당 10회)을 쓰지 않는다.
   */
  static async asAdmin(): Promise<Api> {
    return new Api(await request.newContext({ baseURL: BASE_URL, storageState: PATHS.adminState }));
  }

  /** 새로 로그인한 API 컨텍스트를 만든다. 관리자가 아닌 계정을 쓸 때만 필요하다. */
  static async login(creds: Credentials = ADMIN): Promise<Api> {
    // 반드시 빈 쿠키로 시작한다. 테스트 안에서 만든 컨텍스트는 그 테스트의 storageState(관리자 세션)를
    // 물려받는데, 그 상태로 다른 사용자가 로그인하면 Django 가 기존 세션을 폐기한다
    // → 모든 테스트가 같이 쓰는 관리자 세션이 끊겨 이후 테스트가 전부 401 이 된다.
    const ctx = await request.newContext({ baseURL: BASE_URL, storageState: { cookies: [], origins: [] } });
    const api = new Api(ctx);
    await ctx.get('/api/auth/csrf/');
    const res = await api.post('/api/auth/login/', {
      full_name: creds.fullName,
      employee_no: creds.employeeNo,
      password: creds.password,
    });
    expect(res.status(), `로그인 실패: ${await res.text()}`).toBe(200);
    return api;
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

  async postMultipart(url: string, multipart: Record<string, string | { name: string; mimeType: string; buffer: Buffer }>) {
    return this.ctx.post(url, { multipart, headers: await this.csrfHeaders() });
  }

  /** 202 + job_id 작업이 끝날 때까지 기다린다(specs/15 §1). 화면 검증이 아닌 준비 단계에서만 쓴다. */
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

  async put(url: string, data: unknown) {
    return this.ctx.put(url, { data, headers: await this.csrfHeaders() });
  }

  async patch(url: string, data: unknown) {
    return this.ctx.patch(url, { data, headers: await this.csrfHeaders() });
  }

  async delete(url: string) {
    return this.ctx.delete(url, { headers: await this.csrfHeaders() });
  }

  async dispose() {
    await this.ctx.dispose();
  }

  /**
   * 가장 최근 성공 분석이 있는 **활성** 호기 id. 없으면 null.
   * 비활성 호기(예: 테스트가 끝나며 끈 E2E 호기)는 내비바에서 고를 수 없으므로 뺀다.
   * 전체 이력의 첫 페이지로 고르면 안 된다 — 테스트가 E2E 호기로 분석을 쌓으면 첫 페이지가
   * 전부 비활성 호기 것이 되어 "분석된 호기 없음" 으로 잘못 판단한다. 호기별로 묻는다.
   */
  async latestAnalyzedUnitId(): Promise<number | null> {
    const latest = [...(await this.latestRunByActiveUnit()).entries()].filter(([, run]) => run);
    latest.sort(([, a], [, b]) => (a.executed_at < b.executed_at ? 1 : -1));
    return latest[0]?.[0] ?? null;
  }

  /** 활성 호기별 가장 최근 성공 분석(대시보드에 보이는 결과). 분석이 없는 호기는 null. */
  async latestRunByActiveUnit(): Promise<Map<number, any | null>> {
    const out = new Map<number, any | null>();
    for (const unit of rows(await this.get<any>('/api/units/?is_active=true')) as any[]) {
      const [run] = rows(await this.get<any>(`/api/analysis-runs/?unit_id=${unit.id}&status=SUCCESS&page_size=1`)) as any[];
      out.set(unit.id, run ?? null);
    }
    return out;
  }
}

/** 페이지네이션 응답과 배열 응답을 같이 다룬다. */
export function rows<T>(body: T[] | { results: T[] }): T[] {
  return Array.isArray(body) ? body : body.results;
}
