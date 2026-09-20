"""표준 항목 정의 (specs/02 §3).

분석 코드는 원본 CSV 컬럼명을 절대 알지 못한다. 호기별 ColumnMapping 이
원본 → 표준 항목으로 변환한 뒤에만 데이터가 들어온다(AGENTS.md §5.1).
"""

from dataclasses import dataclass, field

TIMESTAMP = "timestamp"


@dataclass(frozen=True)
class StandardField:
    key: str
    label: str
    dtype: str  # 'datetime' | 'float' | 'bool'
    unit_label: str = ""
    description: str = ""
    # 이 항목이 대체할 수 있는 항목(예: fuel_flow 는 exhaust_flow 의 대체재)
    substitutes: tuple[str, ...] = field(default_factory=tuple)


STANDARD_FIELDS: tuple[StandardField, ...] = (
    StandardField(TIMESTAMP, "측정 시각", "datetime", "", "KST 기준"),
    StandardField("gt_power_mw", "GT 출력", "float", "MW"),
    StandardField("ambient_temp_c", "대기온도", "float", "℃"),
    StandardField("gt_exhaust_temp_c", "GT 배기온도", "float", "℃"),
    StandardField("exhaust_flow", "배기유량", "float", "kg/s"),
    StandardField("hrsg_gas_dp_kpa", "HRSG 가스측 차압", "float", "kPa"),
    StandardField("stack_temp_c", "스택 온도", "float", "℃"),
    StandardField("duct_burner_on", "덕트버너 상태", "bool", "", "1=가동"),
    # 대체 항목 (specs/02 §3.2)
    StandardField("fuel_flow", "연료유량", "float", "Nm³/h", substitutes=("exhaust_flow",)),
    StandardField("igv_position_pct", "IGV 개도", "float", "%", substitutes=("exhaust_flow",)),
    StandardField(
        "gt_backpressure_kpa", "GT 배압", "float", "kPa", substitutes=("hrsg_gas_dp_kpa",)
    ),
    # 선택 항목 (specs/02 §3.3)
    StandardField("st_power_mw", "ST 출력", "float", "MW"),
    StandardField("steam_flow_tph", "증기 유량", "float", "t/h"),
    StandardField("feedwater_temp_c", "급수 온도", "float", "℃"),
    StandardField("ambient_pressure_kpa", "대기압", "float", "kPa"),
    StandardField("humidity_pct", "습도", "float", "%"),
)

FIELD_BY_KEY: dict[str, StandardField] = {f.key: f for f in STANDARD_FIELDS}
ALL_FIELD_KEYS: tuple[str, ...] = tuple(f.key for f in STANDARD_FIELDS)

# 수치 컬럼 (Measurement 에 float 로 저장되는 항목)
NUMERIC_FIELDS: tuple[str, ...] = tuple(f.key for f in STANDARD_FIELDS if f.dtype == "float")

# --- 필수 충족 규칙 (specs/02 §3.4) ---
# 1) 아래 항목이 모두 매핑되어 있을 것
ALWAYS_REQUIRED: tuple[str, ...] = (
    TIMESTAMP,
    "gt_power_mw",
    "ambient_temp_c",
    "gt_exhaust_temp_c",
    "stack_temp_c",
    "duct_burner_on",
)
# 2) 유량 계열 중 최소 1개
FLOW_ALTERNATIVES: tuple[str, ...] = ("exhaust_flow", "fuel_flow", "igv_position_pct")
# 3) 차압 계열 중 최소 1개
DP_ALTERNATIVES: tuple[str, ...] = ("hrsg_gas_dp_kpa", "gt_backpressure_kpa")


def check_required(mapped_fields: set[str]) -> list[dict]:
    """필수 충족 규칙 위반 목록을 반환한다. 빈 리스트면 매핑 완료."""
    problems: list[dict] = []

    missing = [key for key in ALWAYS_REQUIRED if key not in mapped_fields]
    if missing:
        problems.append(
            {
                "code": "REQUIRED_FIELD_UNMAPPED",
                "message": "필수 표준 항목이 매핑되지 않았습니다.",
                "fields": missing,
            }
        )

    if not (set(FLOW_ALTERNATIVES) & mapped_fields):
        problems.append(
            {
                "code": "FLOW_FIELD_UNMAPPED",
                "message": "배기유량 또는 대체 항목(연료유량·IGV 개도) 중 하나는 매핑해야 합니다.",
                "fields": list(FLOW_ALTERNATIVES),
            }
        )

    if not (set(DP_ALTERNATIVES) & mapped_fields):
        problems.append(
            {
                "code": "DP_FIELD_UNMAPPED",
                "message": "가스측 차압 또는 GT 배압 중 하나는 매핑해야 합니다.",
                "fields": list(DP_ALTERNATIVES),
            }
        )

    return problems


# --- 물리적 허용 범위 시드 (specs/03 §4.3) ---
# "(설정값, 기본)" 이므로 DB Setting('physical_ranges', JSON)로 관리하고 여기는 시드값이다.
# gt_power_mw 의 상한은 호기 정격에 비례하므로 max_rated_multiplier 로 표현한다.
DEFAULT_PHYSICAL_RANGES: dict[str, dict] = {
    "gt_power_mw": {"min": -5, "max_rated_multiplier": 1.2},
    "ambient_temp_c": {"min": -40, "max": 60},
    "gt_exhaust_temp_c": {"min": 0, "max": 800},
    "stack_temp_c": {"min": 0, "max": 400},
    "hrsg_gas_dp_kpa": {"min": 0, "max": 20},
    "gt_backpressure_kpa": {"min": 0, "max": 20},
    "humidity_pct": {"min": 0, "max": 100},
}


def resolve_ranges(ranges: dict[str, dict], rated_power_mw: float | None) -> dict[str, tuple]:
    """설정의 범위 정의를 (min, max) 튜플로 확정한다."""
    resolved: dict[str, tuple] = {}
    for key, spec in ranges.items():
        low = spec.get("min")
        high = spec.get("max")
        multiplier = spec.get("max_rated_multiplier")
        if high is None and multiplier is not None and rated_power_mw:
            high = rated_power_mw * multiplier
        resolved[key] = (low, high)
    return resolved
