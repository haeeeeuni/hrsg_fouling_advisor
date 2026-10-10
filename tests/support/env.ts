/**
 * E2E 실행 환경 (specs/14 §4.3).
 *
 * 값은 전부 환경 변수로 바꿀 수 있다. 기본값은 로컬 개발 스택(Vite 5173 + Django 8000)과
 * seed_defaults 가 만드는 기본 관리자 계정이다(specs/01 AUTH-9).
 */
import path from 'node:path';

const ROOT = path.resolve(__dirname, '..', '..');

export const BASE_URL = process.env.E2E_BASE_URL ?? 'http://localhost:5173';

/** localhost 가 아니면 원격(배포본)으로 보고, 데이터를 바꾸는 테스트를 건너뛴다. */
export const IS_REMOTE = !/^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?/.test(BASE_URL);

export const ADMIN = {
  username: process.env.E2E_ADMIN_USERNAME ?? 'admin',
  password: process.env.E2E_ADMIN_PASSWORD ?? 'admin1234!',
};

export const PATHS = {
  root: ROOT,
  adminState: path.join(ROOT, 'playwright', '.auth', 'admin.json'),
};

/** 데이터를 바꾸는 테스트에 붙이는 태그. 원격 대상에서는 config 가 grepInvert 로 제외한다. */
export const MUTATES = '@mutates';

/** 뷰포트 (specs/12 §5). 데스크톱은 기본, 모바일은 레이아웃 검사에 쓴다. */
export const VIEWPORTS = {
  desktop: { width: 1280, height: 800 },
  mobile: { width: 390, height: 844 },
};
