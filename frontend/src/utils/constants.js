/** 화면 공통 상수. 상태 표현은 색만으로 전달하지 않고 항상 아이콘·문구를 함께 쓴다(specs/12 UI-6). */

export const ROLE = {
  USER: '일반 사용자',
  ADMIN: '관리자',
}

export const APPROVAL = {
  PENDING: { label: '승인 대기', variant: 'warning' },
  APPROVED: { label: '승인', variant: 'success' },
  REJECTED: { label: '반려', variant: 'secondary' },
}

/** 정상·주의·위험 (specs/12 §3). 계산기·챗봇 카드가 공유한다. */
export const STATUS = {
  NORMAL: { label: '정상', variant: 'success', icon: 'bi-check-circle-fill' },
  CAUTION: { label: '주의', variant: 'warning', icon: 'bi-exclamation-triangle-fill' },
  DANGER: { label: '위험', variant: 'danger', icon: 'bi-octagon-fill' },
}

/**
 * 앱의 세 기능 (specs/11 §2). 소개·홈·헤더가 같은 목록을 쓴다.
 * milestone 은 아직 준비 중인 기능의 구현 예정 단계(PROJECT.md §6)다.
 */
export const FEATURES = [
  {
    key: 'chat',
    route: 'chat',
    title: '질의응답',
    icon: 'bi-chat-dots',
    summary: 'HRSG 세정·성능 질문에 기술 자료와 사례를 근거로 답합니다.',
    detail: '수치가 필요한 질문은 계산기로 계산해 카드로 보여 줍니다. 한국어·영어 질문을 모두 받습니다.',
    milestone: 'N5',
  },
  {
    key: 'calculator',
    route: 'calculator',
    title: '계산기',
    icon: 'bi-calculator',
    summary: '가스터빈 모델과 운전값으로 현재 상태, 예상 손실, 세정 회수 효과를 계산합니다.',
    detail: '세정 공법별 비용을 비교하고 핀치·어프로치로 열 회수 상태를 점검합니다.',
    milestone: 'N2',
  },
  {
    key: 'checklist',
    route: 'checklist',
    title: '플랜트 데이터 요청 체크리스트',
    icon: 'bi-ui-checks',
    summary: '정확한 평가에 꼭 필요한 데이터 항목을 빠짐없이 요청하고 받은 항목을 관리합니다.',
    detail: '받은 항목을 체크해 진행률을 보고, 남은 항목을 이메일 본문으로 복사합니다.',
    milestone: 'N3',
  },
]
