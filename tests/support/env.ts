/**
 * E2E 실행 환경 (specs/21 §3).
 *
 * 값은 전부 환경 변수로 바꿀 수 있다. 기본값은 로컬 개발 스택(Vite 5173 + Django 8000)과
 * seed_defaults 가 만드는 초기 관리자 계정이다(specs/01 §4).
 */
import path from 'node:path';

const ROOT = path.resolve(__dirname, '..', '..');

export const BASE_URL = process.env.E2E_BASE_URL ?? 'http://localhost:5173';

/** localhost 가 아니면 원격(배포본)으로 보고, 데이터를 바꾸는 테스트를 건너뛴다. */
export const IS_REMOTE = !/^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?/.test(BASE_URL);

export const ADMIN = {
  fullName: process.env.E2E_ADMIN_NAME ?? '관리자',
  employeeNo: process.env.E2E_ADMIN_NO ?? 'ADM01',
  password: process.env.E2E_ADMIN_PASSWORD ?? 'qwer',
};

/** 업로드 시나리오용 샘플 CSV 를 만들 Python. 백엔드 가상환경을 기본으로 쓴다. */
export const PYTHON = process.env.E2E_PYTHON ?? path.join(ROOT, 'backend', '.venv', 'bin', 'python');

export const PATHS = {
  root: ROOT,
  backend: path.join(ROOT, 'backend'),
  adminState: path.join(ROOT, 'playwright', '.auth', 'admin.json'),
  data: path.join(ROOT, 'playwright', '.data'),
};

/** 데이터를 바꾸는 테스트에 붙이는 태그. 원격 대상에서는 config 가 grepInvert 로 제외한다. */
export const MUTATES = '@mutates';
