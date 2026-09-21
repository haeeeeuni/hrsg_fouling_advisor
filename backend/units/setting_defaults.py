"""설정값 시드 정의 (specs/13 §4.2).

여기에 있는 값은 **초기 시드값(default)** 일 뿐이다(AGENTS.md §1.2).
실제 적용값은 DB(Setting / UnitSetting)에서 읽으며, 관리자 화면에서 변경할 수 있다.

조회 우선순위: UnitSetting(호기 오버라이드) → Setting(전역) → 여기의 default

각 Phase에서 새 설정이 생기면 이 파일에 정의를 추가하고 `seed_defaults` 를 다시 실행한다.
"""

from dataclasses import dataclass
from typing import Any

from units.standard_fields import DEFAULT_PHYSICAL_RANGES

# 값 타입
TYPE_INT = "INT"
TYPE_FLOAT = "FLOAT"
TYPE_BOOL = "BOOL"
TYPE_STRING = "STRING"
TYPE_JSON = "JSON"

# 카테고리 (specs/13 §4.1)
CAT_FOULING = "FOULING"
CAT_PREPROCESS = "PREPROCESS"
CAT_CLUSTER = "CLUSTER"
CAT_MODEL = "MODEL"
CAT_BENEFIT = "BENEFIT"
CAT_SYSTEM = "SYSTEM"


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


# --- Phase 1: SYSTEM ---
# 다른 카테고리(FOULING/PREPROCESS/CLUSTER/MODEL/BENEFIT)는 해당 Phase에서 추가한다.
SETTING_DEFS: tuple[SettingDef, ...] = (
    SettingDef(
        key="max_upload_mb",
        default=200,
        value_type=TYPE_INT,
        category=CAT_SYSTEM,
        label="업로드 최대 크기",
        description="운전 데이터 파일 1건의 최대 크기",
        unit_label="MB",
        min_value=1,
        max_value=2048,
    ),
    SettingDef(
        key="max_rows_per_file",
        default=5_000_000,
        value_type=TYPE_INT,
        category=CAT_SYSTEM,
        label="파일당 최대 행수",
        unit_label="행",
        min_value=1000,
        max_value=50_000_000,
    ),
    SettingDef(
        key="report_retention_days",
        default=90,
        value_type=TYPE_INT,
        category=CAT_SYSTEM,
        label="리포트 파일 보존 기간",
        description="경과 후 파일을 정리한다. 생성 이력 레코드는 유지된다.",
        unit_label="일",
        min_value=1,
        max_value=3650,
    ),
    SettingDef(
        key="session_timeout_hours",
        default=8,
        value_type=TYPE_INT,
        category=CAT_SYSTEM,
        label="세션 만료 시간",
        description="무활동 기준. 변경은 서버 재기동 후 적용된다.",
        unit_label="시간",
        min_value=1,
        max_value=72,
    ),
    SettingDef(
        key="trend_window_days",
        default=180,
        value_type=TYPE_INT,
        category=CAT_SYSTEM,
        label="추세 분석 기본 구간",
        description="세정 이력이 없을 때 사용하는 추세 적합 구간",
        unit_label="일",
        min_value=30,
        max_value=3650,
    ),
    SettingDef(
        key="min_trend_points",
        default=30,
        value_type=TYPE_INT,
        category=CAT_SYSTEM,
        label="추세 예측 최소 일수",
        description="유효 일자가 이 값 미만이면 추세·D-day를 제공하지 않는다.",
        unit_label="일",
        min_value=5,
        max_value=365,
    ),
    SettingDef(
        key="max_forecast_days",
        default=730,
        value_type=TYPE_INT,
        category=CAT_SYSTEM,
        label="최대 예측 지평",
        description="예측 도달일이 이 값을 넘으면 '도달 예상 없음'으로 표시한다.",
        unit_label="일",
        min_value=30,
        max_value=3650,
    ),
    # specs/01 §3.2 의 로그인 잠금 규칙을 코드에 고정하지 않기 위한 설정값.
    SettingDef(
        key="login_max_failures",
        default=5,
        value_type=TYPE_INT,
        category=CAT_SYSTEM,
        label="로그인 잠금 실패 횟수",
        description="연속 실패가 이 횟수에 도달하면 해당 사번을 일시 차단한다.",
        unit_label="회",
        min_value=1,
        max_value=20,
    ),
    SettingDef(
        key="login_lockout_minutes",
        default=5,
        value_type=TYPE_INT,
        category=CAT_SYSTEM,
        label="로그인 잠금 시간",
        unit_label="분",
        min_value=1,
        max_value=1440,
    ),
    # --- Phase 2: PREPROCESS (업로드 값 검증) ---
    SettingDef(
        key="physical_ranges",
        default=DEFAULT_PHYSICAL_RANGES,
        value_type=TYPE_JSON,
        category=CAT_PREPROCESS,
        label="물리적 허용 범위",
        description=(
            "업로드 검증에서 이 범위를 벗어난 값은 OUT_OF_RANGE 경고와 함께 NaN 처리한다. "
            "max_rated_multiplier 는 호기 정격 출력에 곱해 상한을 정한다."
        ),
    ),
    # --- Phase 3: PREPROCESS (정제·구간 필터) — specs/04, specs/13 §4.2 ---
    SettingDef(
        "min_analysis_load_pct",
        40,
        TYPE_FLOAT,
        CAT_PREPROCESS,
        "분석 최소 부하율",
        unit_label="%",
        min_value=0,
        max_value=100,
    ),
    SettingDef(
        "ramp_threshold_mw_per_min",
        1.0,
        TYPE_FLOAT,
        CAT_PREPROCESS,
        "부하 급변 임계",
        unit_label="MW/min",
        min_value=0.1,
        max_value=50,
    ),
    SettingDef(
        "ramp_settle_min",
        30,
        TYPE_INT,
        CAT_PREPROCESS,
        "부하 급변 후 안정화 시간",
        unit_label="분",
        min_value=0,
        max_value=600,
    ),
    SettingDef(
        "startup_settle_min",
        120,
        TYPE_INT,
        CAT_PREPROCESS,
        "기동 후 안정화 시간",
        unit_label="분",
        min_value=0,
        max_value=1440,
    ),
    SettingDef(
        "shutdown_lead_min",
        60,
        TYPE_INT,
        CAT_PREPROCESS,
        "정지 전 제외 시간",
        unit_label="분",
        min_value=0,
        max_value=1440,
    ),
    SettingDef(
        "db_settle_min",
        60,
        TYPE_INT,
        CAT_PREPROCESS,
        "덕트버너 OFF 후 제외 시간",
        unit_label="분",
        min_value=0,
        max_value=1440,
    ),
    SettingDef(
        "stability_window_min",
        30,
        TYPE_INT,
        CAT_PREPROCESS,
        "안정성 판정 윈도",
        unit_label="분",
        min_value=5,
        max_value=600,
    ),
    SettingDef(
        "load_std_max_mw",
        2.0,
        TYPE_FLOAT,
        CAT_PREPROCESS,
        "부하 표준편차 상한",
        unit_label="MW",
        min_value=0.1,
        max_value=50,
    ),
    SettingDef(
        "exh_temp_std_max_c",
        5.0,
        TYPE_FLOAT,
        CAT_PREPROCESS,
        "배기온도 표준편차 상한",
        unit_label="℃",
        min_value=0.1,
        max_value=50,
    ),
    SettingDef(
        "min_segment_min",
        60,
        TYPE_INT,
        CAT_PREPROCESS,
        "유효 세그먼트 최소 길이",
        unit_label="분",
        min_value=10,
        max_value=1440,
    ),
    SettingDef(
        "mad_k",
        5.0,
        TYPE_FLOAT,
        CAT_PREPROCESS,
        "MAD 이상치 배수",
        description=(
            "작을수록 공격적으로 제거한다. "
            "오염에 의한 완만한 상승을 지우지 않도록 보수적으로 둔다."
        ),
        min_value=1,
        max_value=20,
    ),
    SettingDef(
        "rolling_window_h",
        3,
        TYPE_INT,
        CAT_PREPROCESS,
        "이상치 판정 윈도",
        description="짧을수록 주야 부하 블록을 잘 따라간다. specs/04 §5.2 정정 근거 참조.",
        unit_label="h",
        min_value=1,
        max_value=168,
    ),
    SettingDef(
        "stuck_points",
        30,
        TYPE_INT,
        CAT_PREPROCESS,
        "고정값 판정 연속 점수",
        unit_label="점",
        min_value=3,
        max_value=1000,
    ),
    SettingDef(
        "gap_fill_max_points",
        3,
        TYPE_INT,
        CAT_PREPROCESS,
        "보간 허용 연속 결측",
        unit_label="점",
        min_value=0,
        max_value=100,
    ),
    SettingDef(
        "min_valid_points",
        500,
        TYPE_INT,
        CAT_PREPROCESS,
        "분석 최소 유효 포인트",
        unit_label="점",
        min_value=10,
        max_value=1_000_000,
    ),
    SettingDef(
        "step_change_sigma",
        5.0,
        TYPE_FLOAT,
        CAT_PREPROCESS,
        "단차 탐지 배수",
        description=(
            "인접 구간 평균 차이가 표준편차의 이 배수를 넘으면 "
            "계측기 교정 의심 경고를 띄운다(제외하지 않음)."
        ),
        min_value=1,
        max_value=20,
    ),
    SettingDef(
        "max_missing_rate_pct",
        50,
        TYPE_FLOAT,
        CAT_PREPROCESS,
        "피처 제외 결측률",
        description="이 값을 넘는 컬럼은 모델 피처에서 제외하고 경고한다.",
        unit_label="%",
        min_value=0,
        max_value=100,
    ),
    # --- Phase 3: CLUSTER — specs/05, specs/13 §4.2 ---
    SettingDef(
        "cluster_method",
        "RULE",
        TYPE_STRING,
        CAT_CLUSTER,
        "군집화 방식",
        description="RULE(부하대×계절) 또는 KMEANS",
    ),
    SettingDef(
        "load_band_edges",
        [40, 60, 80, 95],
        TYPE_JSON,
        CAT_CLUSTER,
        "부하대 경계",
        description="부하율(%) 기준 L1~L4 경계",
    ),
    SettingDef(
        "season_definition",
        "MONTH",
        TYPE_STRING,
        CAT_CLUSTER,
        "계절 판정 기준",
        description="MONTH 또는 TEMP",
    ),
    SettingDef(
        "season_boundaries",
        {
            "months": {"SP": [3, 5], "SU": [6, 8], "FA": [9, 11], "WI": [12, 2]},
            "temp": {"cold_max": 10, "warm_min": 20},
        },
        TYPE_JSON,
        CAT_CLUSTER,
        "계절 정의",
        description=(
            "months 는 계절별 [시작월, 종료월], temp 는 TEMP 모드의 온도 경계다. "
            "10~20 ℃ 구간은 봄·가을이 겹쳐 월 정보를 병용한다(specs/05 §2.1)."
        ),
    ),
    SettingDef("kmeans_k", 6, TYPE_INT, CAT_CLUSTER, "KMeans 군집 수", min_value=2, max_value=20),
    SettingDef(
        "min_cluster_points",
        200,
        TYPE_INT,
        CAT_CLUSTER,
        "희소 군집 판정 하한",
        unit_label="점",
        min_value=10,
        max_value=100_000,
    ),
    SettingDef(
        "drop_sparse_clusters",
        True,
        TYPE_BOOL,
        CAT_CLUSTER,
        "희소 군집 집계 제외",
        description="끄면 표본 수 가중치만 낮춰 집계에 포함한다.",
    ),
    SettingDef(
        "out_of_domain_mahalanobis",
        3.0,
        TYPE_FLOAT,
        CAT_CLUSTER,
        "도메인 밖 판정 거리",
        description="학습 분포 대비 마할라노비스 거리 임계",
        min_value=1,
        max_value=20,
    ),
    # --- Phase 3: MODEL — specs/06, specs/13 §4.2 ---
    SettingDef(
        "model_algorithm",
        "GBR",
        TYPE_STRING,
        CAT_MODEL,
        "기대값 모델 알고리즘",
        description="GBR 또는 RIDGE",
    ),
    SettingDef(
        "baseline_length_days",
        30,
        TYPE_INT,
        CAT_MODEL,
        "청정 기준 기간 길이",
        unit_label="일",
        min_value=3,
        max_value=365,
    ),
    SettingDef(
        "baseline_offset_days",
        1,
        TYPE_INT,
        CAT_MODEL,
        "세정 후 기준 시작 지연",
        unit_label="일",
        min_value=0,
        max_value=90,
    ),
    SettingDef(
        "min_baseline_points",
        1000,
        TYPE_INT,
        CAT_MODEL,
        "청정 기준 최소 포인트",
        unit_label="점",
        min_value=50,
        max_value=1_000_000,
    ),
    SettingDef("r2_good", 0.85, TYPE_FLOAT, CAT_MODEL, "R² 양호 기준", min_value=0, max_value=1),
    SettingDef("r2_warn", 0.70, TYPE_FLOAT, CAT_MODEL, "R² 주의 기준", min_value=0, max_value=1),
    SettingDef(
        "mae_stack_good_c",
        3.0,
        TYPE_FLOAT,
        CAT_MODEL,
        "스택온도 MAE 양호 기준",
        unit_label="℃",
        min_value=0,
        max_value=100,
    ),
    SettingDef(
        "mae_stack_warn_c",
        6.0,
        TYPE_FLOAT,
        CAT_MODEL,
        "스택온도 MAE 주의 기준",
        unit_label="℃",
        min_value=0,
        max_value=100,
    ),
    SettingDef(
        "mae_dp_good_pct",
        5.0,
        TYPE_FLOAT,
        CAT_MODEL,
        "차압 MAE 양호 기준",
        description="평균 차압 대비 비율",
        unit_label="%",
        min_value=0,
        max_value=100,
    ),
    SettingDef(
        "mae_dp_warn_pct",
        10.0,
        TYPE_FLOAT,
        CAT_MODEL,
        "차압 MAE 주의 기준",
        unit_label="%",
        min_value=0,
        max_value=100,
    ),
    SettingDef(
        "ridge_alpha", 1.0, TYPE_FLOAT, CAT_MODEL, "Ridge alpha", min_value=0, max_value=1000
    ),
    SettingDef(
        "ridge_poly_degree", 2, TYPE_INT, CAT_MODEL, "Ridge 다항 차수", min_value=1, max_value=3
    ),
    SettingDef(
        "gbr_hyperparams",
        {"max_iter": 300, "learning_rate": 0.05, "max_depth": 3, "min_samples_leaf": 20},
        TYPE_JSON,
        CAT_MODEL,
        "GBR 하이퍼파라미터",
    ),
    SettingDef(
        "use_delta_t_for_dp",
        False,
        TYPE_BOOL,
        CAT_MODEL,
        "차압 모델에 ΔT 피처 사용",
        description=(
            "delta_t = GT배기온도 − 스택온도. 스택온도가 오염에 반응하므로 "
            "켜면 차압 잔차가 과소평가될 수 있다. specs/06 §3.3 참조."
        ),
    ),
    # --- Phase 4: BENEFIT — specs/09 §3.1 전체, specs/13 §4.2 ---
    # 계수 기본값은 참고치다. 관리자가 실적 데이터에 맞춰 보정해야 함을 화면에 명시한다.
    SettingDef(
        "electricity_price",
        120,
        TYPE_FLOAT,
        CAT_BENEFIT,
        "전력 단가",
        description="전력 판매 또는 기회 단가",
        unit_label="원/kWh",
        min_value=0,
        max_value=100000,
    ),
    SettingDef(
        "fuel_price",
        900,
        TYPE_FLOAT,
        CAT_BENEFIT,
        "연료 단가",
        unit_label="원/Nm³",
        min_value=0,
        max_value=1000000,
    ),
    SettingDef(
        "cleaning_cost",
        30_000_000,
        TYPE_FLOAT,
        CAT_BENEFIT,
        "세정 1회 비용",
        unit_label="원",
        min_value=0,
        max_value=100_000_000_000,
    ),
    SettingDef(
        "outage_days",
        2.0,
        TYPE_FLOAT,
        CAT_BENEFIT,
        "세정 정지 일수",
        description="0이면 운전 중 세정(on-line)으로 보아 정지 손실을 0으로 둔다.",
        unit_label="일",
        min_value=0,
        max_value=365,
    ),
    SettingDef(
        "dp_power_loss_coeff",
        0.35,
        TYPE_FLOAT,
        CAT_BENEFIT,
        "배압 손실 계수",
        description="차압 1 kPa 상승당 GT 출력 손실",
        unit_label="%MW/kPa",
        min_value=0,
        max_value=100,
    ),
    SettingDef(
        "stack_temp_loss_coeff",
        0.12,
        TYPE_FLOAT,
        CAT_BENEFIT,
        "스택온도 손실 계수",
        description="스택온도 1 ℃ 상승당 ST 출력 손실",
        unit_label="%MW(ST)/℃",
        min_value=0,
        max_value=100,
    ),
    SettingDef(
        "heat_rate_penalty_coeff",
        0.30,
        TYPE_FLOAT,
        CAT_BENEFIT,
        "열소비율 악화 계수",
        description="차압 1 kPa 상승당 열소비율 악화",
        unit_label="%/kPa",
        min_value=0,
        max_value=100,
    ),
    SettingDef(
        "operating_hours_per_day",
        20,
        TYPE_FLOAT,
        CAT_BENEFIT,
        "일 평균 운전시간",
        unit_label="h/일",
        min_value=0,
        max_value=24,
    ),
    SettingDef(
        "capacity_factor", 0.85, TYPE_FLOAT, CAT_BENEFIT, "이용률", min_value=0, max_value=1
    ),
    SettingDef(
        "cleaning_recovery_ratio",
        0.9,
        TYPE_FLOAT,
        CAT_BENEFIT,
        "세정 후 회복률",
        description="완전 회복 = 1.0",
        min_value=0,
        max_value=1,
    ),
    SettingDef(
        "evaluation_horizon_days",
        365,
        TYPE_INT,
        CAT_BENEFIT,
        "편익 평가 기간",
        unit_label="일",
        min_value=30,
        max_value=3650,
    ),
    SettingDef(
        "discount_rate_annual",
        0.0,
        TYPE_FLOAT,
        CAT_BENEFIT,
        "할인율",
        description="NPV 계산용(선택). 0이면 할인하지 않는다.",
        min_value=0,
        max_value=1,
    ),
    SettingDef(
        "planned_outage_days_ahead",
        180,
        TYPE_INT,
        CAT_BENEFIT,
        "계획 정비까지 남은 일수",
        description="'계획 정비 시 세정' 시나리오 비교에 쓴다.",
        unit_label="일",
        min_value=0,
        max_value=3650,
    ),
    # --- Phase 4: 추세 (specs/08) ---
    SettingDef(
        "trend_model",
        "AUTO",
        TYPE_STRING,
        CAT_FOULING,
        "추세 모델",
        description="AUTO(검증 MAE 최소 자동 선택) 또는 LINEAR/ROBUST/EXPONENTIAL 고정",
    ),
    SettingDef(
        "trend_p_value_max",
        0.05,
        TYPE_FLOAT,
        CAT_FOULING,
        "추세 유의성 기준",
        description="p 값이 이보다 크면 '추세 미확인'으로 본다.",
        min_value=0,
        max_value=1,
    ),
    SettingDef(
        "trend_confidence_weights",
        {"HIGH": 1.0, "MEDIUM": 0.7, "LOW": 0.4},
        TYPE_JSON,
        CAT_FOULING,
        "추세 회귀 신뢰도 가중치",
        description="FI 일자별 신뢰도에 곱하는 회귀 가중치(specs/08 §4).",
    ),
    SettingDef(
        "sensitivity_delta_pct",
        30,
        TYPE_FLOAT,
        CAT_BENEFIT,
        "민감도 변동폭",
        description="주요 파라미터를 ±이 비율만큼 흔들어 순편익 변화를 본다(specs/09 §5).",
        unit_label="%",
        min_value=1,
        max_value=100,
    ),  # --- Phase 5: 정비 이력 키워드 추출 (specs/10 §3.2) ---
    SettingDef(
        "extraction_threshold",
        1.0,
        TYPE_FLOAT,
        CAT_SYSTEM,
        "키워드 추출 임계 점수",
        description="매칭 점수가 이 값 이상이면 오염 관련 후보로 제시한다.",
        min_value=0,
        max_value=100,
    ),
    # --- Phase 7: 옵션 기능 (specs/19) ---
    SettingDef(
        "priority_weights",
        {"fi": 0.30, "slope": 0.20, "daily_loss": 0.35, "urgency": 0.15},
        TYPE_JSON,
        CAT_SYSTEM,
        "세정 우선순위 가중치",
        description=(
            "호기 간 비교 점수의 가중합(specs/19 §3.3). "
            "fi·slope·daily_loss·urgency 합이 1이 되도록 둔다."
        ),
    ),
    SettingDef(
        "backtest_lookahead_days",
        [30, 60, 90],
        TYPE_JSON,
        CAT_SYSTEM,
        "백테스트 컷오프 지점",
        description="세정 실제 일자에서 이 일수만큼 앞선 시점을 컷오프로 삼는다(specs/19 §2.2).",
    ),
    SettingDef(
        "backtest_hit_window_days",
        30,
        TYPE_INT,
        CAT_SYSTEM,
        "백테스트 적중 판정 폭",
        description="예측 오차가 ±이 일수 이내면 적중으로 센다.",
        unit_label="일",
        min_value=1,
        max_value=365,
    ),
    SettingDef(
        "auto_recalc_rolling_months",
        12,
        TYPE_INT,
        CAT_SYSTEM,
        "자동 재계산 기본 창",
        description="ROLLING 모드에서 사용할 최근 개월 수.",
        unit_label="개월",
        min_value=1,
        max_value=120,
    ),
    SettingDef(
        "analysis_stale_minutes",
        30,
        TYPE_INT,
        CAT_SYSTEM,
        "분석 중단 판정 시간",
        description=(
            "이 시간을 넘긴 RUNNING 분석은 워커가 죽은 것으로 보고 실패 처리한다. "
            "분석 목표는 60초이므로(specs/18 §1) 넉넉히 잡는다."
        ),
        unit_label="분",
        min_value=1,
        max_value=1440,
    ),
    # --- Phase 3: FOULING — specs/07, specs/13 §4.2 ---
    SettingDef(
        "fouling_threshold",
        60,
        TYPE_FLOAT,
        CAT_FOULING,
        "오염도 임계치",
        description="세정 권고 기준이 되는 FI 값",
        min_value=0,
        max_value=100,
    ),
    SettingDef(
        "grade_caution_min",
        30,
        TYPE_FLOAT,
        CAT_FOULING,
        "주의 등급 하한",
        min_value=0,
        max_value=100,
    ),
    SettingDef(
        "grade_warning_min",
        60,
        TYPE_FLOAT,
        CAT_FOULING,
        "경고 등급 하한",
        min_value=0,
        max_value=100,
    ),
    SettingDef(
        "weight_dp",
        0.6,
        TYPE_FLOAT,
        CAT_FOULING,
        "차압 가중치",
        description="w_dp + w_st = 1. 차압 미계측(배압 대체) 호기는 0.4 권장.",
        min_value=0,
        max_value=1,
    ),
    SettingDef(
        "weight_stack_temp",
        0.4,
        TYPE_FLOAT,
        CAT_FOULING,
        "스택온도 가중치",
        min_value=0,
        max_value=1,
    ),
    SettingDef(
        "normalization_method",
        "SIGMA",
        TYPE_STRING,
        CAT_FOULING,
        "정규화 방식",
        description="SIGMA 또는 RELATIVE",
    ),
    SettingDef(
        "sigma_ref",
        6.0,
        TYPE_FLOAT,
        CAT_FOULING,
        "σ 기준 배수",
        description="청정 기준 잔차의 이 배수만큼 벗어나면 100점",
        unit_label="σ",
        min_value=1,
        max_value=30,
    ),
    SettingDef(
        "dp_ref_pct",
        30,
        TYPE_FLOAT,
        CAT_FOULING,
        "차압 기준 상승률",
        unit_label="%",
        min_value=1,
        max_value=200,
    ),
    SettingDef(
        "st_ref_c",
        15,
        TYPE_FLOAT,
        CAT_FOULING,
        "스택온도 기준 상승폭",
        unit_label="℃",
        min_value=1,
        max_value=100,
    ),
    SettingDef(
        "out_of_domain_ratio_max",
        0.30,
        TYPE_FLOAT,
        CAT_FOULING,
        "도메인 밖 허용 비율",
        description="이 비율을 넘으면 신뢰도를 '낮음' 으로 낮춘다(specs/07 §5).",
        min_value=0,
        max_value=1,
    ),
    SettingDef(
        "smoothing_window_h",
        24,
        TYPE_INT,
        CAT_FOULING,
        "평활 윈도",
        unit_label="h",
        min_value=1,
        max_value=336,
    ),
    SettingDef(
        "current_window_days",
        7,
        TYPE_INT,
        CAT_FOULING,
        "현재 지수 산정 기간",
        unit_label="일",
        min_value=1,
        max_value=90,
    ),
    SettingDef(
        key="duplicate_policy",
        default="SKIP",
        value_type=TYPE_STRING,
        category=CAT_PREPROCESS,
        label="중복 타임스탬프 기본 정책",
        description="SKIP(건너뛰기) 또는 OVERWRITE(덮어쓰기). 업로드 시 배치별로 바꿀 수 있다.",
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
        import json

        return json.loads(raw)
    return raw


def serialize_value(value: Any, value_type: str) -> str:
    """파이썬 값을 Setting.value(문자열)로 직렬화한다."""
    if value_type == TYPE_JSON:
        import json

        return json.dumps(value, ensure_ascii=False)
    if value_type == TYPE_BOOL:
        return "true" if value else "false"
    return str(value)
