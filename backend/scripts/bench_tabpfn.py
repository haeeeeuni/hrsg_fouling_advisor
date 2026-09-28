"""TabPFN vs HistGradientBoosting 오프라인 벤치마크 (specs/06 §5.1).

실행 전제 — requirements.txt 에 없는 의존성이므로 실험할 때만 임시로 넣는다:
    pip install 'tabpfn>=2.0,<3'      # v2 계열만 상업적 사용 가능
    TABPFN_ALLOW_CPU_LARGE_DATASET=1 TABPFN_DISABLE_TELEMETRY=1 \
        python manage.py shell < scripts/bench_tabpfn.py
    pip uninstall -y tabpfn torch sympy mpmath einops networkx filelock \
        huggingface-hub safetensors tabpfn-common-utils

2026-09-28 측정 결과와 채택 보류 사유는 specs/06 §5.1 에 있다.

**배포에 영향을 주지 않는 실험이다.** requirements.txt 도 모델 코드도 건드리지 않고,
expected_model 의 피처 생성·시간순 분할을 그대로 재사용해 추정기만 바꿔 비교한다.

판단 기준은 두 가지다.
  1) 모델 지표      — MAE·R² (참고용. 노이즈 하한에 가까우면 개선 여지가 없다)
  2) σ_ref 와 FI    — FI = 잔차/σ_ref 라 정확도 개선이 상쇄될 수 있다. 실제로 재본다.
"""

import time

import numpy as np
import pandas as pd

from analysis.pipeline import build_config, load_measurements, resolve_baseline, resolve_ranges
from analysis.services import cleaning, clustering
from analysis.services import expected_model as em
from analysis.services.segmentation import classify, valid_frame
from analysis.models import AnalysisRun, RunStatus
from units.models import Unit
from units.standard_fields import DEFAULT_PHYSICAL_RANGES

UNITS = ("U1", "U2", "U3", "U4", "U5", "SLIM1")
NOISE_SIGMA_STACK = 1.2  # 생성기가 주입하는 값 (scripts/generate_sample_data.py)
MAE_FLOOR_STACK = NOISE_SIGMA_STACK * np.sqrt(2 / np.pi)


def prepare(unit, run, config):
    frame = load_measurements(unit, run.period_start, run.period_end, None)
    ranges = resolve_ranges(config.get("physical_ranges") or DEFAULT_PHYSICAL_RANGES,
                            unit.rated_power_mw)
    cleaned = cleaning.clean(frame, config, ranges)
    valid = valid_frame(classify(cleaned.frame, config).frame)
    return clustering.cluster(valid, config).frame, cleaned.excluded_features


def split_xy(baseline, target, config, excluded):
    """expected_model.train 과 **동일한** 피처·분할을 재현한다."""
    column = em.resolve_target_column(target, baseline)
    frame = baseline.sort_values("timestamp")
    features, names = em.build_features(frame, target, config, excluded)
    y = frame[column]
    usable = y.notna() & features.notna().any(axis=1)
    features, y = features[usable], y[usable]
    cut = int(len(features) * 0.7)
    return (features.iloc[:cut], features.iloc[cut:],
            y.iloc[:cut], y.iloc[cut:], names)


def fit_gbr(xtr, ytr, config):
    pipe, _ = em._make_pipeline(em.ALGO_GBR, config)
    pipe.fit(xtr, ytr)
    return pipe


def fit_tabpfn(xtr, ytr, _config):
    from sklearn.impute import SimpleImputer
    from sklearn.pipeline import Pipeline
    from tabpfn import TabPFNRegressor

    # TabPFN 은 결측을 받아주지만, GBR 과 조건을 맞추려 같은 전처리를 둔다.
    pipe = Pipeline([
        ("impute", SimpleImputer(strategy="median")),
        ("model", TabPFNRegressor(device="cpu", random_state=0)),
    ])
    pipe.fit(xtr, ytr)
    return pipe


def evaluate(name, fitter, xtr, xva, ytr, yva, config):
    started = time.monotonic()
    model = fitter(xtr, ytr, config)
    fit_s = time.monotonic() - started

    started = time.monotonic()
    pred = model.predict(xva)
    pred_s = time.monotonic() - started

    metrics = em._metrics(yva.to_numpy(), pred)
    resid = yva.to_numpy() - pred
    return {
        "name": name,
        "mae": metrics["mae"],
        "r2": metrics["r2"],
        "rmse": metrics["rmse"],
        "sigma_ref": float(np.std(resid)),   # FI 정규화의 분모
        "fit_s": fit_s,
        "pred_s": pred_s,
        "n_train": len(xtr),
    }


def main():
    print(f"  스택온도 MAE 이론 하한: {MAE_FLOOR_STACK:.3f} ℃ (주입 노이즈 σ={NOISE_SIGMA_STACK})")
    print()
    rows = []
    for code in UNITS:
        try:
            unit = Unit.objects.get(code=code)
        except Unit.DoesNotExist:
            continue
        run = AnalysisRun.objects.filter(unit=unit, status=RunStatus.SUCCESS).order_by("-id").first()
        if run is None:
            continue
        config = build_config(unit)
        valid, excluded = prepare(unit, run, config)
        periods, source, _ = resolve_baseline(unit, config, valid)
        from analysis.pipeline import slice_baseline
        baseline = slice_baseline(valid, periods)

        for target, label, unit_s in ((em.TARGET_DP, "차압", "kPa"),
                                      (em.TARGET_ST, "스택온도", "℃")):
            xtr, xva, ytr, yva, names = split_xy(baseline, target, config, excluded)
            if len(xtr) < 20:
                continue
            for name, fitter in (("GBR", fit_gbr), ("TabPFN", fit_tabpfn)):
                try:
                    r = evaluate(name, fitter, xtr, xva, ytr, yva, config)
                except Exception as exc:  # noqa: BLE001
                    print(f"  {code} {label} {name}: 실패 {exc}")
                    continue
                r.update(unit=code, target=label, unit_s=unit_s)
                rows.append(r)
                print(f"  {code:6} {label:5} {name:7} "
                      f"MAE={r['mae']:7.4f} R²={r['r2']:7.3f} σ_ref={r['sigma_ref']:7.4f} "
                      f"학습={r['fit_s']:5.1f}s 예측={r['pred_s']:5.1f}s (n={r['n_train']})")

    df = pd.DataFrame(rows)
    df.to_csv("/private/tmp/claude-501/-Users-yangdani-Desktop-2026-2-work-dir-hrsg-fouling-advisor/"
              "c29bce4e-017d-40d4-8949-7940ea9febcb/scratchpad/bench_result.csv", index=False)
    print()
    print("  === 요약 (TabPFN 이 GBR 대비 얼마나 좋은가, 음수면 개선) ===")
    for target in df["target"].unique():
        sub = df[df["target"] == target]
        piv = sub.pivot(index="unit", columns="name", values=["mae", "sigma_ref"])
        for u in piv.index:
            g, t = piv.loc[u, ("mae", "GBR")], piv.loc[u, ("mae", "TabPFN")]
            gs, ts = piv.loc[u, ("sigma_ref", "GBR")], piv.loc[u, ("sigma_ref", "TabPFN")]
            print(f"    {u:6} {target:5} MAE {(t-g)/g*100:+6.1f}%   σ_ref {(ts-gs)/gs*100:+6.1f}%")


main()
