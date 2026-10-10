"""Legacy baseline (CT8): a legacy checkpoint scored through the facade on the split_v1 test views.

Uses the synthetic `eval_factory` corpus, a seeded random legacy-format checkpoint (no version
fields) and CPU only. Every output goes under a temporary runs root; the legacy `CharCNNConfig`
creates `models/char_cnn/{weights,logs}` relative to cwd, so runs execute from `tmp_path`.
"""

import csv
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from eval_factory import make_tree
from models.char_cnn.v2 import baseline as baseline_mod
from models.evaluation.manifest import load_manifest
from models.evaluation.splits import SplitConfig, build_split, write_manifest
from test_char_cnn_v2_inference import make_v1_checkpoint, make_v2_checkpoint

ROOT = Path(__file__).resolve().parent.parent
REAL_CHECKPOINT = ROOT / "models" / "char_cnn" / "best_model.pth"


def _sha(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


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
    return tree, path


@pytest.fixture(scope="module")
def baseline_run(corpus, tmp_path_factory):
    tree, manifest_path = corpus
    work = tmp_path_factory.mktemp("baseline")
    runs_root = work / "runs"
    real_before = _sha(REAL_CHECKPOINT)
    with pytest.MonkeyPatch.context() as mp:
        mp.chdir(work)
        checkpoint = make_v1_checkpoint(work / "legacy.pth", 12, {"whitespace_mode": "canonical", "seq_length": 512})
        sha_before = _sha(checkpoint)
        code = baseline_mod.main(
            [
                "--checkpoint", str(checkpoint),
                "--manifest", str(manifest_path),
                "--root", str(tree.repo_root),
                "--runs-root", str(runs_root),
                "--device", "cpu",
                "--n-boot", "20",
            ]
        )
    runs = list((runs_root / "char_cnn_legacy").iterdir()) if (runs_root / "char_cnn_legacy").exists() else []
    return {
        "code": code,
        "work": work,
        "runs_root": runs_root,
        "run_dir": runs[0] if len(runs) == 1 else None,
        "checkpoint": checkpoint,
        "sha_before": sha_before,
        "sha_after": _sha(checkpoint),
        "real_before": real_before,
        "real_after": _sha(REAL_CHECKPOINT),
    }


class TestBaselineRun:
    def test_exit_code_and_layout(self, baseline_run):
        assert baseline_run["code"] == 0
        run_dir = baseline_run["run_dir"]
        assert run_dir is not None and run_dir.parent.name == "char_cnn_legacy"
        assert [p.name for p in baseline_run["runs_root"].iterdir()] == ["char_cnn_legacy"]
        for name in ("config.json", "metrics.json", "report.md", "scores_test.csv", "test_all/metrics.json"):
            assert (run_dir / name).is_file(), name
        assert not (run_dir / "calibration.json").exists()  # never calibrated

    def test_checkpoint_is_read_only(self, baseline_run):
        assert baseline_run["sha_after"] == baseline_run["sha_before"]
        assert baseline_run["real_after"] == baseline_run["real_before"]
        cfg = _json(baseline_run["run_dir"] / "config.json")
        assert cfg["config"]["checkpoint_sha256_before"] == baseline_run["sha_before"]
        assert cfg["checkpoint_sha256_after"] == baseline_run["sha_before"]

    def test_config_is_labelled_contaminated_and_manual(self, baseline_run):
        cfg = _json(baseline_run["run_dir"] / "config.json")
        assert cfg["channel"] == "char_cnn_legacy" and cfg["mode"] == "legacy_contaminated"
        assert cfg["config"]["contaminated"] is True
        assert cfg["threshold_source"] == "manual" and cfg["thresholds"] == {"argmax_0.5": 0.5}
        assert cfg["calibration_path"] is None
        assert cfg["status"] == "complete"
        assert (cfg["config"]["arch_version"], cfg["config"]["preproc_version"]) == (1, 1)

    def test_headline_and_secondary_views(self, corpus, baseline_run):
        manifest = load_manifest(corpus[1])
        run_dir = baseline_run["run_dir"]
        headline, secondary = _json(run_dir / "metrics.json"), _json(run_dir / "test_all" / "metrics.json")
        assert headline["n"] == len(manifest.samples("test", representatives_only=True))
        assert secondary["n"] == len(manifest.samples("test"))
        assert headline["mode"] == "representatives" and secondary["mode"] == "all_files"
        for metrics in (headline, secondary):
            assert metrics["contaminated"] is True
            assert "overlap" in metrics["contamination_note"] and "preprocessing" in metrics["contamination_note"]
            assert any(w.startswith("contaminated") for w in metrics["warnings"])
            assert metrics["bootstrap"]["unit"] == "dup_group"
            assert metrics["threshold_free"]["roc_auc"]["n"] == metrics["n"]
            point = metrics["operating_points"]["argmax_0.5"]
            assert (point["threshold"], point["source"]) == (0.5, "manual")
            assert "observed" in point and "balanced" in point
            assert set(metrics["per_group"]) == {"lang", "course", "length_bucket"}
            assert {"model", "profile"} <= set(metrics["per_generator"])
            assert {"human", "ai", "total", "n"} <= set(metrics["n_abstained"]["test"])

    def test_scores_come_from_the_legacy_facade(self, corpus, baseline_run):
        from models.char_cnn.inference import CharCNNInference

        tree, _ = corpus
        with open(baseline_run["run_dir"] / "scores_test.csv", encoding="utf-8", newline="") as fh:
            rows = list(csv.DictReader(fh))
        assert list(rows[0]) == ["id", "y", "p_synthetic", "abstained", "representative"]
        with pytest.MonkeyPatch.context() as mp:
            mp.chdir(baseline_run["work"])
            engine = CharCNNInference(baseline_run["checkpoint"], device=torch.device("cpu"))
        for row in rows[:5]:
            raw = (tree.repo_root / row["id"]).read_bytes().decode("utf-8", errors="replace")
            result = engine.predict_text(raw)
            assert float(row["p_synthetic"]) == pytest.approx(result["prob_sintetico"], abs=1e-9)
            assert row["abstained"] == str(int(result["insufficient_length"]))

    def test_report_states_the_contamination(self, baseline_run):
        report = (baseline_run["run_dir"] / "report.md").read_text(encoding="utf-8")
        assert "## Legacy baseline (contaminated)" in report
        assert "not comparable" in report


class TestBaselineExitCodes:
    def test_exit_codes_and_defaults_come_from_the_shared_runs_module(self):
        from models.char_cnn.v2 import runs

        assert baseline_mod.REFUSED_EXIT is runs.REFUSED_EXIT
        assert baseline_mod.RUN_FAILED_EXIT is runs.RUN_FAILED_EXIT
        assert baseline_mod.build_parser().parse_args([]).n_boot == runs.DEFAULT_N_BOOT


class TestBaselineRefusals:
    def test_v2_checkpoint_is_refused_before_writing(self, corpus, tmp_path, monkeypatch, capsys):
        tree, manifest_path = corpus
        monkeypatch.chdir(tmp_path)
        checkpoint, _ = make_v2_checkpoint(tmp_path / "v2.pth")
        runs_root = tmp_path / "runs"
        code = baseline_mod.main(
            ["--checkpoint", str(checkpoint), "--manifest", str(manifest_path), "--root", str(tree.repo_root),
             "--runs-root", str(runs_root), "--device", "cpu", "--n-boot", "5"]
        )
        assert code == baseline_mod.REFUSED_EXIT
        assert "legacy" in capsys.readouterr().err
        assert not runs_root.exists()

    def test_checkpoint_change_during_the_run_fails_the_run(self, corpus, tmp_path, monkeypatch, capsys):
        tree, manifest_path = corpus
        monkeypatch.chdir(tmp_path)
        checkpoint = make_v1_checkpoint(tmp_path / "legacy.pth", 12, {"whitespace_mode": "canonical", "seq_length": 512})
        hashes = iter(["a" * 64, "b" * 64])
        monkeypatch.setattr(baseline_mod, "file_sha256", lambda path: next(hashes))
        runs_root = tmp_path / "runs"
        code = baseline_mod.main(
            ["--checkpoint", str(checkpoint), "--manifest", str(manifest_path), "--root", str(tree.repo_root),
             "--runs-root", str(runs_root), "--device", "cpu", "--n-boot", "5"]
        )
        assert code == baseline_mod.RUN_FAILED_EXIT
        assert capsys.readouterr().err.startswith("ERROR:")
        (run_dir,) = list((runs_root / "char_cnn_legacy").iterdir())
        cfg = _json(run_dir / "config.json")
        assert cfg["status"] == "failed" and "changed" in cfg["failure"]["reason"]
