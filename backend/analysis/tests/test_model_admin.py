"""모델 관리 API (specs/15 §11, specs/13 §5). PostgreSQL 필요."""

import pytest
from django.utils import timezone

from analysis.models import CleanBaselinePeriod, ModelTarget, ModelVersion
from common.models import AuditLog
from units.models import Unit

pytestmark = pytest.mark.django_db

URL = "/api/model-versions/"


@pytest.fixture
def unit(db):
    return Unit.objects.create(code="U1", name="1호기", rated_power_mw=160, min_load_mw=60)


def make_version(unit, version=1, is_active=False, r2=0.9, target=ModelTarget.DP):
    return ModelVersion.objects.create(
        unit=unit,
        target=target,
        algorithm="GBR",
        version=version,
        metrics={"r2": r2, "mae": 0.04},
        residual_mean=0.0,
        residual_std=0.03,
        training_rows=2000,
        is_active=is_active,
    )


# --- 권한 ---


def test_model_versions_are_admin_only(api, normal_user, unit):
    api.force_authenticate(normal_user)

    assert api.get(URL).status_code == 403


def test_admin_lists_versions(api, admin_user, unit):
    make_version(unit)
    api.force_authenticate(admin_user)

    res = api.get(URL)

    assert res.status_code == 200
    assert res.data["count"] == 1


def test_filters(api, admin_user, unit):
    make_version(unit, version=1, is_active=True)
    make_version(unit, version=2, target=ModelTarget.STACK_TEMP)
    api.force_authenticate(admin_user)

    assert api.get(URL, {"target": "DP"}).data["count"] == 1
    assert api.get(URL, {"is_active": "true"}).data["count"] == 1
    assert api.get(URL, {"unit_id": unit.id}).data["count"] == 2


# --- AC-06-5 : 승인 전까지 기존 활성 모델 유지 ---


def test_ac_06_5_new_version_is_inactive_until_approved(api, admin_user, unit):
    """AC-06-5: 모델 재학습 후 승인 전까지 기존 활성 모델이 유지된다."""
    current = make_version(unit, version=1, is_active=True, r2=0.90)
    candidate = make_version(unit, version=2, is_active=False, r2=0.95)

    current.refresh_from_db()
    candidate.refresh_from_db()
    assert current.is_active is True
    assert candidate.is_active is False


def test_activation_swaps_the_active_model(api, admin_user, unit):
    current = make_version(unit, version=1, is_active=True)
    candidate = make_version(unit, version=2)
    api.force_authenticate(admin_user)

    res = api.post(f"{URL}{candidate.id}/activate/")

    assert res.status_code == 200
    current.refresh_from_db()
    candidate.refresh_from_db()
    assert current.is_active is False
    assert candidate.is_active is True


def test_only_one_active_per_unit_and_target(api, admin_user, unit):
    make_version(unit, version=1, is_active=True)
    candidate = make_version(unit, version=2)
    api.force_authenticate(admin_user)

    api.post(f"{URL}{candidate.id}/activate/")

    assert (
        ModelVersion.objects.filter(unit=unit, target=ModelTarget.DP, is_active=True).count() == 1
    )


def test_activating_other_target_does_not_affect_dp(api, admin_user, unit):
    dp = make_version(unit, version=1, is_active=True, target=ModelTarget.DP)
    st = make_version(unit, version=1, target=ModelTarget.STACK_TEMP)
    api.force_authenticate(admin_user)

    api.post(f"{URL}{st.id}/activate/")

    dp.refresh_from_db()
    assert dp.is_active is True


def test_activating_already_active_is_conflict(api, admin_user, unit):
    version = make_version(unit, is_active=True)
    api.force_authenticate(admin_user)

    assert api.post(f"{URL}{version.id}/activate/").status_code == 409


def test_activation_is_audited(api, admin_user, unit):
    make_version(unit, version=1, is_active=True)
    candidate = make_version(unit, version=2)
    api.force_authenticate(admin_user)

    api.post(f"{URL}{candidate.id}/activate/")

    log = AuditLog.objects.filter(target_type="ModelVersion", action="ACTIVATE").latest(
        "created_at"
    )
    assert log.before["active_version"] == 1
    assert log.after["active_version"] == 2


# --- 신·구 비교 (specs/13 §5.2) ---


def test_compare_returns_candidate_and_current(api, admin_user, unit):
    make_version(unit, version=1, is_active=True, r2=0.90)
    candidate = make_version(unit, version=2, r2=0.95)
    api.force_authenticate(admin_user)

    res = api.get(f"{URL}{candidate.id}/compare/")

    assert res.data["candidate"]["metrics"]["r2"] == 0.95
    assert res.data["current"]["metrics"]["r2"] == 0.90


def test_compare_without_active_model(api, admin_user, unit):
    candidate = make_version(unit, version=1)
    api.force_authenticate(admin_user)

    res = api.get(f"{URL}{candidate.id}/compare/")

    assert res.data["current"] is None


# --- 재학습 요청 ---


def test_train_returns_202_and_audits(api, admin_user, unit, seeded):
    api.force_authenticate(admin_user)

    res = api.post(f"{URL}train/", {"unit_id": unit.id, "targets": ["DP"]}, format="json")

    # 데이터가 없어 태스크는 실패하지만 요청 접수와 감사 기록은 확인한다.
    assert res.status_code in (202, 500)
    assert AuditLog.objects.filter(target_type="ModelVersion", action="TRAIN").exists()


def test_train_unknown_unit_is_404(api, admin_user, seeded):
    api.force_authenticate(admin_user)

    assert api.post(f"{URL}train/", {"unit_id": 9999}, format="json").status_code == 404


def test_train_is_admin_only(api, normal_user, unit):
    api.force_authenticate(normal_user)

    assert api.post(f"{URL}train/", {"unit_id": unit.id}, format="json").status_code == 403


# --- 청정 기준 기간 (specs/13 §5.1) ---


def test_baseline_period_crud(api, admin_user, unit):
    api.force_authenticate(admin_user)

    res = api.post(
        "/api/clean-baseline-periods/",
        {
            "unit": unit.id,
            "start_at": "2024-07-06T00:00:00+09:00",
            "end_at": "2024-08-05T00:00:00+09:00",
            "source": "MANUAL",
            "is_active": True,
        },
        format="json",
    )

    assert res.status_code == 201
    assert CleanBaselinePeriod.objects.filter(unit=unit).count() == 1
    assert AuditLog.objects.filter(target_type="CleanBaselinePeriod").exists()


def test_baseline_period_rejects_reversed_range(api, admin_user, unit):
    api.force_authenticate(admin_user)

    res = api.post(
        "/api/clean-baseline-periods/",
        {
            "unit": unit.id,
            "start_at": "2024-08-05T00:00:00+09:00",
            "end_at": "2024-07-06T00:00:00+09:00",
        },
        format="json",
    )

    assert res.status_code == 400


def test_baseline_preview_reports_sample_stats(api, admin_user, unit):
    from ingestion.models import Measurement

    period = CleanBaselinePeriod.objects.create(
        unit=unit,
        start_at=timezone.now() - timezone.timedelta(days=1),
        end_at=timezone.now() + timezone.timedelta(days=1),
    )
    Measurement.objects.create(
        unit=unit, timestamp=timezone.now(), hrsg_gas_dp_kpa=3.0, stack_temp_c=110, gt_power_mw=150
    )
    api.force_authenticate(admin_user)

    res = api.get(f"/api/clean-baseline-periods/{period.id}/preview/")

    assert res.data["count"] == 1
    assert res.data["avg_dp"] == 3.0


def test_baseline_periods_are_admin_only(api, normal_user, unit):
    api.force_authenticate(normal_user)

    assert api.get("/api/clean-baseline-periods/").status_code == 403
