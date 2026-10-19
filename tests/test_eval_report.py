"""Run reporting: run directories, config/metrics JSON, curve CSVs, headless plots, report.md."""

import csv
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pytest

from models.evaluation import calibration as C
from models.evaluation import metrics as M
from models.evaluation import provenance as P
from models.evaluation import report as R

ROOT = Path(__file__).resolve().parent.parent
PNGS = ("roc.png", "pr.png", "confusion.png", "reliability.png")
NOW = datetime(2026, 10, 10, 12, 0, 0, tzinfo=timezone.utc)


def _scores(n=400, seed=0, all_negative=False):
    rng = np.random.default_rng(seed)
    y = np.zeros(n, dtype=int) if all_negative else rng.integers(0, 2, n)
    p = np.clip(rng.beta(2, 5, n) + 0.35 * y, 0, 1)
    return y, p


@pytest.fixture
def manifest(tmp_path):
    path = tmp_path / "split_v1.json"
    path.write_bytes(b'{"schema": "graphito.split/v1"}\n')
    return path


@pytest.fixture
def calibration(tmp_path, manifest):
    y, p = _scores(300, seed=1)
    data = C.ScoredSet([f"id{i}" for i in range(y.size)], p, y, split="val", manifest_sha256=P.file_sha256(manifest))
    artifact, _ = C.build_calibration(data, channel="channel_b", score_name="ai_prob", seed=3)
    path = tmp_path / "calibration_channel_b.json"
    C.save_calibration(artifact, path)
    return C.load_calibration(path)


def test_gzip_manifest_path_records_decompressed_sha256(tmp_path):
    import gzip
    import hashlib

    payload = b'{"schema": "graphito.split/v1"}\n'
    path = tmp_path / "split_v1.json.gz"
    path.write_bytes(gzip.compress(payload, mtime=0))
    ctx = R.RunContext.create(
        "channel_b", seed=7, split="test", mode="uncalibrated", manifest_path=path,
        root=tmp_path / "runs", now=NOW, argv=["benchmark_suite.py"],
    )
    assert ctx.config["manifest_sha256"] == hashlib.sha256(payload).hexdigest()


def _run(tmp_path, manifest, calibration=None, *, y=None, p=None, now=NOW, **metric_kwargs):
    if y is None:
        y, p = _scores()
    points = R.operating_points_from_calibration(calibration) if calibration else {}
    ctx = R.RunContext.create(
        "channel_b", seed=7, split="test", mode="calibrated-frozen" if calibration else "uncalibrated",
        manifest_path=manifest, calibration_path=calibration.path if calibration else None,
        thresholds={k: v["threshold"] for k, v in points.items()}, root=tmp_path / "runs", now=now,
        argv=["benchmark_suite.py", "--seed", "7"],
    )
    metrics = R.compute_metrics(
        y, p, channel="channel_b", split="test", mode=ctx.config["mode"], operating_points=points,
        n_boot=50, seed=7, **metric_kwargs,
    )
    ctx.write(y, p, metrics, manifest_stats={"student_overlap": {"train-test": 12}})
    return ctx


def test_run_dir_has_every_artifact_and_provenance(tmp_path, manifest, calibration):
    pytest.importorskip("matplotlib")
    ctx = _run(tmp_path, manifest, calibration, groups={"lang": np.array(["c", "cpp"] * 200)})
    assert ctx.path.parent == tmp_path / "runs" / "channel_b"
    assert re.fullmatch(r"\d{8}-\d{6}", ctx.path.name)
    for name in ("config.json", "metrics.json", "report.md", "roc.csv", "pr.csv", "reliability.csv", *PNGS):
        assert (ctx.path / name).is_file(), name
    config = json.loads((ctx.path / "config.json").read_text(encoding="utf-8"))
    assert config["seed"] == 7 and config["split"] == "test" and config["channel"] == "channel_b"
    assert config["manifest_sha256"] == P.file_sha256(manifest)
    assert config["calibration_sha256"] == calibration.sha256
    assert config["git_sha"] and "dirty" in config
    assert config["versions"]["numpy"] and config["versions"]["scikit-learn"]
    assert config["argv"] == ["benchmark_suite.py", "--seed", "7"]
    assert set(config["thresholds"]) == {"fpr_0.05", "fpr_0.01"}

    metrics = json.loads((ctx.path / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["schema"] == "graphito.metrics/v1" and metrics["artifacts_missing"] == []
    auc = metrics["threshold_free"]["roc_auc"]
    assert auc["value"] is not None and len(auc["ci95"]) == 2 and auc["view"] == "observed"
    assert auc["n"] == 400 and auc["n_pos"] + auc["n_neg"] == 400
    point = metrics["operating_points"]["fpr_0.05"]
    assert point["source"].startswith("calibration") and point["threshold"] == calibration.threshold()["threshold"]
    assert {"observed", "balanced"} <= set(point) and "natural" not in point
    assert point["observed"]["recall"]["view"] == "observed" and "ci95" in point["observed"]["recall"]
    assert metrics["per_group"]["lang"]["roc_auc"]["c"]["n"] == 200
    assert metrics["bootstrap"]["n_boot"] == 50 and metrics["bootstrap"]["unit"] == "sample"
    assert (ctx.path / "roc.csv").read_text(encoding="utf-8").splitlines()[0] == "threshold,fpr,tpr"


def test_operating_points_put_the_calibration_primary_first(calibration):
    points = R.operating_points_from_calibration(calibration)
    assert list(points)[0] == calibration.artifact["primary"] == "fpr_0.05"
    assert points["fpr_0.05"]["primary"] and not points["fpr_0.01"]["primary"]


def test_natural_view_only_when_configured(tmp_path, manifest, calibration):
    ctx = _run(tmp_path, manifest, calibration, natural_prevalence=0.1)
    metrics = json.loads((ctx.path / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["views"] == ["observed", "balanced", "natural"]
    assert metrics["operating_points"]["fpr_0.05"]["natural"]["precision"]["view"] == "natural"


def test_report_md_states_split_hash_thresholds_support_and_overlap(tmp_path, manifest, calibration):
    ctx = _run(tmp_path, manifest, calibration)
    text = (ctx.path / "report.md").read_text(encoding="utf-8")
    assert "test" in text and P.file_sha256(manifest) in text
    assert "fpr_0.05" in text and "fpr_0.01" in text
    assert f"{calibration.threshold()['threshold']:.4f}" in text
    assert calibration.sha256 in text  # threshold source
    assert calibration.threshold("fpr_0.01")["low_support"]  # 300 val samples < 1000 negatives
    assert "low_support" in text
    assert "Student overlap" in text and "train-test" in text


def test_no_git_gives_unknown_and_run_succeeds(tmp_path, manifest, monkeypatch):
    monkeypatch.setattr(P, "GIT", "git-executable-that-does-not-exist")
    ctx = _run(tmp_path, manifest)
    config = json.loads((ctx.path / "config.json").read_text(encoding="utf-8"))
    assert config["git_sha"] == "unknown" and config["dirty"] == "unknown"
    assert (ctx.path / "metrics.json").is_file()


def test_single_class_omits_roc_png_and_explains(tmp_path, manifest):
    y, p = _scores(all_negative=True)
    ctx = _run(tmp_path, manifest, y=y, p=p)
    assert not (ctx.path / "roc.png").exists() and not (ctx.path / "pr.png").exists()
    metrics = json.loads((ctx.path / "metrics.json").read_text(encoding="utf-8"))
    auc = metrics["threshold_free"]["roc_auc"]
    assert auc["value"] is None and auc["reason"] == "single_class" and auc["ci95"] is None
    missing = {m["file"]: m["reason"] for m in metrics["artifacts_missing"]}
    assert missing["roc.png"] in ("single_class", "matplotlib_unavailable")
    text = (ctx.path / "report.md").read_text(encoding="utf-8")
    assert re.search(r"roc\.png.*(single_class|matplotlib_unavailable)", text)


def test_uncalibrated_run_has_no_operating_points(tmp_path, manifest):
    ctx = _run(tmp_path, manifest)
    metrics = json.loads((ctx.path / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["operating_points"] == {} and metrics["mode"] == "uncalibrated"
    assert not (ctx.path / "confusion.png").exists()


def test_runs_in_the_same_second_get_distinct_dirs(tmp_path, manifest):
    first = R.RunContext.create("channel_b", seed=1, split="test", manifest_path=manifest, root=tmp_path, now=NOW)
    second = R.RunContext.create("channel_b", seed=1, split="test", manifest_path=manifest, root=tmp_path, now=NOW)
    assert first.path != second.path and first.path.is_dir() and second.path.is_dir()
    assert second.path.name == first.path.name + "-1"


def test_missing_matplotlib_records_artifacts_missing(tmp_path, manifest, calibration, monkeypatch):
    monkeypatch.setitem(sys.modules, "matplotlib", None)
    ctx = _run(tmp_path, manifest, calibration)
    metrics = json.loads((ctx.path / "metrics.json").read_text(encoding="utf-8"))
    missing = {m["file"]: m["reason"] for m in metrics["artifacts_missing"]}
    assert missing == {name: "matplotlib_unavailable" for name in PNGS}
    assert not any((ctx.path / name).exists() for name in PNGS)
    assert (ctx.path / "roc.csv").is_file() and (ctx.path / "report.md").is_file()


def test_grouped_bootstrap_and_non_probability_scores(tmp_path, manifest):
    y, p = _scores()
    units = np.arange(y.size) // 4
    metrics = R.compute_metrics(
        y, p * 3 - 1, channel="channel_a", split="test", mode="uncalibrated", n_boot=30, seed=0,
        bootstrap_groups=units, bootstrap_unit="atomic_unit",
    )
    assert metrics["bootstrap"]["unit"] == "atomic_unit" and metrics["bootstrap"]["n_units"] == 100
    assert metrics["threshold_free"]["ece"]["value"] is None
    assert metrics["threshold_free"]["ece"]["reason"] == "scores_not_probabilities"


def test_roc_csv_columns_match_roc_curve(tmp_path, manifest):
    y, p = _scores()
    ctx = _run(tmp_path, manifest, y=y, p=p)
    with open(ctx.path / "roc.csv", encoding="utf-8", newline="") as fh:
        header, *rows = list(csv.reader(fh))
    assert header == ["threshold", "fpr", "tpr"]
    fpr, tpr, thresholds = M.roc_curve(y, p)
    table = np.array(rows, dtype=np.float64)
    assert table.shape == (thresholds.size, 3)
    np.testing.assert_array_equal(table[:, 0], thresholds)
    np.testing.assert_array_equal(table[:, 1], fpr)
    np.testing.assert_array_equal(table[:, 2], tpr)
    assert table[0].tolist() == [np.inf, 0.0, 0.0] and table[-1, 1:].tolist() == [1.0, 1.0]


def test_plot_failure_is_recorded_and_run_completes(tmp_path, manifest, calibration, monkeypatch):
    pytest.importorskip("matplotlib")

    def broken_plot(*_args, **_kwargs):
        raise RuntimeError("renderer exploded")

    monkeypatch.setattr(R, "_plot_reliability", broken_plot)
    ctx = _run(tmp_path, manifest, calibration)
    metrics = json.loads((ctx.path / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["artifacts_missing"] == [{"file": "reliability.png", "reason": "RuntimeError: renderer exploded"}]
    assert all((ctx.path / name).is_file() for name in ("roc.png", "pr.png", "confusion.png"))
    assert not (ctx.path / "reliability.png").exists()
    text = (ctx.path / "report.md").read_text(encoding="utf-8")
    assert "reliability.png not produced: RuntimeError: renderer exploded" in text


def _bootstrap_case():
    rng = np.random.default_rng(11)
    y = rng.integers(0, 2, 120)
    p = np.clip(rng.beta(2, 5, 120) + 0.3 * y, 0, 1)
    points = {
        "fpr_0.05": {"threshold": 0.45, "primary": True, "source": "manual"},
        "fpr_0.01": {"threshold": 0.6, "primary": False, "source": "manual"},
    }
    return y, p, points


# CI95s produced by the per-metric implementation (threshold_views recomputed for every
# view/metric entry) before views were shared per resample; sharing must not change them.
EXPECTED_CI95 = {
    ("fpr_0.05", "observed", "precision"): [0.7090909090909091, 0.9155506883604505],
    ("fpr_0.05", "observed", "recall"): [0.6417462686567164, 0.8492115027829313],
    ("fpr_0.05", "observed", "fpr"): [0.06424251152073733, 0.2784604519774011],
    ("fpr_0.05", "observed", "f1"): [0.6839473684210526, 0.8574197120708748],
    ("fpr_0.05", "balanced", "precision"): [0.7193010449741136, 0.9202795031055899],
    ("fpr_0.05", "balanced", "recall"): [0.6417462686567164, 0.8492115027829312],
    ("fpr_0.05", "balanced", "fpr"): [0.06424251152073733, 0.27846045197740094],
    ("fpr_0.05", "balanced", "f1"): [0.6872883082651431, 0.8581643527636547],
    ("fpr_0.05", "natural", "precision"): [0.3904800502260396, 0.7426915229085512],
    ("fpr_0.05", "natural", "recall"): [0.6417462686567164, 0.8492115027829313],
    ("fpr_0.05", "natural", "fpr"): [0.06424251152073734, 0.27846045197740116],
    ("fpr_0.05", "natural", "f1"): [0.4940867736605979, 0.7421368061701858],
    ("fpr_0.01", "observed", "precision"): [0.7212121212121212, 0.9663793103448276],
    ("fpr_0.01", "observed", "recall"): [0.25996551724137934, 0.5],
    ("fpr_0.01", "observed", "fpr"): [0.013732394366197184, 0.09132867132867131],
    ("fpr_0.01", "observed", "f1"): [0.3894289533995416, 0.6546524064171123],
    ("fpr_0.01", "balanced", "precision"): [0.7537288688840021, 0.9715963139120095],
    ("fpr_0.01", "balanced", "recall"): [0.25996551724137923, 0.5],
    ("fpr_0.01", "balanced", "fpr"): [0.01373239436619719, 0.0913286713286713],
    ("fpr_0.01", "balanced", "f1"): [0.39502230716046804, 0.6489272777932572],
    ("fpr_0.01", "natural", "precision"): [0.43354783813940045, 0.8955166757791141],
    ("fpr_0.01", "natural", "recall"): [0.2599655172413794, 0.5],
    ("fpr_0.01", "natural", "fpr"): [0.013732394366197186, 0.0913286713286713],
    ("fpr_0.01", "natural", "f1"): [0.3326698745619827, 0.6159152223059533],
}


def test_operating_point_cis_are_reproducible_for_a_seed():
    y, p, points = _bootstrap_case()
    metrics = R.compute_metrics(
        y, p, channel="c", split="test", mode="m", seed=3, n_boot=40,
        operating_points=points, natural_prevalence=0.2,
    )
    got = {
        (key, view, metric): metrics["operating_points"][key][view][metric]["ci95"]
        for key, view, metric in EXPECTED_CI95
    }
    for name, expected in EXPECTED_CI95.items():
        assert got[name] == pytest.approx(expected, rel=1e-12, abs=1e-15), name


def test_threshold_views_runs_once_per_point_per_resample(monkeypatch):
    y, p, points = _bootstrap_case()
    real = M.threshold_views
    calls = []

    def counting(y_, s_, t, natural_prevalence=None):
        calls.append(t)
        return real(y_, s_, t, natural_prevalence)

    monkeypatch.setattr(M, "threshold_views", counting)
    n_boot = 25
    R.compute_metrics(
        y, p, channel="c", split="test", mode="m", seed=3, n_boot=n_boot,
        operating_points=points, natural_prevalence=0.2,
    )
    # one evaluation per resample plus one on the full set, per operating point
    assert sorted(set(calls)) == [0.45, 0.6]
    assert calls.count(0.45) == calls.count(0.6) == n_boot + 1


def test_replot_curves_default_lang_reproduces_run_pngs(tmp_path, manifest):
    ctx = _run(tmp_path, manifest)
    out = R.replot_curves(ctx.path, tmp_path / "replot")
    assert [p.name for p in out] == ["roc.png", "pr.png"]
    for p in out:
        assert p.read_bytes() == (ctx.path / p.name).read_bytes()


def test_replot_curves_spanish_labels_and_prefix(tmp_path, manifest, monkeypatch):
    ctx = _run(tmp_path, manifest)
    texts = []
    original = R._figure
    monkeypatch.setattr(R, "_figure", lambda mpl, *t: texts.append(t) or original(mpl, *t))
    out = R.replot_curves(ctx.path, tmp_path / "es", lang="es", prefix="charcnn_v2_")
    assert [p.name for p in out] == ["charcnn_v2_roc.png", "charcnn_v2_pr.png"]
    auc = json.loads((ctx.path / "metrics.json").read_text(encoding="utf-8"))["threshold_free"]["roc_auc"]["value"]
    assert texts[0] == (f"ROC (AUC={auc:.4f})", *R.CURVE_LABELS["es"]["roc"][1:])
    assert texts[1][1:] == R.CURVE_LABELS["es"]["pr"][1:]


def test_replot_curves_rejects_unknown_lang(tmp_path, manifest):
    ctx = _run(tmp_path, manifest)
    with pytest.raises(ValueError, match="lang"):
        R.replot_curves(ctx.path, tmp_path / "x", lang="fr")


def test_run_requires_a_manifest_hash(tmp_path):
    with pytest.raises(ValueError, match="manifest"):
        R.RunContext.create("channel_b", seed=1, split="test", root=tmp_path)


def test_package_imports_without_torch_or_matplotlib():
    code = (
        "import sys; sys.modules['torch'] = None; sys.modules['matplotlib'] = None\n"
        "import models.evaluation as ev\n"
        "from models.evaluation import metrics, calibration, report, provenance\n"
        "assert ev.RunContext is report.RunContext\n"
    )
    done = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
