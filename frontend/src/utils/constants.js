/** 등급 표현 (specs/16 §8). 색상만으로 정보를 전달하지 않고 항상 라벨을 함께 쓴다. */
export const GRADE = {
  NORMAL: { label: '정상', variant: 'success', range: '오염도 지수 < 30' },
  CAUTION: { label: '주의', variant: 'warning', range: '30 ≤ 오염도 지수 < 60' },
  WARNING: { label: '경고', variant: 'danger', range: '오염도 지수 ≥ 60' },
}

export const ROLE = {
  USER: '일반 사용자',
  ADMIN: '관리자',
}

/** 분석 실행 단계 — 진행률 표시에 사용 (specs/11 §8) */
export const ANALYSIS_STAGES = ['정제', '군집화', '기대값 예측', '오염도 지수', '추세', '편익']
