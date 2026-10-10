"""Benchmark suite on the evaluation package: test-only samples, calibration modes, run dirs (BS1-BS5).

Everything runs on the synthetic `eval_factory` tree (split manifest -> golden test/val corpora ->
golden manifests) with the STUB engine: no real data, models or network. Stub numbers are NOT
evidence about the real models.
"""

import importlib.util
import json
import re
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
    with pytest.raises(ValueError) as info:
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
    with pytest.raises(ValueError, match=re.escape(leaked)):
        suite.require_split(golden["samples"], "test", env["split"], golden["source_manifest_sha256"])


def test_golden_manifest_without_source_hash_is_refused(env, tmp_path):
    golden = _json(env["test"])
    golden["source_manifest_sha256"] = None
    with pytest.raises(ValueError, match="source_manifest_sha256"):
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
        top = sorted((tmp_path / "runs" / "benchmark").glob("*"))
        frozen = sorted(p.name for t in top for p in t.glob("calibration_*.json"))
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


# --- BS2: no threshold constants --------------------------------------------------------------


def test_no_numeric_threshold_literal_in_the_suite():
    source = SUITE_PATH.read_text(encoding="utf-8")
    assert not re.findall(r"(?<![\w.:])\d*\.\d+", source), "float literals (threshold defaults) remain"
    for name in ("DEFAULT_THRESHOLDS_SEM", "THRESHOLD_AI", "threshold_ai", "settings",
                 "calibrate_semantic_similarity"):
        assert name not in source
