"""전역 상수. 튜닝 가능한 값은 여기가 아니라 Setting(DB)에 둔다(AGENTS.md §1.2)."""

# 재현성: 난수를 쓰는 모든 곳에 random_state=RANDOM_SEED 를 전달한다(AGENTS.md §4).
RANDOM_SEED = 42

# 사용자 역할
ROLE_USER = "USER"
ROLE_ADMIN = "ADMIN"

# 로그인 실패 사유 코드 (LoginHistory.fail_reason)
FAIL_NOT_FOUND = "NOT_FOUND"
FAIL_NAME_MISMATCH = "NAME_MISMATCH"
FAIL_INACTIVE = "INACTIVE"
FAIL_BAD_PASSWORD = "BAD_PASSWORD"
FAIL_LOCKED = "LOCKED"
