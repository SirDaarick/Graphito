"""`scripts/build_deploy_artifacts.py` on a synthetic corpus and fake runs (spec DA1.2, DA2.1, DA2.2).

Nothing here reads real weights, the real corpus or `runs/`: the split manifest is built from
`eval_factory`, the CharCNN run holds fake checkpoint bytes and a calibration fitted on synthetic
scores, and the GraphCodeBERT run holds only the JSON files the script reads.
"""

import hashlib
import importlib.util
import json
import sys
from pathlib import Path, PurePosixPath

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from eval_factory import STUDENT_BASE, disguise, make_tree  # noqa: E402
from models.evaluation.calibration import ScoredSet, build_calibration, load_calibration, save_calibration  # noqa: E402
from models.evaluation.manifest import load_manifest  # noqa: E402
from models.evaluation.splits import SplitConfig, build_split, write_manifest  # noqa: E402
from models.graphcodebert.v2.pairs import EvalPairs  # noqa: E402

_spec = importlib.util.spec_from_file_location("build_deploy_artifacts", ROOT / "scripts" / "build_deploy_artifacts.py")
bda = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bda)

FAKE_CHECKPOINT = b"fake-charcnn-v2-checkpoint\x00\x01\x02"
LABELLED_COURSES = ("A2016", "A2017", "B2016")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _plant_positives(tree, n_blocks: int) -> None:
    """Make every ground-truth pair (student base+1, base+2) a disguised copy, so val positives
    get a high Jaccard and `fpr_0.05` is achievable after isotonic calibration."""
    for course in LABELLED_COURSES:
        lang = "c" if course.startswith("A") else "cpp"
        base = STUDENT_BASE[course]
        for z in range(1, n_blocks + 1):
            folder = tree.raw_root / course / f"Z{z}" / "Z1"
            src = folder / f"student{base + 1}.{lang}"
            dst = folder / f"student{base + 2}.{lang}"
            dst.write_bytes(disguise(src.read_text(encoding="utf-8")).encode("utf-8"))


@pytest.fixture(scope="module")
def corpus(tmp_path_factory):
    base = tmp_path_factory.mktemp("deploy_corpus")
    tree = make_tree(base / "repo", planted=False)
    _plant_positives(tree, 6)
    config = SplitConfig(
        seed=7, repo_root=tree.repo_root, raw_root=tree.raw_root, ai_root=tree.ai_root,
        gt_static=tree.gt_static, gt_ambiguous=(tree.gt_dynamic,),
    )
    manifest_path = write_manifest(build_split(config), base / "split.json")
    return tree, manifest_path, load_manifest(manifest_path)


def _charcnn_run(path: Path, manifest_sha256: str, *, tamper_best_sha: bool = False) -> Path:
    path.mkdir(parents=True)
    (path / "best.pth").write_bytes(FAKE_CHECKPOINT)
    rng = np.random.default_rng(0)
    y = np.r_[np.zeros(400, dtype=int), np.ones(60, dtype=int)]
    scores = np.r_[rng.uniform(0.0, 0.5, 400), rng.uniform(0.6, 1.0, 60)]
    data = ScoredSet([f"f{i}" for i in range(y.size)], scores, y, "val", manifest_sha256=manifest_sha256)
    artifact, _ = build_calibration(data, channel="char_cnn", score_name="p_synthetic_raw", seed=42, method="platt")
    cal_sha = save_calibration(artifact, path / "calibration.json")
    config = {
        "schema": "graphito.run_config/v1",
        "run_id": f"char_cnn/{path.name}",
        "status": "complete",
        "best_sha256": "0" * 64 if tamper_best_sha else _sha(FAKE_CHECKPOINT),
        "calibration_sha256": cal_sha,
        "manifest_sha256": manifest_sha256,
        "config": {"arch_version": 2, "preproc_version": 2},
    }
    (path / "config.json").write_text(json.dumps(config), encoding="utf-8")
    return path


def _gcb_run(path: Path, manifest) -> Path:
    path.mkdir(parents=True)
    val = EvalPairs.from_manifest(manifest, "val")
    config = {
        "schema": "graphito.run_config/v1",
        "run_id": f"graphcodebert/{path.name}",
        "status": "complete",
        "manifest_sha256": manifest.sha256,
        "config": {
            "model_name": "microsoft/graphcodebert-base",
            "model_revision": "2b0488a7bb0eefc7041f1bb2cad1ab26b0da269d",
            "gcb_v2": {
                "code_length": 384, "data_flow_length": 128, "dtype": "float32", "input_version": "v2",
                "max_windows": 16, "pooling": "cls", "use_dfg": True, "walker_version": "c-cpp-2",
            },
        },
    }
    thresholds = {"methods": {"jaccard": {"space": "raw", "thresholds": {"fpr_0.05": {"threshold": 0.6491}}}}}
    selection = {
        "n_pairs": int(val.pairs.a.size),
        "files_sha256": hashlib.sha256("\n".join(sorted(val.pairs.ids)).encode("utf-8")).hexdigest(),
    }
    (path / "config.json").write_text(json.dumps(config), encoding="utf-8")
    (path / "thresholds_val.json").write_text(json.dumps(thresholds), encoding="utf-8")
    (path / "selection.json").write_text(json.dumps(selection), encoding="utf-8")
    return path


@pytest.fixture
def runs(tmp_path, corpus):
    _, _, manifest = corpus
    charcnn = _charcnn_run(tmp_path / "runs" / "char_cnn" / "20260101-000000", manifest.sha256)
    gcb = _gcb_run(tmp_path / "runs" / "graphcodebert" / "20260101-000001", manifest)
    return charcnn, gcb


def _argv(corpus, runs, out: Path, *extra: str):
    tree, manifest_path, _ = corpus
    charcnn, gcb = runs
    return [
        "--charcnn-run", str(charcnn), "--gcb-run", str(gcb), "--manifest", str(manifest_path),
        "--root", str(tree.repo_root), "--out", str(out), *extra,
    ]


def _read_manifest(out: Path) -> dict:
    return json.loads((out / "manifest.json").read_text(encoding="utf-8"))


def test_build_writes_verified_manifest(tmp_path, corpus, runs):
    out = tmp_path / "deploy"
    assert bda.main(_argv(corpus, runs, out)) == 0
    doc = _read_manifest(out)
    charcnn, gcb = runs
    _, _, manifest = corpus

    assert doc["schema"] == "graphito.deploy-manifest/v1"
    assert set(doc["files"]) == {"channel_a/calibration.json", "channel_b/best.pth", "channel_b/calibration.json"}
    for rel, sha in doc["files"].items():
        p = PurePosixPath(rel)
        assert not p.is_absolute() and ".." not in p.parts
        assert (out / rel).resolve().is_relative_to(out.resolve())
        assert _sha((out / rel).read_bytes()) == sha

    # DA2.1: isotonic Jaccard calibration fitted on val, fpr_0.05 present and non-null.
    cal_a = load_calibration(out / "channel_a" / "calibration.json")
    assert cal_a.artifact["fit_set"]["split"] == "val"
    assert cal_a.artifact["method"] == "isotonic"
    assert cal_a.artifact["thresholds"]["fpr_0.05"]["threshold"] is not None
    a = doc["channel_a"]
    assert a["method"] == "jaccard" and a["shingle_k"] == 5 and a["threshold_key"] == "fpr_0.05"
    assert a["threshold"] == cal_a.artifact["thresholds"]["fpr_0.05"]["threshold"]
    assert a["achieved_fpr"] <= 0.05 and a["tpr"] is not None
    assert a["raw_val_threshold_ref"] == 0.6491
    assert a["source_run"] == f"graphcodebert/{gcb.name}"

    # DA2.2: one split manifest across both channels.
    cal_b = load_calibration(out / "channel_b" / "calibration.json")
    assert doc["split_manifest_sha256"] == manifest.sha256 == cal_b.artifact["manifest"]["sha256"]
    assert cal_a.artifact["manifest"]["sha256"] == cal_b.artifact["manifest"]["sha256"]

    # Channel B is a verbatim copy of the run.
    b = doc["channel_b"]
    assert (out / "channel_b" / "best.pth").read_bytes() == FAKE_CHECKPOINT
    assert (out / "channel_b" / "calibration.json").read_bytes() == (charcnn / "calibration.json").read_bytes()
    assert b["threshold_key"] == "fpr_0.01"
    assert b["threshold"] == cal_b.artifact["thresholds"]["fpr_0.01"]["threshold"]
    assert b["source_run"] == f"char_cnn/{charcnn.name}" and b["arch_version"] == 2

    assert doc["gcb"]["role"] == "secondary_non_deciding" and doc["gcb"]["pooling"] == "mean"
    assert len(doc["gcb"]["fingerprint"]) == 64
    assert doc["build"]["limit_assignments"] is None
    assert doc["label"] == "not validated against reference-derived plagiarism"
    assert not list(out.rglob("*.tmp"))


def test_refuses_when_fpr_005_unachievable(tmp_path, corpus, runs, monkeypatch):
    def flat(manifest, root, limit_assignments=None):
        y = np.r_[np.zeros(30, dtype=int), np.ones(3, dtype=int)]
        data = ScoredSet([f"p{i}" for i in range(y.size)], np.full(y.size, 0.4), y, "val", manifest_sha256=manifest.sha256)
        return data, {"n_files": 10, "n_pairs": int(y.size), "files_sha256": None}

    monkeypatch.setattr(bda, "score_val_pairs", flat)
    out = tmp_path / "deploy"
    assert bda.main(_argv(corpus, runs, out)) == 1
    assert not out.exists() or not any(out.iterdir())


def test_refuses_split_manifest_mismatch(tmp_path, corpus, runs):
    charcnn = _charcnn_run(tmp_path / "other_cnn", "f" * 64)
    out = tmp_path / "deploy"
    assert bda.main(_argv(corpus, (charcnn, runs[1]), out)) == 1
    assert not out.exists()


def test_refuses_checkpoint_sha_mismatch(tmp_path, corpus, runs):
    _, _, manifest = corpus
    charcnn = _charcnn_run(tmp_path / "bad_cnn", manifest.sha256, tamper_best_sha=True)
    out = tmp_path / "deploy"
    assert bda.main(_argv(corpus, (charcnn, runs[1]), out)) == 1
    assert not out.exists()


def test_refuses_to_overwrite_differing_files_without_force(tmp_path, corpus, runs):
    out = tmp_path / "deploy"
    assert bda.main(_argv(corpus, runs, out)) == 0
    target = out / "channel_b" / "best.pth"
    target.write_bytes(b"locally edited")
    assert bda.main(_argv(corpus, runs, out)) == 1
    assert target.read_bytes() == b"locally edited"
    assert bda.main(_argv(corpus, runs, out, "--force")) == 0
    assert target.read_bytes() == FAKE_CHECKPOINT


def test_manifest_write_is_atomic(tmp_path, corpus, runs, monkeypatch):
    out = tmp_path / "deploy"
    assert bda.main(_argv(corpus, runs, out)) == 0
    before = (out / "manifest.json").read_bytes()
    real_write = bda.atomic_write_bytes

    def failing(path, data):
        if Path(path).name == "manifest.json":
            tmp = Path(path).with_name(f".{Path(path).name}.boom.tmp")
            tmp.write_bytes(data[:10])
            tmp.unlink()
            raise OSError("disk full")
        return real_write(path, data)

    monkeypatch.setattr(bda, "atomic_write_bytes", failing)
    with pytest.raises(OSError):
        bda.main(_argv(corpus, runs, out, "--force"))
    assert (out / "manifest.json").read_bytes() == before
    assert not list(out.rglob("*.tmp"))


def test_dry_run_writes_nothing(tmp_path, corpus, runs, capsys):
    out = tmp_path / "deploy"
    assert bda.main(_argv(corpus, runs, out, "--dry-run")) == 0
    assert not out.exists()
    assert "graphito.deploy-manifest/v1" in capsys.readouterr().out


def test_limit_assignments_is_debug_only(tmp_path, corpus, runs):
    assert bda.main(_argv(corpus, runs, bda.DEFAULT_OUT, "--limit-assignments", "2")) == 1
    out = tmp_path / "deploy"
    assert bda.main(_argv(corpus, runs, out, "--limit-assignments", "4")) == 0
    assert _read_manifest(out)["build"]["limit_assignments"] == 4


def test_out_dir_guard_protects_legacy_checkpoint():
    with pytest.raises(bda.BuildRefused):
        bda.check_out_dir(ROOT / "models" / "char_cnn")
    with pytest.raises(bda.BuildRefused):
        bda.check_out_dir(ROOT)
    bda.check_out_dir(ROOT / "models" / "deploy")


def test_help_mentions_required_runs(capsys):
    with pytest.raises(SystemExit) as exc:
        bda.main(["--help"])
    assert exc.value.code == 0
    text = capsys.readouterr().out
    assert "--charcnn-run" in text and "--gcb-run" in text and "--dry-run" in text
