/**
 * 업로드 시나리오용 운전 데이터 CSV (specs/17).
 *
 * 1MB 가 넘는 CSV 를 저장소에 넣지 않고, 시드를 고정해 매번 같은 파일을 만든다.
 * 6개월 · 30분 간격 · 세정 2회면 기준 기간 학습과 추세 적합에 충분하고 생성은 1초 안에 끝난다.
 */
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

import { PATHS, PYTHON } from './env';

export const E2E_UNIT_CODE = 'E2E';

/** 영문 헤더 CSV 라 원본 컬럼명 = 표준 항목명이다. */
export const E2E_MAPPING = [
  'timestamp',
  'gt_power_mw',
  'ambient_temp_c',
  'gt_exhaust_temp_c',
  'exhaust_flow',
  'hrsg_gas_dp_kpa',
  'stack_temp_c',
  'duct_burner_on',
  'st_power_mw',
].map((field) => ({
  standard_field: field,
  source_column: field,
  // 덕트버너는 0/1 로 나온다. BOOL 규칙이 1/0 을 참/거짓으로 읽는다.
  ...(field === 'duct_burner_on' ? { bool_rule: 'BOOL' } : {}),
}));

export function ensureSampleCsv(): string {
  const out = path.join(PATHS.data, 'e2e_unit.csv');
  if (fs.existsSync(out) && fs.existsSync(maintenancePath())) return out;

  fs.mkdirSync(PATHS.data, { recursive: true });
  execFileSync(
    PYTHON,
    [
      'scripts/generate_sample_data.py',
      '--unit-code', E2E_UNIT_CODE,
      '--months', '6',
      '--interval-min', '30',
      '--cleanings', '2',
      '--seed', '7',
      '--out', out,
      // 같은 시드로 정비 이력도 만든다. 운전 데이터의 세정 시점과 맞물린다(수세·드라이아이스 2건).
      '--maintenance-out', maintenancePath(),
    ],
    { cwd: PATHS.backend, stdio: 'pipe' },
  );
  return out;
}

function maintenancePath(): string {
  return path.join(PATHS.data, 'e2e_maintenance.csv');
}

/** 정비 이력 CSV (specs/17 §4.3). 세정 후보 2건이 들어 있다. */
export function ensureMaintenanceCsv(): string {
  ensureSampleCsv();
  return maintenancePath();
}

/**
 * 원본 CSV 의 앞부분을 변형해 오류 사례 파일을 만든다(업로드 검증용).
 * 내용이 매번 같으므로 두 번째 실행부터는 "같은 파일" 확인 대화상자가 뜬다(specs/21 §4.5).
 */
export function writeCsvVariant(
  name: string,
  transform: (header: string[], rows: string[][]) => { header: string[]; rows: string[][] },
  rowLimit = 500,
): string {
  const [headerLine, ...lines] = fs.readFileSync(ensureSampleCsv(), 'utf-8').trim().split('\n');
  const { header, rows } = transform(
    headerLine.split(','),
    lines.slice(0, rowLimit).map((l) => l.split(',')),
  );
  const out = path.join(PATHS.data, name);
  fs.writeFileSync(out, [header, ...rows].map((r) => r.join(',')).join('\n') + '\n');
  return out;
}

/** 한 컬럼을 통째로 뺀다. */
export function dropColumn(column: string) {
  return (header: string[], rows: string[][]) => {
    const i = header.indexOf(column);
    return { header: header.filter((_, j) => j !== i), rows: rows.map((r) => r.filter((_, j) => j !== i)) };
  };
}

/** 지정한 행들의 한 칸을 바꾼다. */
export function replaceCells(column: string, rowIndexes: number[], value: string) {
  return (header: string[], rows: string[][]) => {
    const i = header.indexOf(column);
    for (const r of rowIndexes) rows[r][i] = value;
    return { header, rows };
  };
}
