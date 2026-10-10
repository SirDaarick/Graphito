"""CharCNN v2 trainer: AUC selection, seeded end-to-end run, leak guard and determinism.

End-to-end runs use the synthetic `eval_factory` corpus in a temporary directory, a tiny model
(window 256, embedding 8, 4 filters per kernel, fc 16), 2 epochs and CPU only. Every run writes
under a temporary runs root, never under the repository.
"""

import csv
import hashlib
import json
import os
import sys
import types
from pathlib import Path

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from eval_factory import make_tree
from models.char_cnn.v2 import data as data_mod
from models.char_cnn.v2 import evaluate as eval_mod
from models.char_cnn.v2 import train as train_mod
from models.char_cnn.v2.config import CharCNNV2Config
from models.char_cnn.v2.data import EncodedSet
from models.char_cnn.v2.preprocess import preprocess_v2
from models.evaluation.manifest import Sample, load_manifest
from models.evaluation.splits import SplitConfig, build_split, write_manifest

ROOT = Path(__file__).resolve().parent.parent
REAL_CHECKPOINT = ROOT / "models" / "char_cnn" / "best_model.pth"

TINY = dict(
    embedding_dim=8,
    conv_kernel_sizes=(3, 5, 7, 9),
    conv_filters=(4, 4, 4, 4),
    fc_units=16,
    dropout=0.1,
    window=256,
    stride=128,
    max_windows=4,
)
HISTORY_COLUMNS = ["epoch", "train_loss", "val_roc_auc", "val_pr_auc", "lr", "n_epoch_samples", "seconds"]


def _sha256(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def _models_mtimes() -> dict:
    """mtime of every file under the repo's `models/` (bytecode caches excluded)."""
    out = {}
    for dirpath, dirnames, filenames in os.walk(ROOT / "models"):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for name in filenames:
            path = Path(dirpath) / name
            out[path] = path.stat().st_mtime_ns
    return out


@pytest.fixture(scope="module", autouse=True)
def restore_torch_determinism():
    """The trainer switches torch to deterministic kernels; restore the process state afterwards."""
    previous = (
        torch.are_deterministic_algorithms_enabled(),
        torch.is_deterministic_algorithms_warn_only_enabled(),
        torch.backends.cudnn.deterministic,
        torch.backends.cudnn.benchmark,
    )
    yield
    torch.use_deterministic_algorithms(previous[0], warn_only=previous[1])
    torch.backends.cudnn.deterministic, torch.backends.cudnn.benchmark = previous[2], previous[3]


@pytest.fixture(scope="module")
def corpus(tmp_path_factory):
    tree = make_tree(tmp_path_factory.mktemp("corpus"))
    config = SplitConfig(
        seed=7,
        repo_root=tree.repo_root,
        raw_root=tree.raw_root,
        ai_root=tree.ai_root,
        gt_static=tree.gt_static,
        gt_ambiguous=(tree.gt_dynamic,),
    )
    path = write_manifest(build_split(config), tree.repo_root / "data" / "splits" / "split_v1.json")
    model_config = tree.repo_root / "tiny_model.json"
    model_config.write_text(json.dumps(TINY), encoding="utf-8")
    return tree, path, model_config


def _argv(corpus, runs_root: Path, *extra: str) -> list:
    tree, manifest_path, model_config = corpus
    return [
        "--manifest", str(manifest_path),
        "--root", str(tree.repo_root),
        "--runs-root", str(runs_root),
        "--seed", "1",
        "--epochs", "2",
        "--batch-size", "8",
        "--device", "cpu",
        "--model-config", str(model_config),
        "--n-boot", "40",
        *extra,
    ]


def _single_run_dir(runs_root: Path) -> Path:
    assert [p.name for p in runs_root.iterdir()] == ["char_cnn"]
    runs = list((runs_root / "char_cnn").iterdir())
    assert len(runs) == 1 and runs[0].is_dir()
    return runs[0]


def _history(run_dir: Path) -> list:
    with open(run_dir / "history.csv", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


@pytest.fixture(scope="module")
def traced_run(corpus, tmp_path_factory):
    """One end-to-end run with spies on seeding, data loading, model building, collation and promote."""
    runs_root = tmp_path_factory.mktemp("runs")
    events, forward_calls, collated, windows, promote_calls = [], [], [], [], []
    real_before = _sha256(REAL_CHECKPOINT)
    mtimes_before = _models_mtimes()

    def seed_spy(seed, deterministic_torch=False):
        events.append(("seed", seed, deterministic_torch))
        return original["seed_everything"](seed, deterministic_torch=deterministic_torch)

    def load_views_spy(*args, **kwargs):
        events.append(("load_views",))
        return original["load_views"](*args, **kwargs)

    def build_model_spy(*args, **kwargs):
        events.append(("build_model",))
        model = original["build_model"](*args, **kwargs)
        model.register_forward_pre_hook(
            lambda module, inputs: forward_calls.append((module.training, inputs[0].detach().cpu().clone()))
        )
        return model

    def collate_spy(*args, **kwargs):
        out = original["collate"](*args, **kwargs)
        collated.append(out[0].clone())
        return out

    def epoch_batches_spy(*args, **kwargs):
        windows.append(kwargs.get("window"))
        return original["epoch_batches"](*args, **kwargs)

    promote = types.ModuleType("models.char_cnn.v2.promote")
    promote.main = lambda *a, **k: promote_calls.append((a, k))
    promote.promote = promote.main

    evaluate_calls, calibration_inputs, scored = [], [], []

    def evaluate_run_spy(ctx, *args, **kwargs):
        evaluate_calls.append(ctx.path)
        return original["evaluate_run"](ctx, *args, **kwargs)

    def build_calibration_spy(data, **kwargs):
        calibration_inputs.append((list(data.ids), list(data.entry_splits or ())))
        return original_eval["build_calibration"](data, **kwargs)

    def score_split_spy(model, encoded, device, batch_size, *, name):
        run_dir = evaluate_calls[-1]
        scored.append((name, list(encoded.ids), (run_dir / "calibration.json").exists()))
        return original_eval["score_split"](model, encoded, device, batch_size, name=name)

    original = {
        name: getattr(train_mod, name)
        for name in ("seed_everything", "load_views", "build_model", "collate", "epoch_batches", "evaluate_run")
    }
    original_eval = {name: getattr(eval_mod, name) for name in ("build_calibration", "score_split")}
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(train_mod, "seed_everything", seed_spy)
        mp.setattr(train_mod, "load_views", load_views_spy)
        mp.setattr(train_mod, "build_model", build_model_spy)
        mp.setattr(train_mod, "collate", collate_spy)
        mp.setattr(train_mod, "epoch_batches", epoch_batches_spy)
        mp.setattr(train_mod, "evaluate_run", evaluate_run_spy)
        mp.setattr(eval_mod, "build_calibration", build_calibration_spy)
        mp.setattr(eval_mod, "score_split", score_split_spy)
        mp.setitem(sys.modules, "models.char_cnn.v2.promote", promote)
        code = train_mod.main(_argv(corpus, runs_root))
    return {
        "evaluate_calls": evaluate_calls,
        "calibration_inputs": calibration_inputs,
        "scored": scored,
        "code": code,
        "runs_root": runs_root,
        "run_dir": _single_run_dir(runs_root),
        "events": events,
        "forward_calls": forward_calls,
        "collated": collated,
        "windows": windows,
        "promote_calls": promote_calls,
        "real_before": real_before,
        "real_after": _sha256(REAL_CHECKPOINT),
        "mtimes_before": mtimes_before,
        "mtimes_after": _models_mtimes(),
    }


# --- 5.1 selection -----------------------------------------------------------------------------


def _sample(sample_id: str, source: str, split: str) -> Sample:
    return Sample(
        id=sample_id, course="A2016", block="A/Z1", assignment="A/Z1/Z1", student=None, lang="c",
        source=source, model=None, profile=None, sha256="0", norm_hash="0", n_tokens=10,
        dup_group=None, dup_rep=None, cluster_id=None, gt_status=None, split=split,
        excluded=False, flags=(),
    )


def _encoded(split: str, n_ai: int, n_human: int) -> EncodedSet:
    rng = np.random.RandomState(0 if split == "train" else 1)
    samples = [_sample(f"{split}/ai{i}.c", "ai", split) for i in range(n_ai)]
    samples += [_sample(f"{split}/h{i}.c", "human", split) for i in range(n_human)]
    arrays = [rng.randint(2, 98, size=40 + 5 * i).astype(np.uint8) for i in range(len(samples))]
    return EncodedSet.build(samples, arrays)


def _fit_with_stub(tmp_path, monkeypatch, sequence, **option_overrides):
    stub = iter(sequence)
    monkeypatch.setattr(train_mod, "val_metrics", lambda *a, **k: next(stub))
    options = train_mod.TrainOptions(
        **{"epochs": len(sequence), "batch_size": 4, "early_stop": 100, "seed": 3, **option_overrides}
    )
    model = train_mod.build_model(CharCNNV2Config(**TINY), torch.device("cpu"), seed=3)
    return train_mod.fit(
        model, _encoded("train", 4, 6), _encoded("val", 3, 3), options, torch.device("cpu"), tmp_path
    )


class TestSelection:
    def test_selection_tuple_prefers_auc_then_pr_then_earlier_epoch(self):
        sel = train_mod.Selection()
        assert sel.update(0, 0.80, 0.7) is True
        assert sel.update(1, 0.90, 0.6) is True
        assert sel.update(2, 0.90, 0.8) is True
        assert sel.update(3, 0.90, 0.8) is False  # exact tie keeps the earlier epoch
        assert (sel.best_epoch, sel.best_roc_auc, sel.best_pr_auc, sel.stale) == (2, 0.90, 0.8, 1)

    def test_null_auc_is_never_selected(self):
        sel = train_mod.Selection()
        assert sel.update(0, None, None) is False
        assert sel.best_epoch is None
        assert sel.update(1, 0.55, None) is True
        assert sel.update(2, None, 0.99) is False
        assert sel.best_epoch == 1 and sel.stale == 1

    def test_fit_selects_epoch_2_from_stubbed_val_metrics(self, tmp_path, monkeypatch):
        result = _fit_with_stub(tmp_path, monkeypatch, [(0.80, 0.7), (0.90, 0.6), (0.90, 0.8)])
        assert result.best_epoch == 2
        ckpt = torch.load(tmp_path / "best.pth", weights_only=True)
        assert (ckpt["config"]["epoch"], ckpt["config"]["val_roc_auc"], ckpt["config"]["val_pr_auc"]) == (2, 0.90, 0.8)
        assert [int(r["epoch"]) for r in _history(tmp_path)] == [0, 1, 2]

    def test_fit_ties_keep_the_earlier_epoch(self, tmp_path, monkeypatch):
        assert _fit_with_stub(tmp_path, monkeypatch, [(0.9, 0.7), (0.9, 0.7)]).best_epoch == 0

    def test_fit_skips_null_auc_epochs(self, tmp_path, monkeypatch):
        result = _fit_with_stub(tmp_path, monkeypatch, [(None, None), (0.6, 0.5), (None, None)])
        assert result.best_epoch == 1

    def test_fit_without_any_defined_auc_raises_and_saves_nothing(self, tmp_path, monkeypatch):
        with pytest.raises(RuntimeError, match="ROC-AUC"):
            _fit_with_stub(tmp_path, monkeypatch, [(None, None), (None, None)])
        assert not (tmp_path / "best.pth").exists()

    def test_early_stop_counts_epochs_without_improvement(self, tmp_path, monkeypatch):
        result = _fit_with_stub(
            tmp_path, monkeypatch, [(0.9, 0.5), (0.8, 0.5), (0.85, 0.5), (0.95, 0.5)], early_stop=2
        )
        assert (result.best_epoch, result.epochs_run, result.stopped_early) == (0, 3, True)

    def test_scheduler_reduces_lr_on_val_auc_plateau(self, tmp_path, monkeypatch):
        result = _fit_with_stub(
            tmp_path, monkeypatch, [(0.9, 0.5), (0.8, 0.5), (0.8, 0.5)], lr_patience=0, lr_factor=0.5
        )
        lrs = [float(r["lr"]) for r in result.history]
        assert lrs == pytest.approx([1e-3, 1e-3, 5e-4])  # mode="max": a lower AUC is a plateau


# --- 5.2 end-to-end run --------------------------------------------------------------------------


class TestRun:
    def test_exit_code_and_run_layout(self, traced_run):
        assert traced_run["code"] == 0
        run_dir = traced_run["run_dir"]
        assert run_dir.parent == traced_run["runs_root"] / "char_cnn"
        for name in ("config.json", "best.pth", "history.csv", "leak_guard.json"):
            assert (run_dir / name).is_file(), name

    def test_seed_runs_before_data_and_model(self, traced_run):
        events = traced_run["events"]
        assert events[0] == ("seed", 1, True)
        names = [e[0] for e in events]
        assert names.index("seed") < names.index("load_views") < names.index("build_model")

    def test_no_forward_before_the_first_real_batch(self, traced_run):
        calls, collated = traced_run["forward_calls"], traced_run["collated"]
        assert calls and collated
        training, first_input = calls[0]
        assert training is True
        assert torch.equal(first_input, collated[0])

    def test_crops_use_the_run_config_window(self, traced_run):
        assert traced_run["windows"] == [TINY["window"]] * 2

    def test_config_json_records_provenance(self, corpus, traced_run):
        _, manifest_path, _ = corpus
        doc = json.loads((traced_run["run_dir"] / "config.json").read_text(encoding="utf-8"))
        assert doc["channel"] == "char_cnn" and doc["seed"] == 1
        assert doc["manifest_sha256"] == load_manifest(manifest_path).sha256
        assert "git_sha" in doc and "dirty" in doc
        cfg = doc["config"]
        assert (cfg["arch_version"], cfg["preproc_version"]) == (2, 2)
        assert cfg["alphabet"] == CharCNNV2Config().to_dict()["alphabet"]
        assert cfg["conv_kernel_sizes"] == list(TINY["conv_kernel_sizes"])
        assert cfg["conv_filters"] == list(TINY["conv_filters"])
        assert cfg["dropout"] == TINY["dropout"]
        hp = cfg["hyperparams"]
        assert (hp["epochs"], hp["lr"], hp["seed"], hp["batch_size"]) == (2, 1e-3, 1, 8)
        assert cfg["device"] == "cpu"
        assert doc["sampling"]["ratio"] == "1:1"
        assert doc["sampling"]["human_shortfall"] == 0
        assert doc["selection"]["epoch"] in (0, 1)
        assert doc["leak_guard"]["passed"] is True

    def test_best_checkpoint_is_weights_only_and_self_describing(self, corpus, traced_run):
        from models.char_cnn.v2.checkpoint import CHECKPOINT_FORMAT, load_v2_model

        _, manifest_path, _ = corpus
        ckpt = torch.load(traced_run["run_dir"] / "best.pth", weights_only=True)
        assert ckpt["format"] == CHECKPOINT_FORMAT
        config = ckpt["config"]
        assert CharCNNV2Config.from_dict(config) == CharCNNV2Config(**TINY)
        assert config["manifest_sha256"] == load_manifest(manifest_path).sha256
        assert config["seed"] == 1 and config["device"] == "cpu"
        assert config["run_id"] == f"char_cnn/{traced_run['run_dir'].name}"
        assert config["epoch"] in (0, 1) and 0.0 <= config["val_roc_auc"] <= 1.0
        assert config["hyperparams"]["epochs"] == 2
        load_v2_model(ckpt, "cpu")

    def test_history_has_one_row_per_epoch(self, traced_run):
        rows = _history(traced_run["run_dir"])
        assert list(rows[0]) == HISTORY_COLUMNS
        assert [int(r["epoch"]) for r in rows] == [0, 1]
        assert all(int(r["n_epoch_samples"]) > 0 for r in rows)

    def test_writes_only_under_the_runs_root_and_never_promotes(self, traced_run):
        assert traced_run["promote_calls"] == []
        assert traced_run["real_after"] == traced_run["real_before"]  # NF3 (None when absent)
        assert traced_run["mtimes_after"] == traced_run["mtimes_before"]
        _single_run_dir(traced_run["runs_root"])


# --- 5.3 leak guard ------------------------------------------------------------------------------


class TestLeakGuard:
    def test_clean_corpus_passes_with_zero_shares(self, traced_run):
        doc = json.loads((traced_run["run_dir"] / "leak_guard.json").read_text(encoding="utf-8"))
        assert doc["passed"] is True
        assert doc["shares"] and set(doc["shares"].values()) == {0.0}
        assert doc["n_texts"]["human"] > 0

    def test_leaking_preprocessing_aborts_before_any_checkpoint(self, corpus, tmp_path, monkeypatch):
        monkeypatch.setattr(data_mod, "preprocess_v2", lambda text: preprocess_v2(text) + "\nZadaca 4")
        runs_root = tmp_path / "runs"
        assert train_mod.main(_argv(corpus, runs_root)) == 2
        run_dir = _single_run_dir(runs_root)
        doc = json.loads((run_dir / "leak_guard.json").read_text(encoding="utf-8"))
        assert doc["passed"] is False
        assert doc["shares"]["course_marker"] == 1.0
        assert doc["offending_ids"]["course_marker"]
        assert not list(runs_root.rglob("*.pth"))
        assert not (run_dir / "history.csv").exists()
        config = json.loads((run_dir / "config.json").read_text(encoding="utf-8"))
        assert config["status"] == "failed" and config["failure"]["stage"] == "leak_guard"


# --- 6.1 / 6.3 evaluation ------------------------------------------------------------------------


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _csv(path: Path) -> list:
    with open(path, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


CT53_ARTIFACTS = (
    "config.json", "best.pth", "history.csv", "leak_guard.json", "calibration.json", "metrics.json",
    "report.md", "shortcuts.json", "scores_val.csv", "scores_test.csv", "test_all/metrics.json",
    "test_all/report.md",
)


class TestEvaluate:
    def test_main_invokes_evaluate_run_once(self, traced_run):
        assert traced_run["evaluate_calls"] == [traced_run["run_dir"]]

    def test_run_has_every_artifact(self, traced_run):
        run_dir = traced_run["run_dir"]
        for name in CT53_ARTIFACTS:
            assert (run_dir / name).is_file(), name
        report = (run_dir / "report.md").read_text(encoding="utf-8")
        for section in ("## Test view", "## Per generator", "## Abstention", "## Shortcut audit"):
            assert section in report, section

    def test_calibration_is_fitted_on_val_ids_only(self, corpus, traced_run):
        manifest = load_manifest(corpus[1])
        val_ids = {s.id for s in manifest.samples("val", representatives_only=True)}
        assert len(traced_run["calibration_inputs"]) == 1
        ids, splits = traced_run["calibration_inputs"][0]
        assert set(ids) == val_ids and set(splits) == {"val"}
        cal = _json(traced_run["run_dir"] / "calibration.json")
        assert cal["fit_set"]["split"] == "val" and cal["fit_set"]["n"] == len(val_ids)
        assert cal["method"] == "platt" and cal["channel"] == "char_cnn"

    def test_test_is_scored_once_after_calibration(self, corpus, traced_run):
        manifest = load_manifest(corpus[1])
        assert [name for name, _, _ in traced_run["scored"]] == ["val", "test"]
        (_, _, cal_before_val), (_, test_ids, cal_before_test) = traced_run["scored"]
        assert cal_before_val is False and cal_before_test is True
        assert set(test_ids) == {s.id for s in manifest.samples("test")}

    def test_headline_and_secondary_views(self, corpus, traced_run):
        manifest = load_manifest(corpus[1])
        run_dir = traced_run["run_dir"]
        headline, secondary = _json(run_dir / "metrics.json"), _json(run_dir / "test_all" / "metrics.json")
        n_reps = len(manifest.samples("test", representatives_only=True))
        n_all = len(manifest.samples("test"))
        assert n_reps < n_all
        assert (headline["n"], secondary["n"]) == (n_reps, n_all)
        assert headline["test_view"]["name"] == "test" and "representatives" in headline["test_view"]["label"]
        assert secondary["test_view"]["name"] == "test_all" and "all" in secondary["test_view"]["label"]
        assert headline["mode"] == "representatives" and secondary["mode"] == "all_files"
        assert "## Test view" in (run_dir / "test_all" / "report.md").read_text(encoding="utf-8")

    def test_ci_is_bootstrapped_by_dup_group(self, corpus, traced_run):
        manifest = load_manifest(corpus[1])
        secondary = _json(traced_run["run_dir"] / "test_all" / "metrics.json")
        units = {s.dup_group or s.id for s in manifest.samples("test")}
        assert secondary["bootstrap"]["unit"] == "dup_group"
        assert secondary["bootstrap"]["n_units"] == len(units) < secondary["n"]
        assert secondary["threshold_free"]["roc_auc"]["ci95"] is not None

    def test_operating_points_come_from_val_calibration(self, traced_run):
        run_dir = traced_run["run_dir"]
        headline = _json(run_dir / "metrics.json")
        sha = hashlib.sha256((run_dir / "calibration.json").read_bytes()).hexdigest()
        assert headline["operating_points"]
        assert {p["source"] for p in headline["operating_points"].values()} == {f"calibration:{sha}"}
        config = _json(run_dir / "config.json")
        assert config["calibration_sha256"] == sha
        assert config["threshold_source"] == f"calibration:{sha}"
        assert config["calibration_path"].endswith("calibration.json")

    def test_per_group_breakdowns(self, traced_run):
        per_group = _json(traced_run["run_dir"] / "metrics.json")["per_group"]
        assert set(per_group) == {"lang", "course", "length_bucket"}
        for name, table in per_group.items():
            for entry in table["roc_auc"].values():
                assert isinstance(entry["low_support"], bool), name
        buckets = per_group["length_bucket"]["roc_auc"]
        assert set(buckets) == {"<512", "512-1023", "1024-2047", "2048-4095", ">=4096"}
        assert buckets[">=4096"] == {"n": 0, "n_pos": 0, "value": None, "reason": "empty", "low_support": True}
        assert set(per_group["course"]["roc_auc"]) == {"A2016", "A2017", "B2016", "B2017"}

    def test_per_generator_compares_each_group_with_all_humans(self, corpus, traced_run):
        manifest = load_manifest(corpus[1])
        test = manifest.samples("test", representatives_only=True)
        n_human = sum(s.source == "human" for s in test)
        metrics = _json(traced_run["run_dir"] / "metrics.json")
        per_gen = metrics["per_generator"]
        assert set(per_gen) >= {"model", "profile"}
        for key in ("model", "profile"):
            for group, entry in per_gen[key].items():
                expected_pos = sum(s.source == "ai" and str(getattr(s, key)) == group for s in test)
                assert (entry["n_pos"], entry["n_neg"]) == (expected_pos, n_human), (key, group)
                assert entry["low_support"] is (entry["n_pos"] < 30)
                assert set(entry["recall"]) == set(metrics["operating_points"])
        assert {"kimi", "deepseek-chat"} <= set(per_gen["model"])

    def test_n_abstained_is_reported_per_split_and_class(self, traced_run):
        n_abstained = _json(traced_run["run_dir"] / "metrics.json")["n_abstained"]
        for split in ("val", "test", "test_all"):
            entry = n_abstained[split]
            assert {"human", "ai", "total"} <= set(entry)
            assert entry["total"] == entry["human"] + entry["ai"]

    def test_score_csvs(self, corpus, traced_run):
        manifest = load_manifest(corpus[1])
        run_dir = traced_run["run_dir"]
        val_rows = _csv(run_dir / "scores_val.csv")
        assert list(val_rows[0]) == ["id", "y", "raw", "calibrated"]
        assert [r["id"] for r in val_rows] == [s.id for s in manifest.samples("val", representatives_only=True)]
        test_rows = _csv(run_dir / "scores_test.csv")
        assert list(test_rows[0]) == ["id", "y", "raw", "calibrated", "representative"]
        assert {r["id"] for r in test_rows} == {s.id for s in manifest.samples("test")}
        reps = {s.id for s in manifest.samples("test", representatives_only=True)}
        assert {r["id"] for r in test_rows if r["representative"] == "1"} == reps
        assert all(0.0 <= float(r["calibrated"]) <= 1.0 for r in val_rows + test_rows)

    def test_shortcuts_cover_train_and_test_representatives(self, corpus, traced_run):
        manifest = load_manifest(corpus[1])
        doc = _json(traced_run["run_dir"] / "shortcuts.json")
        for split in ("train", "test"):
            reps = manifest.samples(split, representatives_only=True)
            assert doc["sets"][split]["human"]["n"] == sum(s.source == "human" for s in reps)
            assert doc["sets"][split]["ai"]["n"] == sum(s.source == "ai" for s in reps)


class TestPerGroupSupport:
    def test_small_group_is_low_support_and_absent_group_is_empty(self):
        from models.evaluation.report import compute_metrics

        y = np.array([0, 1] * 35 + [0, 1])
        s = np.linspace(0.0, 1.0, y.size)
        groups = np.array(["big"] * 70 + ["tiny"] * 2, dtype=object)
        metrics = compute_metrics(
            y, s, channel="char_cnn", split="test", mode="representatives", seed=0,
            groups={"g": groups}, n_boot=10,
        )
        table = eval_mod.complete_per_group(metrics["per_group"], {"g": ["big", "tiny", "absent"]})["g"]
        for metric in ("roc_auc", "pr_auc"):
            assert table[metric]["big"]["low_support"] is False
            assert table[metric]["tiny"]["n"] == 2 and table[metric]["tiny"]["low_support"] is True
            assert table[metric]["absent"] == {
                "n": 0, "n_pos": 0, "value": None, "reason": "empty", "low_support": True
            }


# --- 5.4 determinism -----------------------------------------------------------------------------


class TestDeterminism:
    def test_two_cpu_runs_are_identical(self, corpus, traced_run, tmp_path):
        runs_root = tmp_path / "runs"
        assert train_mod.main(_argv(corpus, runs_root)) == 0
        first, second = traced_run["run_dir"], _single_run_dir(runs_root)

        def strip_seconds(rows):
            return [{k: v for k, v in row.items() if k != "seconds"} for row in rows]

        assert strip_seconds(_history(first)) == strip_seconds(_history(second))
        a = torch.load(first / "best.pth", weights_only=True)
        b = torch.load(second / "best.pth", weights_only=True)
        assert a["config"]["epoch"] == b["config"]["epoch"]
        assert a["model_state_dict"].keys() == b["model_state_dict"].keys()
        for key in a["model_state_dict"]:
            assert torch.equal(a["model_state_dict"][key], b["model_state_dict"][key]), key
        for name in ("metrics.json", "test_all/metrics.json", "calibration.json", "shortcuts.json"):
            assert _json(first / name) == _json(second / name), name

    def test_real_checkpoint_is_untouched(self, traced_run):
        if traced_run["real_before"] is None:
            pytest.skip("models/char_cnn/best_model.pth is absent")
        assert traced_run["real_after"] == traced_run["real_before"]


# --- PR3 review follow-ups: option validation ----------------------------------------------------


class TestOptionValidation:
    @pytest.mark.parametrize(
        "field, value",
        [
            ("epochs", 0), ("early_stop", 0), ("lr", 0.0), ("lr", -1e-3), ("lr", float("nan")),
            ("batch_size", 0), ("eval_batch_size", 0), ("n_boot", 0), ("limit_per_class", 0),
            ("lr_patience", -1), ("lr_factor", 0.0), ("lr_factor", 1.0), ("weight_decay", -1e-4),
        ],
    )
    def test_invalid_options_raise_value_error_naming_the_field(self, field, value):
        with pytest.raises(ValueError, match=field):
            train_mod.TrainOptions(**{field: value})

    def test_defaults_and_boundaries_are_valid(self):
        train_mod.TrainOptions()
        train_mod.TrainOptions(
            epochs=1, early_stop=1, lr_patience=0, lr_factor=0.99, limit_per_class=1, n_boot=1, weight_decay=0.0
        )

    @pytest.mark.parametrize(
        "flag, value",
        [
            ("--epochs", "0"), ("--early-stop", "0"), ("--lr", "0"), ("--batch-size", "0"),
            ("--eval-batch-size", "0"), ("--n-boot", "0"), ("--limit-per-class", "0"),
            ("--lr-patience", "-1"), ("--lr-factor", "1"),
        ],
    )
    def test_cli_rejects_invalid_numbers_before_writing(self, corpus, tmp_path, capsys, flag, value):
        runs_root = tmp_path / "runs"
        with pytest.raises(SystemExit) as exc:
            train_mod.main(_argv(corpus, runs_root, flag, value))
        assert exc.value.code == 2
        err = capsys.readouterr().err
        assert "error:" in err and flag in err
        assert not runs_root.exists()


# --- PR3 review follow-ups: run status and failure exit code -------------------------------------


class TestRunStatus:
    def test_successful_run_is_marked_complete(self, traced_run):
        doc = _json(traced_run["run_dir"] / "config.json")
        assert doc["status"] == "complete"
        assert doc.get("failure") is None

    def test_no_defined_val_auc_exits_3_and_marks_the_run_failed(self, corpus, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(train_mod, "val_metrics", lambda *a, **k: (None, None))
        runs_root = tmp_path / "runs"
        assert train_mod.main(_argv(corpus, runs_root)) == train_mod.RUN_FAILED_EXIT == 3
        err = capsys.readouterr().err
        assert err.startswith("ERROR:") and "ROC-AUC" in err
        run_dir = _single_run_dir(runs_root)
        doc = _json(run_dir / "config.json")
        assert doc["status"] == "failed"
        assert doc["failure"]["stage"] == "fit" and "ROC-AUC" in doc["failure"]["reason"]
        assert not (run_dir / "best.pth").exists() and not (run_dir / "metrics.json").exists()

    def test_evaluation_failure_exits_3_and_marks_the_run_failed(self, corpus, tmp_path, monkeypatch, capsys):
        def boom(*args, **kwargs):
            raise ValueError("calibration exploded")

        monkeypatch.setattr(train_mod, "evaluate_run", boom)
        runs_root = tmp_path / "runs"
        assert train_mod.main(_argv(corpus, runs_root)) == 3
        assert capsys.readouterr().err.startswith("ERROR:")
        run_dir = _single_run_dir(runs_root)
        doc = _json(run_dir / "config.json")
        assert doc["status"] == "failed" and doc["failure"]["stage"] == "evaluate"
        assert "calibration exploded" in doc["failure"]["reason"]
        assert (run_dir / "best.pth").is_file()

    def test_single_class_val_fails_cleanly_before_training(self, corpus, tmp_path, monkeypatch, capsys):
        def humans_only_val(*args, **kwargs):
            views = original(*args, **kwargs)
            val = views["val"]
            keep = [i for i, label in enumerate(val.y.tolist()) if label == 0]
            views["val"] = EncodedSet.build([val.samples[i] for i in keep], [val.arrays[i] for i in keep])
            return views

        original = train_mod.load_views
        monkeypatch.setattr(train_mod, "load_views", humans_only_val)
        runs_root = tmp_path / "runs"
        assert train_mod.main(_argv(corpus, runs_root)) == 3
        assert "val" in capsys.readouterr().err
        run_dir = _single_run_dir(runs_root)
        doc = _json(run_dir / "config.json")
        assert doc["status"] == "failed" and doc["failure"]["stage"] == "load_data"
        assert not (run_dir / "best.pth").exists()

    @pytest.mark.parametrize("limit", [1, 2])
    def test_limit_per_class_runs_with_both_classes_per_view(self, corpus, tmp_path, limit):
        runs_root = tmp_path / "runs"
        assert train_mod.main(_argv(corpus, runs_root, "--limit-per-class", str(limit))) == 0
        doc = _json(_single_run_dir(runs_root) / "config.json")
        assert doc["status"] == "complete"
        for name, entry in doc["data_summary"].items():
            assert entry["n_ai"] <= limit and entry["n_human"] <= limit, name
        assert doc["config"]["hyperparams"]["limit_per_class"] == limit


# --- PR3 review follow-ups: re-evaluating an existing run ----------------------------------------


EVAL_OUTPUTS = (
    "calibration.json", "metrics.json", "report.md", "shortcuts.json", "scores_val.csv", "scores_test.csv",
)


def _copy_run(traced_run, tmp_path: Path, *, strip_outputs: bool) -> Path:
    import shutil

    run_dir = tmp_path / "run"
    shutil.copytree(traced_run["run_dir"], run_dir)
    if strip_outputs:
        for name in EVAL_OUTPUTS:
            (run_dir / name).unlink()
        shutil.rmtree(run_dir / "test_all")
        for name in ("roc.csv", "pr.csv", "reliability.csv"):
            (run_dir / name).unlink(missing_ok=True)
    return run_dir


class TestReevaluate:
    def test_rebuilds_calibration_and_metrics_from_best_pth(self, traced_run, tmp_path):
        run_dir = _copy_run(traced_run, tmp_path, strip_outputs=True)
        assert eval_mod.main(["--run-dir", str(run_dir), "--device", "cpu"]) == 0
        for name in CT53_ARTIFACTS:
            assert (run_dir / name).is_file(), name
        original = traced_run["run_dir"]
        for name in ("metrics.json", "test_all/metrics.json", "calibration.json", "shortcuts.json"):
            assert _json(run_dir / name) == _json(original / name), name
        doc = _json(run_dir / "config.json")
        assert doc["status"] == "complete"
        assert doc["calibration_sha256"] == hashlib.sha256((run_dir / "calibration.json").read_bytes()).hexdigest()

    def test_refuses_existing_outputs_without_force(self, traced_run, tmp_path, capsys):
        run_dir = _copy_run(traced_run, tmp_path, strip_outputs=False)
        before = {name: (run_dir / name).read_bytes() for name in ("calibration.json", "metrics.json", "config.json")}
        assert eval_mod.main(["--run-dir", str(run_dir), "--device", "cpu"]) == eval_mod.REFUSED_EXIT == 1
        assert "--force" in capsys.readouterr().err
        assert {name: (run_dir / name).read_bytes() for name in before} == before

    def test_force_recomputes_existing_outputs(self, traced_run, tmp_path):
        run_dir = _copy_run(traced_run, tmp_path, strip_outputs=False)
        assert eval_mod.main(["--run-dir", str(run_dir), "--device", "cpu", "--force"]) == 0
        assert _json(run_dir / "metrics.json") == _json(traced_run["run_dir"] / "metrics.json")

    def test_refuses_a_run_without_checkpoint(self, traced_run, tmp_path, capsys):
        run_dir = _copy_run(traced_run, tmp_path, strip_outputs=True)
        (run_dir / "best.pth").unlink()
        assert eval_mod.main(["--run-dir", str(run_dir), "--device", "cpu"]) == 1
        assert "best.pth" in capsys.readouterr().err


# --- PR3 review follow-ups: shared constants and helpers -----------------------------------------


class TestSharedHelpers:
    def test_char_index_matches_encode(self):
        from models.char_cnn.v2.config import char_index
        from models.char_cnn.v2.preprocess import encode

        for ch in (" ", "\n", "a", "~", "{"):
            assert char_index(ch) == int(encode(ch)[0]), repr(ch)

    def test_empty_after_normalize_is_counted_with_unk(self):
        from models.char_cnn.v2.config import UNK_IDX
        from models.char_cnn.v2.data import data_summary

        samples = [_sample("x/a.c", "ai", "val"), _sample("x/b.c", "human", "val")]
        arrays = [np.array([UNK_IDX], dtype=np.uint8), np.array([UNK_IDX, 40], dtype=np.uint8)]
        summary = data_summary({"val": EncodedSet.build(samples, arrays)})
        assert summary["val"] == {"n": 2, "n_ai": 1, "n_human": 1, "n_empty_after_normalize": 1}

    def test_group_labels_follow_group_keys(self):
        encoded = _encoded("test", 2, 2)
        labels = eval_mod.group_labels(encoded)
        assert tuple(labels) == eval_mod.GROUP_KEYS
        assert all(len(values) == len(encoded) for values in labels.values())

    def test_one_json_writer_is_shared(self):
        assert not hasattr(train_mod, "_write_json") and not hasattr(eval_mod, "_write_json")
        assert train_mod.write_json is eval_mod.write_json


class TestPerGeneratorNoneGroup:
    def test_ai_files_without_model_or_profile_form_the_none_group(self):
        from dataclasses import replace

        samples = [
            replace(_sample("t/k.c", "ai", "test"), model="kimi", profile="aplicado"),
            _sample("t/u1.c", "ai", "test"),
            _sample("t/u2.c", "ai", "test"),
            _sample("t/h1.c", "human", "test"),
            _sample("t/h2.c", "human", "test"),
        ]
        y = np.array([1, 1, 1, 0, 0])
        scores = np.array([0.9, 0.8, 0.15, 0.2, 0.1])
        points = {"fpr_0.05": {"threshold": 0.5}}
        out = eval_mod.per_generator(samples, y, scores, points, {"model": ["kimi"], "profile": ["aplicado"]})
        for key, known in (("model", "kimi"), ("profile", "aplicado")):
            none = out[key]["<none>"]
            assert (none["n_pos"], none["n_neg"]) == (2, 2), key
            assert none["roc_auc"] == pytest.approx(0.75)
            assert none["recall"]["fpr_0.05"] == pytest.approx(0.5)
            assert none["low_support"] is True
            assert out[key][known]["n_pos"] == 1
