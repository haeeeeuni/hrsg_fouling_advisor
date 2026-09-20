"""군집화 검증 (specs/05 §7). DB 불필요."""

import numpy as np
import pandas as pd
import pytest

from analysis.services import clustering as cl
from analysis.tests.factories import config, steady_frame


def frame_at(load_ratio: float, month: int, n: int = 50) -> pd.DataFrame:
    index = pd.date_range(f"2024-{month:02d}-10", periods=n, freq="10min")
    power = 160 * load_ratio
    return pd.DataFrame(
        {
            "timestamp": index,
            "gt_power_mw": np.full(n, power),
            "ambient_temp_c": np.full(n, 20.0),
            "exhaust_flow": np.full(n, 400.0),
            "gt_exhaust_temp_c": np.full(n, 600.0),
            "hrsg_gas_dp_kpa": np.full(n, 3.0),
            "stack_temp_c": np.full(n, 110.0),
        }
    )


def test_ac_05_1_load_92pct_in_july_is_l3_su():
    """AC-05-1: 부하율 92%, 7월 데이터가 L3-SU 로 분류된다."""
    result = cl.cluster(frame_at(0.92, 7), config())

    assert set(result.frame.cluster_key) == {"L3-SU"}


@pytest.mark.parametrize(
    ("ratio", "band"), [(0.45, "L1"), (0.70, "L2"), (0.90, "L3"), (0.98, "L4")]
)
def test_load_bands(ratio, band):
    result = cl.cluster(frame_at(ratio, 7), config())

    assert result.frame.cluster_key.iloc[0].startswith(band)


@pytest.mark.parametrize(("month", "season"), [(4, "SP"), (7, "SU"), (10, "FA"), (1, "WI")])
def test_seasons_by_month(month, season):
    result = cl.cluster(frame_at(0.9, month), config())

    assert result.frame.cluster_key.iloc[0].endswith(season)


def test_ac_05_2_changing_band_edges_changes_assignment():
    """AC-05-2: 관리자가 부하대 경계를 바꾸면 다음 분석부터 반영된다."""
    frame = frame_at(0.65, 7)  # 부하율 65%

    # 기본 경계 [40,60,80,95] → L2(60~80)
    default = cl.cluster(frame, config()).frame.cluster_key.iloc[0]
    # 경계를 [40,70,85,95] 로 옮기면 65% 는 L1(40~70) 으로 내려간다
    shifted = cl.cluster(frame, config(load_band_edges=[40, 70, 85, 95])).frame.cluster_key.iloc[0]

    assert default == "L2-SU"
    assert shifted == "L1-SU"


def test_temp_season_resolves_spring_autumn_ambiguity():
    """정정된 specs/05 §2.1 — 10~20℃ 구간은 월 정보로 봄/가을을 가른다."""
    spring = frame_at(0.9, 4)
    autumn = frame_at(0.9, 10)
    spring["ambient_temp_c"] = 15.0
    autumn["ambient_temp_c"] = 15.0

    cfg = config(season_definition="TEMP")
    assert cl.cluster(spring, cfg).frame.cluster_key.iloc[0].endswith("SP")
    assert cl.cluster(autumn, cfg).frame.cluster_key.iloc[0].endswith("FA")


def test_temp_season_uses_temperature_outside_ambiguous_band():
    hot = frame_at(0.9, 1)  # 1월이지만 25℃
    hot["ambient_temp_c"] = 25.0

    assert (
        cl.cluster(hot, config(season_definition="TEMP")).frame.cluster_key.iloc[0].endswith("SU")
    )


# --- AC-05-4 : 희소 군집 ---


def test_ac_05_4_sparse_clusters_are_flagged():
    """AC-05-4: 표본이 부족한 군집이 '표본 부족'으로 표시된다."""
    frame = pd.concat([frame_at(0.9, 7, n=300), frame_at(0.45, 7, n=5)], ignore_index=True)

    result = cl.cluster(frame, config(min_cluster_points=200))

    sparse = result.summary[result.summary.is_sparse]
    assert set(sparse.cluster_key) == {"L1-SU"}
    assert any(w["code"] == "SPARSE_CLUSTERS" for w in result.warnings)


def test_single_cluster_triggers_diversity_warning():
    result = cl.cluster(frame_at(0.9, 7, n=300), config())

    assert any(w["code"] == "SINGLE_CLUSTER" for w in result.warnings)


# --- 요약 (specs/05 §5) ---


def test_summary_has_counts_shares_and_labels():
    frame = pd.concat([frame_at(0.9, 7, n=300), frame_at(0.65, 7, n=100)], ignore_index=True)

    result = cl.cluster(frame, config())

    assert set(result.summary.columns) >= {
        "cluster_key",
        "sample_count",
        "share_pct",
        "is_sparse",
        "label",
        "avg_load_ratio_pct",
        "avg_ambient_temp_c",
    }
    assert result.summary.sample_count.sum() == 400
    assert result.summary.share_pct.sum() == pytest.approx(100.0, abs=0.1)
    assert result.summary.set_index("cluster_key").loc["L3-SU", "label"] == "고부하·여름"


# --- KMeans (AC-05-3) ---


def test_ac_05_3_kmeans_labels_stay_stable_across_runs():
    """AC-05-3: KMeans 재실행 시에도 동일 군집이 동일 라벨을 유지한다."""
    frame = steady_frame(days=10)
    cfg = config(cluster_method="KMEANS", kmeans_k=3)

    first = cl.cluster(frame, cfg)
    second = cl.cluster(frame, cfg)

    pd.testing.assert_series_equal(
        first.frame.cluster_key, second.frame.cluster_key, check_names=False
    )


def test_kmeans_params_allow_reassignment_of_new_data():
    frame = steady_frame(days=10)
    cfg = config(cluster_method="KMEANS", kmeans_k=3)

    fitted = cl.cluster(frame, cfg)
    reassigned = cl.cluster(frame.iloc[:100], cfg, params=fitted.params)

    assert list(reassigned.frame.cluster_key) == list(fitted.frame.cluster_key.iloc[:100])


def test_kmeans_falls_back_to_rule_when_samples_are_insufficient():
    """specs/05 §6 — 표본 부족 시 RULE 로 폴백하고 사유를 기록한다."""
    result = cl.cluster(frame_at(0.9, 7, n=2), config(cluster_method="KMEANS", kmeans_k=10))

    assert any(w["code"] == "KMEANS_FALLBACK" for w in result.warnings)
    assert result.params["method"] == cl.METHOD_RULE


# --- 도메인 판정 (specs/05 §6) ---


def test_mahalanobis_flags_out_of_domain_points():
    frame = steady_frame(days=10)
    params = cl.build_domain_params(frame, list(cl.KMEANS_FEATURES))

    far = frame.iloc[:5].copy()
    far["gt_power_mw"] = 400.0
    far["exhaust_flow"] = 2000.0

    inside = cl.mahalanobis_distance(frame.iloc[:5], params)
    outside = cl.mahalanobis_distance(far, params)

    assert (outside > inside).all()


def test_domain_params_empty_when_too_few_samples():
    assert cl.build_domain_params(frame_at(0.9, 7, n=2), list(cl.KMEANS_FEATURES)) == {}
