"""전역 상수. 튜닝 가능한 값은 여기가 아니라 Setting(DB)에 둔다(AGENTS.md §1.2)."""

# 사용자 역할
ROLE_USER = "USER"
ROLE_ADMIN = "ADMIN"

# 가입 승인 상태 (specs/01 §2)
APPROVAL_PENDING = "PENDING"
APPROVAL_APPROVED = "APPROVED"
APPROVAL_REJECTED = "REJECTED"

# 로그인 실패 사유 코드 (LoginHistory.fail_reason)
# ID·비밀번호가 틀린 경우만 연속 실패로 센다. 나머지는 비밀번호가 맞았다는 뜻이다.
FAIL_NOT_FOUND = "NOT_FOUND"
FAIL_BAD_PASSWORD = "BAD_PASSWORD"
FAIL_PENDING = "PENDING"
FAIL_REJECTED = "REJECTED"
FAIL_INACTIVE = "INACTIVE"
FAIL_LOCKED = "LOCKED"
CREDENTIAL_FAILURES = frozenset({FAIL_NOT_FOUND, FAIL_BAD_PASSWORD})
