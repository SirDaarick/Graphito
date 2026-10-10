"""Benchmark suite on the evaluation package: test-only samples, calibration modes, run dirs (BS1-BS5).

Everything runs on the synthetic `eval_factory` tree (split manifest -> golden test/val corpora ->
golden manifests) with the STUB engine: no real data, models or network. Stub numbers are NOT
evidence about the real models.
"""

import ast
import importlib.util
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pytest

from eval_factory import make_tree
from models.evaluation.calibration import ScoredSet, build_calibration, load_calibration, save_calibration
from models.evaluation.provenance import file_sha256
from models.evaluation.splits import SplitConfig, build_split, write_manifest

ROOT = Path(__file__).resolve().parent.parent
SUITE_PATH = ROOT / "scripts" / "benchmark_suite.py"
CHANNELS = ("channel_a", "channel_b")
RUN_FILES = ("config.json", "metrics.json", "report.md", "roc.csv", "pr.csv", "reliability.csv")


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


suite = _load("benchmark_suite", SUITE_PATH)
corpus_builder = _load("build_corpus", ROOT / "data" / "golden_set" / "build_corpus.py")
manifest_builder = _load("build_manifest", ROOT / "data" / "golden_set" / "build_manifest.py")


@pytest.fixture(scope="module")
def env(tmp_path_factory):
    """Split manifest plus test and val golden manifests built from the synthetic factory tree."""
    base = tmp_path_factory.mktemp("bench")
    tree = make_tree(base / "repo")
    config = SplitConfig(
        seed=7, repo_root=tree.repo_root, raw_root=tree.raw_root, ai_root=tree.ai_root,
        gt_static=tree.gt_static, gt_ambiguous=(tree.gt_dynamic,),
    )
    split_path = write_manifest(build_split(config), base / "split.json")
    golden = {}
    for split in ("test", "val"):
        corpus = base / f"corpus_{split}"
        corpus_builder.build_corpus(split_path, split, corpus, repo_root=tree.repo_root)
        out = base / f"manifest_{split}.json"
        assert manifest_builder.main([str(corpus), "--out", str(out)]) == 0
        golden[split] = out
    return {"base": base, "split": split_path, "test": golden["test"], "val": golden["val"]}


def _calibration(env, tmp_path, channel, method, threshold):
    """A frozen calibration file whose primary threshold is `threshold` (bound to the split hash)."""
    rng = np.random.default_rng(0)
    scores = np.concatenate([rng.uniform(0, 0.6, 40), rng.uniform(0.4, 1, 40)])
    y = np.r_[np.zeros(40, int), np.ones(40, int)]
    data = ScoredSet([f"v{i}" for i in range(80)], scores, y, "val", file_sha256(env["split"]))
    artifact, _ = build_calibration(data, channel=channel, score_name=channel, seed=1, method=method)
    entry = artifact["thresholds"][artifact["primary"]]
    entry.update(threshold=threshold, unachievable=False, reason=None)
    path = tmp_path / f"calibration_{channel}.json"
    save_calibration(artifact, path)
    return path


def _args(env, runs, *extra):
    return [
        "--manifest", str(env["test"]), "--split-manifest", str(env["split"]), "--engine", "stub",
        "--runs-root", str(runs), "--n-boot", "20", "--seed", "3", *extra,
    ]


def _channel_dirs(runs: Path):
    tops = sorted((runs / "benchmark").iterdir())
    assert len(tops) == 1, tops
    top = tops[0]
    dirs = {}
    for channel in (*CHANNELS, "fused"):
        found = sorted((top / channel).iterdir()) if (top / channel).is_dir() else []
        if found:
            dirs[channel] = found[0]
    return top, dirs


def _json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


# --- BS2: frozen calibration thresholds -------------------------------------------------------


def test_frozen_thresholds_from_calibration_reach_config(env, tmp_path):
    cal_a = _calibration(env, tmp_path, "channel_a", "isotonic", 0.61)
    cal_b = _calibration(env, tmp_path, "channel_b", "platt", 0.33)
    runs = tmp_path / "runs"
    code = suite.main(_args(env, runs, "--mode", "calibrated-frozen",
                            "--calibration-a", str(cal_a), "--calibration-b", str(cal_b)))
    assert code == 0
    _, dirs = _channel_dirs(runs)
    config_a, config_b = _json(dirs["channel_a"] / "config.json"), _json(dirs["channel_b"] / "config.json")
    assert config_a["thresholds"]["fpr_0.05"] == 0.61
    assert config_b["thresholds"]["fpr_0.05"] == 0.33
    assert config_a["calibration_sha256"] == file_sha256(cal_a)
    assert config_a["threshold_source"] == f"calibration:{file_sha256(cal_a)}"
    metrics_a = _json(dirs["channel_a"] / "metrics.json")
    assert metrics_a["mode"] == "calibrated-frozen"
    assert metrics_a["operating_points"]["fpr_0.05"]["threshold"] == 0.61
    fused = _json(dirs["fused"] / "metrics.json")
    point = fused["operating_points"]["or_fpr_0.05"]
    assert point["rule"] == "or"
    assert point["channel_thresholds"] == {"channel_a": 0.61, "channel_b": 0.33}


def test_frozen_calibration_is_not_modified(env, tmp_path):
    cal_a = _calibration(env, tmp_path, "channel_a", "isotonic", 0.61)
    cal_b = _calibration(env, tmp_path, "channel_b", "platt", 0.33)
    before = (cal_a.read_bytes(), cal_b.read_bytes())
    suite.main(_args(env, tmp_path / "runs", "--mode", "calibrated-frozen", "--calibration-dir", str(tmp_path)))
    assert (cal_a.read_bytes(), cal_b.read_bytes()) == before


def test_missing_calibration_exits_non_zero_pointing_to_the_calibration_step(env, tmp_path, capsys):
    runs = tmp_path / "runs"
    code = suite.main(_args(env, runs, "--mode", "calibrated-frozen"))
    assert code != 0
    err = capsys.readouterr().err
    assert "calibrated-fit-in-run" in err and "calibration_channel_a.json" in err
    code = suite.main(_args(env, runs, "--mode", "calibrated-frozen", "--calibration-dir", str(tmp_path / "nope")))
    assert code != 0
    assert not (runs / "benchmark").exists(), "no run dir is created before calibration is resolved"


def test_calibration_of_another_split_manifest_is_refused(env, tmp_path, capsys):
    cal_a = _calibration(env, tmp_path, "channel_a", "isotonic", 0.61)
    cal_b = _calibration(env, tmp_path, "channel_b", "platt", 0.33)
    doc = _json(cal_b)
    doc["manifest"]["sha256"] = "e" * 64
    save_calibration(doc, cal_b)
    code = suite.main(_args(env, tmp_path / "runs", "--mode", "calibrated-frozen",
                            "--calibration-a", str(cal_a), "--calibration-b", str(cal_b)))
    assert code != 0
    assert "sha256" in capsys.readouterr().err


# --- BS1: test split only ---------------------------------------------------------------------


def test_val_golden_set_passed_as_test_raises_naming_the_id(env, tmp_path):
    golden = _json(env["val"])
    with pytest.raises(suite.BenchmarkError) as info:
        suite.run_suite(
            golden=golden, root=Path(golden["root"]), split_manifest_path=env["split"],
            engine=suite.make_engine("stub"), engine_name="stub", mode="uncalibrated",
            seed=1, n_boot=10, runs_root=tmp_path / "runs",
        )
    assert golden["samples"][0]["split_id"] in str(info.value)


def test_non_test_split_id_behind_a_test_tag_raises_naming_it(env, tmp_path):
    golden, val = _json(env["test"]), _json(env["val"])
    leaked = val["samples"][0]["split_id"]
    golden["samples"][0]["split_id"] = leaked  # tagged "test" but the split manifest says val
    with pytest.raises(suite.BenchmarkError, match=re.escape(leaked)):
        suite.require_split(golden["samples"], "test", env["split"], golden["source_manifest_sha256"])


def test_golden_manifest_without_source_hash_is_refused(env, tmp_path):
    golden = _json(env["test"])
    golden["source_manifest_sha256"] = None
    with pytest.raises(suite.BenchmarkError, match="source_manifest_sha256"):
        suite.run_suite(
            golden=golden, root=Path(golden["root"]), split_manifest_path=env["split"],
            engine=suite.make_engine("stub"), engine_name="stub", mode="uncalibrated",
            seed=1, n_boot=10, runs_root=tmp_path / "runs",
        )


# --- modes ------------------------------------------------------------------------------------


def test_uncalibrated_mode_emits_no_operating_points(env, tmp_path):
    runs = tmp_path / "runs"
    assert suite.main(_args(env, runs, "--mode", "uncalibrated")) == 0
    top, dirs = _channel_dirs(runs)
    assert set(dirs) == set(CHANNELS), "fused needs calibrated decisions"
    for channel in CHANNELS:
        metrics = _json(dirs[channel] / "metrics.json")
        assert metrics["mode"] == "uncalibrated"
        assert metrics["operating_points"] == {}
        assert _json(dirs[channel] / "config.json")["thresholds"] == {}
        assert metrics["threshold_free"]["roc_auc"]["value"] is not None
    summary = _json(top / "summary.json")
    assert summary["skipped"]["fused"]


def test_fit_in_run_fits_on_val_only_and_freezes_before_test(env, tmp_path, monkeypatch):
    calls = []
    real = suite.score_manifest

    async def spy(golden, root, engine):
        # the run is still staged while scoring, so look anywhere under the runs root
        frozen = sorted(p.name for p in (tmp_path / "runs").rglob("calibration_*.json"))
        calls.append(({s["split"] for s in golden["samples"]}, frozen))
        return await real(golden, root, engine)

    monkeypatch.setattr(suite, "score_manifest", spy)
    code = suite.main(_args(env, tmp_path / "runs", "--calibrate", "--val-manifest", str(env["val"])))
    assert code == 0
    assert calls == [
        ({"val"}, []),
        ({"test"}, ["calibration_channel_a.json", "calibration_channel_b.json"]),
    ]
    top, dirs = _channel_dirs(tmp_path / "runs")
    val_ids = {s["split_id"] for s in _json(env["val"])["samples"]}
    for channel, method in (("channel_a", "isotonic"), ("channel_b", "platt")):
        cal = load_calibration(top / f"calibration_{channel}.json")
        assert cal.artifact["method"] == method
        assert cal.artifact["fit_set"]["split"] == "val"
        assert cal.artifact["manifest"]["sha256"] == file_sha256(env["split"])
        config = _json(dirs[channel] / "config.json")
        assert config["mode"] == "calibrated-fit-in-run"
        assert config["calibration_sha256"] == file_sha256(top / f"calibration_{channel}.json")
    n_val = cal.artifact["fit_set"]["n"]
    assert 0 < n_val <= len(val_ids)


def test_fit_in_run_requires_a_val_manifest(env, tmp_path, capsys):
    assert suite.main(_args(env, tmp_path / "runs", "--mode", "calibrated-fit-in-run")) != 0
    assert "--val-manifest" in capsys.readouterr().err


def test_method_override_is_recorded(env, tmp_path):
    runs = tmp_path / "runs"
    code = suite.main(_args(env, runs, "--calibrate", "--val-manifest", str(env["val"]), "--method-b", "isotonic"))
    assert code == 0
    top, _ = _channel_dirs(runs)
    assert load_calibration(top / "calibration_channel_b.json").artifact["method"] == "isotonic"


# --- BS3: run directory -----------------------------------------------------------------------


def test_run_dir_is_complete_and_carries_the_manifest_hash(env, tmp_path):
    runs = tmp_path / "runs"
    assert suite.main(_args(env, runs, "--calibrate", "--val-manifest", str(env["val"]))) == 0
    top, dirs = _channel_dirs(runs)
    sha = file_sha256(env["split"])
    assert _json(top / "config.json")["manifest_sha256"] == sha
    assert set(dirs) == {*CHANNELS, "fused"}
    for channel, path in dirs.items():
        for name in RUN_FILES:
            assert (path / name).is_file(), f"{channel}: {name}"
        config = _json(path / "config.json")
        assert config["split"] == "test" and config["manifest_sha256"] == sha
        assert _json(path / "metrics.json")["split"] == "test"
        assert sha in (path / "report.md").read_text(encoding="utf-8")
    summary = _json(top / "summary.json")
    assert summary["manifest_sha256"] == sha and summary["mode"] == "calibrated-fit-in-run"


# --- scores -----------------------------------------------------------------------------------


def test_channel_a_score_is_raw_cosine():
    assert suite.cosine([1, 0], [-1, 0]) == pytest.approx(-1)
    assert suite.cosine([1, 2], [2, 4]) == pytest.approx(1)
    assert suite.cosine([0, 0], [1, 0]) == 0


def test_fused_decision_is_or_of_channel_decisions():
    score, decision = suite.fuse(
        np.array([0.2, 0.7, 0.1, 0.9]), np.array([0.5, 0.1, 0.2, 0.8]), 0.6, 0.4
    )
    assert decision.tolist() == [True, True, False, True]
    assert score.tolist() == [0.5, 0.7, 0.2, 0.9]


# --- fused metrics on the OR decision (R3-001, R2 alignment) -----------------------------------


class _IdentityCalibration:
    """Stand-in for a `LoadedCalibration` whose calibrated score is the raw score."""

    def __init__(self, channel, threshold, path: Path):
        path.write_text("{}\n", encoding="utf-8")
        self.path, self.sha256 = path, file_sha256(path)
        self.artifact = {
            "channel": channel, "primary": "fpr_0.05",
            "thresholds": {"fpr_0.05": {
                "threshold": threshold, "target_fpr": 0.05, "low_support": False, "unachievable": False,
                "reason": None, "achieved_fpr": 0.0, "tpr": 1.0, "n_neg": 50, "n_pos": 50, "min_negatives": 20,
            }},
        }

    def apply(self, raw):
        return np.asarray(raw, dtype=np.float64)


def _row(i, sim, ai_prob, copy, ai):
    return {
        "id": f"A2016_Z1_Z1/x/s{i}.c", "split_id": f"s{i}", "split": "test", "problem_id": "A2016_Z1_Z1",
        "lang": "c", "model": None, "dup_group": None, "cluster_id": None,
        "label_copy": copy, "label_ai": ai, "sim": sim, "ai_prob": ai_prob,
    }


# calibrated A, calibrated B, label_copy, label_ai; t_A = t_B = 0.5
HAND_BUILT = [
    _row(0, 0.6, 0.1, True, False),    # A fires          -> TP
    _row(1, 0.2, 0.7, False, True),    # B fires          -> TP
    _row(2, 0.7, 0.2, False, False),   # A fires          -> FP
    _row(3, 0.1, 0.3, False, False),   # neither          -> TN
    _row(4, 0.3, 0.4, True, False),    # neither          -> FN
    _row(5, 0.2, 0.1, False, False),   # neither          -> TN
    _row(6, None, 0.9, False, True),   # no reference: channel B only, never fused
]


def _hand_built_run(env, tmp_path, monkeypatch):
    async def fake_scores(golden, root, engine):
        return [dict(r) for r in HAND_BUILT]

    cals = {
        "channel_a": _IdentityCalibration("channel_a", 0.5, tmp_path / "cal_a.json"),
        "channel_b": _IdentityCalibration("channel_b", 0.5, tmp_path / "cal_b.json"),
    }
    monkeypatch.setattr(suite, "score_manifest", fake_scores)
    monkeypatch.setattr(suite, "resolve_calibrations", lambda paths, sha: cals)
    golden = _json(env["test"])
    runs = tmp_path / "runs"
    suite.run_suite(
        golden=golden, root=Path(golden["root"]), split_manifest_path=env["split"],
        engine=None, engine_name="stub", mode="calibrated-frozen", seed=1, n_boot=20, runs_root=runs,
    )
    return _channel_dirs(runs)


def test_fused_threshold_metrics_are_the_or_decision_confusion(env, tmp_path, monkeypatch):
    fused = [r for r in HAND_BUILT if r["sim"] is not None]
    a = np.array([r["sim"] for r in fused])
    b = np.array([r["ai_prob"] for r in fused])
    y = np.array([r["label_copy"] or r["label_ai"] for r in fused])
    decision = (a >= 0.5) | (b >= 0.5)
    assert ((np.maximum(a, b) >= 1) != decision).any(), "precondition: max >= 1 differs from the OR decision"

    _, dirs = _hand_built_run(env, tmp_path, monkeypatch)
    point = _json(dirs["fused"] / "metrics.json")["operating_points"]["or_fpr_0.05"]
    obs = point["observed"]
    tp, fp = int((decision & y).sum()), int((decision & ~y).sum())
    fn, tn = int((~decision & y).sum()), int((~decision & ~y).sum())
    assert (obs["tp"], obs["fp"], obs["fn"], obs["tn"]) == (tp, fp, fn, tn) == (2, 1, 1, 2)
    assert obs["precision"]["value"] == pytest.approx(tp / (tp + fp))
    assert obs["recall"]["value"] == pytest.approx(tp / (tp + fn))
    assert obs["fpr"]["value"] == pytest.approx(fp / (fp + tn))
    assert point["channel_thresholds"] == {"channel_a": 0.5, "channel_b": 0.5}


def test_fused_rows_are_the_rows_scored_by_both_channels(env, tmp_path, monkeypatch):
    _, dirs = _hand_built_run(env, tmp_path, monkeypatch)
    config = _json(dirs["fused"] / "config.json")["config"]
    assert config["dropped_without_reference"] == 1
    assert _json(dirs["fused"] / "metrics.json")["n"] == 6
    assert _json(dirs["channel_b"] / "metrics.json")["n"] == 7
    assert "OR" in config["operating_points"] and "max" in config["threshold_free_score"]


# --- run lifecycle (R4 orphan run dir / R3-003) -----------------------------------------------


STUB_ENGINE = type(suite.make_engine("stub"))


class _FailingEngine:
    """The stub engine, raising on the n-th AI probability (i.e. mid-scoring)."""

    def __init__(self, fail_at: int):
        self.inner, self.calls, self.fail_at = STUB_ENGINE(), 0, fail_at

    async def extract_semantic_embedding(self, code, lang):
        return await self.inner.extract_semantic_embedding(code, lang=lang)

    async def predict_synthetic_prob(self, code):
        self.calls += 1
        if self.calls >= self.fail_at:
            raise RuntimeError("engine crashed mid-scoring")
        return await self.inner.predict_synthetic_prob(code)


def _no_run_left(runs: Path):
    bench = runs / "benchmark"
    assert not bench.exists() or not any(bench.iterdir()), list(bench.iterdir())
    assert not list(runs.rglob("config.json")), "a run directory survived the failure"
    assert not list(runs.rglob("calibration_*.json"))


def test_failure_mid_scoring_leaves_no_run_dir(env, tmp_path, monkeypatch):
    n_val = sum(1 for s in _json(env["val"])["samples"] if s["role"] == "submission")
    monkeypatch.setattr(suite, "make_engine", lambda name: _FailingEngine(n_val + 2))  # in the test set
    runs = tmp_path / "runs"
    with pytest.raises(RuntimeError, match="mid-scoring"):
        suite.main(_args(env, runs, "--calibrate", "--val-manifest", str(env["val"])))
    _no_run_left(runs)


def test_failure_while_fitting_calibration_leaves_no_run_dir(env, tmp_path, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("fit failed")

    monkeypatch.setattr(suite, "build_calibration", boom)
    runs = tmp_path / "runs"
    with pytest.raises(RuntimeError, match="fit failed"):
        suite.main(_args(env, runs, "--calibrate", "--val-manifest", str(env["val"])))
    _no_run_left(runs)


def test_published_run_records_final_paths_and_complete_status(env, tmp_path):
    runs = tmp_path / "runs"
    assert suite.main(_args(env, runs, "--calibrate", "--val-manifest", str(env["val"]))) == 0
    top, dirs = _channel_dirs(runs)
    assert not (runs / suite.STAGING).exists()
    summary = _json(top / "summary.json")
    assert summary["status"] == "complete" and summary["run_dir"] == top.as_posix()
    assert summary["channels"]["fused"]["run_dir"] == dirs["fused"].as_posix()
    config_a = _json(dirs["channel_a"] / "config.json")
    assert config_a["calibration_path"] == (top / "calibration_channel_a.json").as_posix()
    assert config_a["calibration_sha256"] == file_sha256(top / "calibration_channel_a.json")
    fused_cal = _json(dirs["fused"] / "config.json")["config"]["calibrations"]["channel_b"]
    assert fused_cal["path"] == (top / "calibration_channel_b.json").as_posix()


STAMP = "20260102-030405"


class _FixedNow(datetime):
    """Every run started in the same second, so they all want the same `<ts>` directory."""

    @classmethod
    def now(cls, tz=None):
        return datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def _assert_published_at(top: Path):
    """The run at `top` records `top` (never the staging dir) as its location and run id."""
    summary = _json(top / "summary.json")
    assert summary["status"] == "complete" and summary["run_dir"] == top.as_posix()
    assert _json(top / "config.json")["run_id"] == f"{top.parent.name}/{top.name}"
    for channel in CHANNELS:
        run_dir = Path(summary["channels"][channel]["run_dir"])
        assert run_dir.parent.parent == top and run_dir.is_dir()
    for path in top.rglob("*"):
        if path.suffix in (".json", ".md"):
            assert suite.STAGING not in path.read_text(encoding="utf-8"), path


def test_runs_with_the_same_timestamp_publish_to_distinct_dirs(env, tmp_path, monkeypatch):
    monkeypatch.setattr(suite, "datetime", _FixedNow)
    runs = tmp_path / "runs"
    for _ in range(2):
        assert suite.main(_args(env, runs, "--mode", "uncalibrated")) == 0
    tops = sorted((runs / "benchmark").iterdir())
    assert [t.name for t in tops] == [STAMP, f"{STAMP}-1"]
    for top in tops:
        _assert_published_at(top)


def test_publish_retries_when_a_concurrent_run_takes_the_name(env, tmp_path, monkeypatch):
    """Another run publishes `<ts>` between our existence check and our rename."""
    monkeypatch.setattr(suite, "datetime", _FixedNow)
    runs = tmp_path / "runs"
    bench, real_rename, racer = runs / "benchmark", Path.rename, []

    def racing_rename(self, target):
        target = Path(target)
        if target.parent == bench and not racer:
            target.mkdir()
            (target / "summary.json").write_text("{}\n", encoding="utf-8")  # the racer's run
            racer.append(target)
        return real_rename(self, target)

    monkeypatch.setattr(Path, "rename", racing_rename)
    assert suite.main(_args(env, runs, "--mode", "uncalibrated")) == 0
    assert sorted(t.name for t in bench.iterdir()) == [STAMP, f"{STAMP}-1"]
    assert _json(bench / STAMP / "summary.json") == {}, "the racer's run is untouched"
    _assert_published_at(bench / f"{STAMP}-1")
    assert not (runs / suite.STAGING).exists()


@pytest.mark.parametrize("error", [PermissionError(13, "denied"), FileExistsError(17, "taken")],
                         ids=["permission", "always_taken"])
def test_publish_failure_keeps_the_completed_staged_run(env, tmp_path, monkeypatch, error):
    runs = tmp_path / "runs"
    bench, real_rename = runs / "benchmark", Path.rename

    def failing_rename(self, target):
        if Path(target).parent == bench:
            raise error
        return real_rename(self, target)

    monkeypatch.setattr(Path, "rename", failing_rename)
    with pytest.raises(suite.PublishError) as info:
        suite.main(_args(env, runs, "--mode", "uncalibrated"))
    staged = sorted((runs / suite.STAGING).rglob("summary.json"))
    assert len(staged) == 1, "the completed run must survive a failed publish"
    top = staged[0].parent
    assert top.as_posix() in str(info.value)
    # the kept run records its staged location, not a destination it never reached
    summary = _json(staged[0])
    assert summary["status"] == "complete" and summary["run_dir"] == top.as_posix()
    assert _json(top / "config.json")["run_id"] == f"benchmark/{top.name}"
    assert not bench.exists() or not any(bench.iterdir())


# --- CLI errors (R3-002) and config keys (R2) -------------------------------------------------


def _bad_golden(env, tmp_path, **changes):
    golden = _json(env["test"])
    golden.update(changes)
    path = tmp_path / "golden.json"
    path.write_text(json.dumps(golden), encoding="utf-8")
    return path


@pytest.mark.parametrize("case", ["val_as_test", "no_source_sha", "hash_mismatch", "not_json", "split_id_leak"])
def test_cli_turns_input_errors_into_exit_2(env, tmp_path, capsys, case):
    if case == "val_as_test":
        manifest = env["val"]
    elif case == "no_source_sha":
        manifest = _bad_golden(env, tmp_path, source_manifest_sha256=None)
    elif case == "not_json":
        manifest = tmp_path / "golden.json"
        manifest.write_text("{not json", encoding="utf-8")
    elif case == "split_id_leak":
        golden = _json(env["test"])
        golden["samples"][0]["split_id"] = _json(env["val"])["samples"][0]["split_id"]
        manifest = _bad_golden(env, tmp_path, samples=golden["samples"])
    else:
        manifest = _bad_golden(env, tmp_path, source_manifest_sha256="e" * 64)
    runs = tmp_path / "runs"
    args = _args(env, runs, "--mode", "uncalibrated")
    args[args.index("--manifest") + 1] = str(manifest)
    assert suite.main(args) == 2
    err = capsys.readouterr().err
    assert err.startswith("ERROR: ") and "Traceback" not in err
    assert not (runs / "benchmark").exists()


def test_cli_turns_a_malformed_calibration_into_exit_2(env, tmp_path, capsys):
    (tmp_path / "calibration_channel_a.json").write_text("{not json", encoding="utf-8")
    (tmp_path / "calibration_channel_b.json").write_text("{not json", encoding="utf-8")
    runs = tmp_path / "runs"
    assert suite.main(_args(env, runs, "--mode", "calibrated-frozen", "--calibration-dir", str(tmp_path))) == 2
    err = capsys.readouterr().err
    assert err.startswith("ERROR: ") and "calibration_channel_a.json" in err
    assert not (runs / "benchmark").exists()


@pytest.mark.parametrize("target", ["score_manifest", "build_calibration", "compute_metrics"])
def test_internal_value_error_is_not_reported_as_an_input_error(env, tmp_path, monkeypatch, target):
    """A ValueError raised while scoring, fitting or computing metrics is a bug, not bad input:
    it must propagate with its traceback instead of becoming `ERROR:` + exit 2."""
    def boom(*args, **kwargs):
        raise ValueError(f"internal bug in {target}")

    monkeypatch.setattr(suite, target, boom)
    with pytest.raises(ValueError, match=f"internal bug in {target}"):
        suite.main(_args(env, tmp_path / "runs", "--calibrate", "--val-manifest", str(env["val"])))
    _no_run_left(tmp_path / "runs")


def test_default_split_manifest_is_the_gzip_manifest():
    assert suite.DEFAULT_MANIFEST.as_posix().endswith("data/splits/split_v1.json.gz")


def test_config_records_golden_and_split_manifest_paths(env, tmp_path):
    runs = tmp_path / "runs"
    assert suite.main(_args(env, runs, "--mode", "uncalibrated")) == 0
    top, _ = _channel_dirs(runs)
    config = _json(top / "config.json")["config"]
    assert config["golden_manifest"] == Path(env["test"]).as_posix()
    assert config["split_manifest"] == Path(env["split"]).as_posix()


# --- BS2: no threshold constants --------------------------------------------------------------

ALLOWED_FLOATS = (0.0, 1.0)


def _threshold_literals(source: str):
    """(line, value) of every float literal other than 0.0/1.0 anywhere in `source` (assignments,
    defaults, dict values, call arguments, comparisons; a leading minus is a separate node), plus
    every `float(<constant>)` call, which would smuggle a literal past the check."""
    found = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Constant) and type(node.value) is float and node.value not in ALLOWED_FLOATS:
            found.append((node.lineno, node.value))
        elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "float"
              and node.args and isinstance(node.args[0], ast.Constant)):
            found.append((node.lineno, f"float({node.args[0].value!r})"))
    return found


def test_threshold_literal_guard_catches_every_float_position():
    for bad in ("THRESHOLD_AI = 0.20", "f(threshold=0.5)", "def f(t: float = 0.85):\n    pass",
                "ok = s >= 0.7", "D = {'t': 0.3}", "x = -0.25", "y = 5e-2", "z = float('0.5')",
                "w = float(0)", "f(0.95)"):
        assert _threshold_literals(bad), bad
    for ok in ("x = 0.0", "y = -1.0", "z = a if d else 0.0", "DECISION_TRUE = 1", "s = 'fpr_0.05'",
               "t = f'{v:.3f}'", "u = float(a @ b / d)"):
        assert not _threshold_literals(ok), ok


def test_no_numeric_threshold_literal_in_the_suite():
    source = SUITE_PATH.read_text(encoding="utf-8")
    assert not _threshold_literals(source), "float literals other than 0.0/1.0 remain in the suite"
    for name in ("DEFAULT_THRESHOLDS_SEM", "THRESHOLD_AI", "threshold_ai", "settings",
                 "calibrate_semantic_similarity"):
        assert name not in source
