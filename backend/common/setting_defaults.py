"""설정값 시드 정의 (specs/08 §4).

여기에 있는 값은 **초기 시드값(default)** 일 뿐이다(AGENTS.md §1.2).
실제 적용값은 DB(Setting)에서 읽으며, 관리자 화면에서 변경할 수 있다.

조회 우선순위: Setting(DB) → 여기의 default

마일스톤마다 새 설정이 생기면 이 파일에 정의를 추가하고 `seed_defaults` 를 다시 실행한다.
specs/08 §4 의 설정 키 표도 같은 변경에서 갱신한다.
"""

import json
from dataclasses import dataclass
from typing import Any

# 값 타입
TYPE_INT = "INT"
TYPE_FLOAT = "FLOAT"
TYPE_BOOL = "BOOL"
TYPE_STRING = "STRING"
TYPE_TEXT = "TEXT"  # 여러 줄 문자열 (시스템 프롬프트 등)
TYPE_JSON = "JSON"

# 분류 (specs/08 §4)
CAT_AUTH = "AUTH"
CAT_CHAT = "CHAT"
CAT_RAG = "RAG"
CAT_CHUNK = "CHUNK"
CAT_DOCUMENT = "DOCUMENT"
CAT_LLM = "LLM"
CAT_CALC = "CALC"
CAT_CHECKLIST = "CHECKLIST"

CATEGORY_LABELS: dict[str, str] = {
    CAT_AUTH: "인증",
    CAT_CHAT: "질의응답",
    CAT_RAG: "검색(RAG)",
    CAT_CHUNK: "청크",
    CAT_DOCUMENT: "문서",
    CAT_LLM: "LLM",
    CAT_CALC: "계산기",
    CAT_CHECKLIST: "체크리스트",
}


@dataclass(frozen=True)
class SettingDef:
    key: str
    default: Any
    value_type: str
    category: str
    label: str
    description: str = ""
    unit_label: str = ""
    min_value: float | None = None
    max_value: float | None = None


SETTING_DEFS: tuple[SettingDef, ...] = (
    # --- N1: 인증 (specs/01 AUTH-8) ---
    SettingDef(
        key="login_max_failures",
        default=5,
        value_type=TYPE_INT,
        category=CAT_AUTH,
        label="로그인 연속 실패 허용 횟수",
        description="이 횟수만큼 연속으로 틀리면 해당 ID 로그인을 잠근다.",
        unit_label="회",
        min_value=3,
        max_value=20,
    ),
    SettingDef(
        key="login_lockout_minutes",
        default=5,
        value_type=TYPE_INT,
        category=CAT_AUTH,
        label="로그인 잠금 시간",
        unit_label="분",
        min_value=1,
        max_value=1440,
    ),
    # --- N2: 계산기 (specs/05 §3.1) ---
    SettingDef(
        key="calc_default_method",
        default="드라이아이스 세정",
        value_type=TYPE_STRING,
        category=CAT_CALC,
        label="기본 세정 공법",
        description="계산기를 열 때 처음 선택되는 공법 이름. 없거나 비활성이면 첫 공법을 쓴다.",
    ),
    # --- N3: 체크리스트 이메일 문구 (specs/07 CHK-5) ---
    SettingDef(
        key="chk_email_header_ko",
        default=(
            "안녕하십니까.\nHRSG 세정 평가를 위해 아래 자료를 요청드립니다. "
            "정확한 평가를 위해 가능한 범위에서 회신 부탁드립니다."
        ),
        value_type=TYPE_TEXT,
        category=CAT_CHECKLIST,
        label="복사 문구 머리말 (한국어)",
    ),
    SettingDef(
        key="chk_email_footer_ko",
        default="문의 사항은 회신 주시면 안내드리겠습니다. 감사합니다.",
        value_type=TYPE_TEXT,
        category=CAT_CHECKLIST,
        label="복사 문구 맺음말 (한국어)",
    ),
    SettingDef(
        key="chk_email_header_en",
        default=(
            "Dear Sir or Madam,\nFor the HRSG cleaning assessment, "
            "we kindly request the data below. Please share what is available."
        ),
        value_type=TYPE_TEXT,
        category=CAT_CHECKLIST,
        label="복사 문구 머리말 (영어)",
    ),
    SettingDef(
        key="chk_email_footer_en",
        default="Please let us know if you have any questions. Thank you.",
        value_type=TYPE_TEXT,
        category=CAT_CHECKLIST,
        label="복사 문구 맺음말 (영어)",
    ),
)

SETTING_DEF_BY_KEY: dict[str, SettingDef] = {d.key: d for d in SETTING_DEFS}


def cast_value(raw: str, value_type: str) -> Any:
    """Setting.value(문자열)를 value_type 에 맞게 변환한다."""
    if value_type == TYPE_INT:
        return int(float(raw))
    if value_type == TYPE_FLOAT:
        return float(raw)
    if value_type == TYPE_BOOL:
        return str(raw).strip().lower() in {"1", "true", "yes", "on"}
    if value_type == TYPE_JSON:
        return json.loads(raw)
    return raw


def serialize_value(value: Any, value_type: str) -> str:
    """파이썬 값을 Setting.value(문자열)로 직렬화한다."""
    if value_type == TYPE_JSON:
        return json.dumps(value, ensure_ascii=False)
    if value_type == TYPE_BOOL:
        return "true" if value else "false"
    return str(value)
