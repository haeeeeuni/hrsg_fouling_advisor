"""오염 키워드 사전 시드 (specs/10 §3.1).

여기는 **초기 시드값**이다. 관리자가 화면에서 추가·삭제·수정하며,
`restore-defaults` 로 이 목록을 되돌릴 수 있다.
"""

CATEGORY_CLEANING = "CLEANING"
CATEGORY_FOULING = "FOULING"
CATEGORY_INSPECTION = "INSPECTION"
CATEGORY_EXCLUDE = "EXCLUDE"

DEFAULT_KEYWORDS: tuple[tuple[str, str], ...] = (
    # 세정
    ("세정", CATEGORY_CLEANING),
    ("수세", CATEGORY_CLEANING),
    ("화학세정", CATEGORY_CLEANING),
    ("건식세정", CATEGORY_CLEANING),
    ("워터젯", CATEGORY_CLEANING),
    ("드라이아이스", CATEGORY_CLEANING),
    ("전열면 청소", CATEGORY_CLEANING),
    ("핀 튜브 청소", CATEGORY_CLEANING),
    ("튜브 클리닝", CATEGORY_CLEANING),
    ("soot blowing", CATEGORY_CLEANING),
    ("cleaning", CATEGORY_CLEANING),
    # 오염 징후
    ("오염", CATEGORY_FOULING),
    ("파울링", CATEGORY_FOULING),
    ("회분 부착", CATEGORY_FOULING),
    ("차압 상승", CATEGORY_FOULING),
    ("스택온도 상승", CATEGORY_FOULING),
    ("전열면 막힘", CATEGORY_FOULING),
    ("스케일", CATEGORY_FOULING),
    ("퇴적", CATEGORY_FOULING),
    # 점검
    ("내부 점검", CATEGORY_INSPECTION),
    ("개방 점검", CATEGORY_INSPECTION),
    ("육안 점검", CATEGORY_INSPECTION),
    # 제외어
    ("계획 없음", CATEGORY_EXCLUDE),
    ("취소", CATEGORY_EXCLUDE),
    ("미시행", CATEGORY_EXCLUDE),
)
