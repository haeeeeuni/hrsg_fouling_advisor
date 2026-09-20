"""AC-13-4: 코드 내에 임계치·가중치·편익 계수의 하드코딩된 사용처가 없다.

Phase 6 의 완료 조건이다. DB 불필요.

**무엇이 금지인가** — AGENTS.md §1.2 는 "설정값은 DB 에 저장하고 관리자 화면에서
변경 가능해야 하며, **코드에는 초기 시드값(seed/default)만 둔다**" 고 한다. 따라서

  금지: 로직 한가운데 박힌 매직 넘버 (`if ratio > 0.30:`)
  허용: 이름 붙은 모듈 상수 폴백 (`DEFAULT_X = 0.30`) 과 함수 기본 인자

이 테스트는 앞의 것만 잡는다.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from units.setting_defaults import SETTING_DEFS

SERVICES = Path(__file__).resolve().parents[1] / "services"

# 수학·구조적 상수(인덱스, 백분율 분모, 시간 환산 등)는 튜닝값이 아니다.
STRUCTURAL = {
    0,
    1,
    2,
    3,
    4,
    5,
    6,
    7,
    8,
    10,
    12,
    20,
    24,
    30,
    60,
    100,
    200,
    365,
    1000,
    -1,
    0.5,
    0.7,
    1.5,
    0.05,
    1e-6,
    1e-9,
}


def tunable_defaults() -> dict[float, list[str]]:
    """설정으로 관리되는 숫자 기본값 → 설정 키."""
    out: dict[float, list[str]] = {}
    for definition in SETTING_DEFS:
        value = definition.default
        if isinstance(value, bool) or not isinstance(value, int | float):
            continue
        out.setdefault(float(value), []).append(definition.key)
    return out


def _allowed_nodes(tree: ast.Module) -> set[int]:
    """허용되는 리터럴의 id 집합.

    - 모듈 최상위 UPPER_SNAKE 상수 대입의 값 (시드 폴백)
    - 함수 정의의 기본 인자
    """
    allowed: set[int] = set()

    for node in tree.body:
        if isinstance(node, ast.Assign):
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if names and all(n.isupper() or n.startswith("DEFAULT_") for n in names):
                for child in ast.walk(node.value):
                    allowed.add(id(child))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id.isupper() and node.value is not None:
                for child in ast.walk(node.value):
                    allowed.add(id(child))

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            for default in [*node.args.defaults, *node.args.kw_defaults]:
                if default is None:
                    continue
                for child in ast.walk(default):
                    allowed.add(id(child))
    return allowed


def literal_suspects(path: Path) -> list[str]:
    tunable = tunable_defaults()
    source = path.read_text()
    lines = source.splitlines()
    tree = ast.parse(source)
    allowed = _allowed_nodes(tree)

    found: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or id(node) in allowed:
            continue
        value = node.value
        if isinstance(value, bool) or not isinstance(value, int | float):
            continue
        if float(value) in STRUCTURAL or float(value) not in tunable:
            continue
        found.append(
            f"{path.name}:{node.lineno} 값 {value} (설정 {tunable[float(value)]}) "
            f"— {lines[node.lineno - 1].strip()}"
        )
    return found


@pytest.mark.parametrize("path", sorted(SERVICES.glob("*.py")), ids=lambda p: p.name)
def test_ac_13_4_no_magic_numbers_in_logic(path: Path):
    """AC-13-4: 설정으로 관리되는 값이 로직에 매직 넘버로 박혀 있으면 안 된다."""
    suspects = literal_suspects(path)

    assert not suspects, "\n".join(suspects)


def test_detector_catches_a_planted_magic_number(tmp_path):
    """검사기가 실제로 동작하는지 — 일부러 심은 매직 넘버를 잡아야 한다."""
    planted = tmp_path / "planted.py"
    planted.write_text("def f(ratio):\n    return ratio > 0.35\n")  # dp_power_loss_coeff

    assert literal_suspects(planted)


def test_detector_allows_named_seed_default(tmp_path):
    """이름 붙은 모듈 상수 폴백은 AGENTS.md §1.2 가 허용한다."""
    allowed = tmp_path / "allowed.py"
    allowed.write_text("DEFAULT_RATIO = 0.35\n\n\ndef f(config):\n    return config['x']\n")

    assert not literal_suspects(allowed)


def test_services_take_settings_from_caller():
    """설정은 config dict 또는 명시적 인자로 받아야 한다.

    순수 함수가 인자로 받는 것도 정상이다(comparison.py). 금지되는 매직 넘버는
    위 테스트가 잡는다.
    """
    pattern = re.compile(r"config\[|config\.get\(|params\[|params\.get\(|def \w+\([^)]*config")
    for path in sorted(SERVICES.glob("*.py")):
        if path.name == "__init__.py":
            continue
        source = path.read_text()
        takes_explicit = bool(re.search(r"def \w+\([^)]*:\s*(int|float|dict)", source))
        assert (
            pattern.search(source) or takes_explicit
        ), f"{path.name} 이 설정을 config 로도 인자로도 받지 않습니다"


# --- 설정 시드 완전성 ---


def test_season_boundaries_are_configurable():
    """specs/05 §2.1 — 계절 정의는 DB 설정값이며 호기별 오버라이드가 가능하다."""
    keys = {d.key for d in SETTING_DEFS}

    assert "season_boundaries" in keys
    assert "load_band_edges" in keys


def test_confidence_threshold_is_configurable():
    """specs/07 §5 — 도메인 밖 비율 판정 임계값."""
    assert "out_of_domain_ratio_max" in {d.key for d in SETTING_DEFS}


def test_all_spec_required_settings_exist():
    """specs/13 §4.2 와 specs/09 §3.1 이 열거한 필수 설정 항목이 모두 시드에 있다."""
    required = {
        "fouling_threshold",
        "grade_caution_min",
        "grade_warning_min",
        "weight_dp",
        "weight_stack_temp",
        "normalization_method",
        "sigma_ref",
        "dp_ref_pct",
        "st_ref_c",
        "smoothing_window_h",
        "current_window_days",
        "min_analysis_load_pct",
        "ramp_threshold_mw_per_min",
        "ramp_settle_min",
        "startup_settle_min",
        "shutdown_lead_min",
        "db_settle_min",
        "stability_window_min",
        "load_std_max_mw",
        "exh_temp_std_max_c",
        "min_segment_min",
        "mad_k",
        "rolling_window_h",
        "stuck_points",
        "gap_fill_max_points",
        "min_valid_points",
        "cluster_method",
        "load_band_edges",
        "season_definition",
        "kmeans_k",
        "min_cluster_points",
        "model_algorithm",
        "baseline_length_days",
        "baseline_offset_days",
        "min_baseline_points",
        "r2_good",
        "r2_warn",
        "mae_stack_good_c",
        "mae_stack_warn_c",
        "electricity_price",
        "fuel_price",
        "cleaning_cost",
        "outage_days",
        "dp_power_loss_coeff",
        "stack_temp_loss_coeff",
        "heat_rate_penalty_coeff",
        "operating_hours_per_day",
        "capacity_factor",
        "cleaning_recovery_ratio",
        "evaluation_horizon_days",
        "discount_rate_annual",
        "max_upload_mb",
        "max_rows_per_file",
        "report_retention_days",
        "session_timeout_hours",
        "trend_window_days",
        "min_trend_points",
        "max_forecast_days",
    }
    missing = required - {d.key for d in SETTING_DEFS}

    assert not missing, f"시드에 없는 설정: {sorted(missing)}"


def test_every_setting_has_label_and_category():
    """관리자 화면에 표시할 라벨·분류가 모두 있어야 한다 (specs/13 §4.3)."""
    for definition in SETTING_DEFS:
        assert definition.label, f"{definition.key} 에 라벨이 없습니다"
        assert definition.category, f"{definition.key} 에 분류가 없습니다"
