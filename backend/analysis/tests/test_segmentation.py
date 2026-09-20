"""운전 구간 분류 검증 (specs/04 §7, §10). DB 불필요."""

import numpy as np
import pandas as pd

from analysis.services import segmentation as seg
from analysis.tests.factories import config, steady_frame


def run(frame, **overrides):
    return seg.classify(frame, config(**overrides))


def test_clean_steady_data_is_mostly_valid():
    result = run(steady_frame(days=5))

    assert result.stats["valid_ratio"] > 0.9
    assert result.frame.segment_state.value_counts().idxmax() == seg.STEADY


def test_ac_04_1_startup_and_shutdown_are_excluded_and_counted():
    """AC-04-1: 기동/정지 구간이 자동 제외되고 제외 건수가 요약에 표시된다."""
    frame = steady_frame(days=6)
    # 하루치 정지 + 전후 전환
    frame.loc[300:450, "gt_power_mw"] = 0.0

    result = run(frame)

    states = set(result.frame.segment_state)
    assert seg.OFFLINE in states
    assert seg.STARTUP in states
    assert seg.SHUTDOWN in states
    assert result.stats["excluded_by_reason"]["기동/정지"] > 150


def test_startup_settle_window_is_respected():
    frame = steady_frame(days=4)
    frame.loc[100:200, "gt_power_mw"] = 0.0

    result = run(frame, startup_settle_min=120)  # 10분 주기 → 12 포인트

    after = result.frame.iloc[201:213]
    assert (after.segment_state == seg.STARTUP).all()


def test_ac_04_2_duct_burner_on_and_settle_window_excluded():
    """AC-04-2: 덕트버너 ON 구간과 OFF 후 60분이 제외된다."""
    frame = steady_frame(days=3)
    frame.loc[100:130, "duct_burner_on"] = True

    result = run(frame, db_settle_min=60)  # 10분 주기 → 6 포인트

    assert (result.frame.loc[100:130, "segment_state"] == seg.DUCT_BURNER).all()
    assert (result.frame.loc[131:136, "segment_state"] == seg.DUCT_BURNER).all()
    assert result.frame.loc[140, "segment_state"] == seg.STEADY


def test_load_ramp_is_excluded():
    frame = steady_frame(days=3)
    frame.loc[200, "gt_power_mw"] = frame.loc[199, "gt_power_mw"] + 30  # 3 MW/min

    result = run(frame)

    assert result.frame.loc[200, "segment_state"] == seg.LOAD_RAMP


def test_low_load_is_excluded():
    frame = steady_frame(days=3)
    frame.loc[300:320, "gt_power_mw"] = 62.0  # 정격 160 대비 38.8% < 40%

    result = run(frame)

    assert (result.frame.loc[305:318, "segment_state"] == seg.LOW_LOAD).any()


def test_unstable_load_is_excluded():
    frame = steady_frame(days=3)
    rng = np.random.default_rng(0)
    frame.loc[200:240, "gt_power_mw"] += rng.normal(0, 8, 41)  # 표준편차 > 2 MW

    result = run(frame)

    assert (result.frame.loc[200:240, "segment_state"] == seg.UNSTABLE).any()


def test_short_segments_are_dropped():
    frame = steady_frame(days=3)
    # 짧은 STEADY 섬을 만들기 위해 앞뒤를 덕트버너로 막는다
    frame.loc[100:150, "duct_burner_on"] = True
    frame.loc[155:200, "duct_burner_on"] = True

    result = run(frame, min_segment_min=60, db_settle_min=0)

    assert seg.SHORT_SEGMENT in set(result.frame.segment_state)


def test_valid_frame_returns_only_steady():
    result = run(steady_frame(days=3))

    valid = seg.valid_frame(result.frame)

    assert (valid.segment_state == seg.STEADY).all()
    assert valid.is_valid.all()


def test_exclusion_reason_is_recorded_for_every_excluded_row():
    frame = steady_frame(days=4)
    frame.loc[100:200, "gt_power_mw"] = 0.0

    result = run(frame)

    excluded = result.frame[~result.frame.is_valid]
    assert (excluded.exclusion_reason != "").all()
    assert (result.frame[result.frame.is_valid].exclusion_reason == "").all()


def test_segment_ids_are_assigned_only_to_valid_rows():
    result = run(steady_frame(days=3))

    assert result.frame.loc[result.frame.is_valid, "segment_id"].notna().all()
    assert result.frame.loc[~result.frame.is_valid, "segment_id"].isna().all()


# --- 경고 (specs/04 §9) ---


def test_low_valid_ratio_triggers_warning():
    frame = steady_frame(days=4)
    frame.loc[: int(len(frame) * 0.9), "gt_power_mw"] = 0.0

    result = run(frame)

    assert any(w["code"] == "LOW_VALID_RATIO" for w in result.warnings)


def test_duct_burner_always_on_triggers_warning():
    frame = steady_frame(days=3)
    frame["duct_burner_on"] = True

    result = run(frame)

    assert any(w["code"] == "DUCT_BURNER_ALWAYS_ON" for w in result.warnings)


def test_stats_include_every_exclusion_group():
    result = run(steady_frame(days=3))

    assert set(result.stats["excluded_by_reason"]) == set(seg.EXCLUSION_GROUPS)


def test_empty_frame_is_handled():
    result = seg.classify(pd.DataFrame(columns=["timestamp", "gt_power_mw"]), config())

    assert result.stats["row_total"] == 0


# --- AC-04-4 : 설정 변경이 즉시 반영 ---


def test_ac_04_4_threshold_change_takes_effect_immediately():
    """AC-04-4: 정제 임계값을 바꾸면 다음 분석에 즉시 반영된다."""
    frame = steady_frame(days=3)
    frame.loc[300:320, "gt_power_mw"] = 62.0

    strict = run(frame, min_analysis_load_pct=40).stats["row_valid"]
    relaxed = run(frame, min_analysis_load_pct=30).stats["row_valid"]

    assert relaxed > strict
