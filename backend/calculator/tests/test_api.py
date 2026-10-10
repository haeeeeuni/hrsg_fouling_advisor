"""계산 API — 응답 구조, 비공개, 기본값, 오류 (specs/05 AC-05-5·7·8·9, specs/10 §4)."""

import json
import time

import pytest

from reference.models import CalcParameterSet, CleaningMethod, GtModel, SmpPrice
from reference.param_defs import PARAM_DEFS

pytestmark = pytest.mark.django_db

LOSS = "/api/calculator/loss/"
METHODS = "/api/calculator/methods/"
PINCH = "/api/calculator/pinch-approach/"
OPTIONS = "/api/calculator/options/"

# USER 응답에 나오면 안 되는 이름 — 계수 키와 경보·트립 한계 필드 (CALC-8)
SECRET_KEYS = [d.key for d in PARAM_DEFS if d.group == "LOSS"] + [
    "backpressure_alarm_kpa",
    "backpressure_trip_kpa",
    "exhaust_temp_alarm_c",
    "exhaust_temp_trip_c",
    "recovery_ratio",
    "params",
]


@pytest.fixture
def as_user(api, normal_user, seeded):
    api.force_authenticate(normal_user)
    return api


@pytest.fixture
def model_a():
    return GtModel.objects.get(name="가상 모델 A (F급)")


def test_options_give_defaults_without_limits(as_user):
    data = as_user.get(OPTIONS).json()

    assert len(data["gt_models"]) == 3
    assert data["smp"]["is_estimate"] is True
    assert (
        data["defaults"]["cleaning_method_id"]
        == CleaningMethod.objects.get(name="드라이아이스 세정").id
    )
    body = json.dumps(data)
    for key in SECRET_KEYS:
        assert key not in body, key


def test_loss_fills_defaults_from_design_values(as_user, model_a):
    data = as_user.post(LOSS, {"gt_model_id": model_a.id}, format="json").json()

    assert data["inputs"]["backpressure_kpa"] == model_a.design_backpressure_kpa
    assert data["inputs"]["gt_power_mw"] == model_a.rated_gt_mw
    assert data["results"]["daily_loss_won"] == 0
    assert data["results"]["recovery"]["payback_days"] is None  # 화면은 '회수 불가'
    assert data["status"]["state"] == "NORMAL"


def test_loss_response_has_no_coefficients_or_limits(as_user, model_a):
    """AC-05-5 — 결과만 있고 계수·한계값 원본은 없다."""
    body = json.dumps(
        as_user.post(
            LOSS, {"gt_model_id": model_a.id, "backpressure_kpa": 4.8}, format="json"
        ).json()
    )
    for key in SECRET_KEYS:
        assert key not in body, key


def test_methods_response_has_no_coefficients(as_user, model_a):
    body = json.dumps(as_user.post(METHODS, {"gt_model_id": model_a.id}, format="json").json())
    for key in SECRET_KEYS:
        assert key not in body, key


def test_methods_marks_best_net_benefit(as_user, model_a):
    rows = as_user.post(
        METHODS,
        {"gt_model_id": model_a.id, "backpressure_kpa": 4.0, "stack_temp_c": 100},
        format="json",
    ).json()["results"]["methods"]

    assert len(rows) == 3
    assert sum(r["is_best"] for r in rows) == 1
    assert rows[0]["is_best"]
    assert rows[0]["net_benefit_won"] >= rows[-1]["net_benefit_won"]


@pytest.mark.parametrize(
    ("backpressure", "state"), [(4.4, "NORMAL"), (4.5, "ALARM"), (5.5, "TRIP")]
)
def test_status_changes_at_limits(as_user, model_a, backpressure, state):
    """AC-05-3"""
    data = as_user.post(
        LOSS, {"gt_model_id": model_a.id, "backpressure_kpa": backpressure}, format="json"
    ).json()

    assert data["status"]["state"] == state


def test_placeholder_notice_until_all_values_are_real(as_user, model_a):
    """AC-05-8 — 임시값을 하나라도 쓰면 안내가 붙는다."""
    data = as_user.post(LOSS, {"gt_model_id": model_a.id}, format="json").json()
    assert data["meta"]["uses_placeholder"] is True
    assert "임시 참조값" in data["meta"]["notices"][0]

    GtModel.objects.update(is_placeholder=False)
    CleaningMethod.objects.update(is_placeholder=False)
    CalcParameterSet.objects.update(is_seed=False)
    data = as_user.post(LOSS, {"gt_model_id": model_a.id}, format="json").json()
    assert data["meta"]["uses_placeholder"] is False


def test_user_smp_is_marked(as_user, model_a):
    data = as_user.post(
        LOSS, {"gt_model_id": model_a.id, "smp_won_per_kwh": 200}, format="json"
    ).json()

    assert data["meta"]["smp"]["user_input"] is True
    assert data["meta"]["smp"]["source"] == "사용자 입력"


def test_registered_smp_shows_date_and_source(as_user, model_a):
    smp = as_user.post(LOSS, {"gt_model_id": model_a.id}, format="json").json()["meta"]["smp"]

    assert smp["as_of"]
    assert smp["source"]
    assert smp["is_estimate"] is True


def test_smp_required_when_none_registered(as_user, model_a):
    SmpPrice.objects.all().delete()

    res = as_user.post(LOSS, {"gt_model_id": model_a.id}, format="json")

    assert res.status_code == 400
    assert res.json()["error"]["code"] == "SMP_REQUIRED"


@pytest.mark.parametrize(
    ("payload", "field"),
    [
        ({"backpressure_kpa": -1}, "backpressure_kpa"),
        ({"stack_temp_c": 900}, "stack_temp_c"),
        ({"operating_hours_per_day": 0}, "operating_hours_per_day"),
        ({"smp_won_per_kwh": 0}, "smp_won_per_kwh"),
        ({"gt_power_mw": 400}, "gt_power_mw"),
    ],
)
def test_invalid_inputs_are_reported_by_field(as_user, model_a, payload, field):
    res = as_user.post(LOSS, {"gt_model_id": model_a.id, **payload}, format="json")

    assert res.status_code == 400
    assert field in res.json()["error"]["details"]


def test_inactive_gt_model_is_not_usable(as_user, model_a):
    model_a.is_active = False
    model_a.save()

    assert as_user.post(LOSS, {"gt_model_id": model_a.id}, format="json").status_code == 404


def test_pinch_returns_criteria_and_rejects_impossible_input(as_user):
    ok = as_user.post(
        PINCH,
        {
            "stages": [
                {
                    "drum_pressure_barg": 120,
                    "evaporator_outlet_gas_temp_c": 335,
                    "economizer_outlet_water_temp_c": 318,
                }
            ]
        },
        format="json",
    ).json()
    assert ok["meta"]["criteria"]["pinch_range_c"] == [5, 15]
    assert ok["results"]["stages"][0]["label"] == "1단"

    bad = as_user.post(
        PINCH,
        {
            "stages": [
                {
                    "drum_pressure_barg": 120,
                    "evaporator_outlet_gas_temp_c": 300,
                    "economizer_outlet_water_temp_c": 290,
                }
            ]
        },
        format="json",
    )
    assert bad.status_code == 400
    assert bad.json()["error"]["code"] == "PINCH_INPUT_INVALID"


def test_pinch_allows_at_most_three_stages(as_user):
    stage = {
        "drum_pressure_barg": 10,
        "evaporator_outlet_gas_temp_c": 200,
        "economizer_outlet_water_temp_c": 170,
    }

    assert as_user.post(PINCH, {"stages": [stage] * 4}, format="json").status_code == 400


def test_calculation_uses_new_parameter_version(api, normal_user, admin_user, seeded, model_a):
    """파라미터를 바꾸면 다음 계산부터 새 버전이 쓰이고 결과에 버전이 남는다(CALC-10)."""
    payload = {"gt_model_id": model_a.id, "backpressure_kpa": 4.0}
    api.force_authenticate(normal_user)
    before = api.post(LOSS, payload, format="json").json()

    params = {**CalcParameterSet.objects.get(is_active=True).params, "dp_power_loss_coeff": 0.7}
    api.force_authenticate(admin_user)
    assert (
        api.post("/api/admin/calc-parameter-sets/", {"params": params}, format="json").status_code
        == 201
    )

    api.force_authenticate(normal_user)
    after = api.post(LOSS, payload, format="json").json()

    assert before["meta"]["param_version"] == "p1"
    assert after["meta"]["param_version"] == "p2"
    assert after["results"]["power_loss_gt_mw"] == pytest.approx(
        2 * before["results"]["power_loss_gt_mw"]
    )


def test_calculation_is_fast(as_user, model_a):
    """AC-05-9 — 즉시 반응을 위해 계산 API 가 빨라야 한다(로컬 기준 평균으로 확인)."""
    payload = {"gt_model_id": model_a.id, "backpressure_kpa": 4.2, "stack_temp_c": 101}
    as_user.post(LOSS, payload, format="json")
    start = time.perf_counter()
    for _ in range(20):
        as_user.post(LOSS, payload, format="json")
    assert (time.perf_counter() - start) / 20 < 0.3
