"""Zero-shot evaluation CLI of GraphCodeBERT v2 (spec GV1-GV6, TH1.1; design D9-D12).

Synthetic `eval_factory` corpus, stub hash-vector embedders (no model), CPU only, small n_boot.
Every output goes under `tmp_path`.
"""

import gzip
import hashlib
import json
import shutil
from pathlib import Path

import numpy as np
import pytest

from eval_factory import make_tree
from models.evaluation.calibration import DEFAULT_TARGETS, load_calibration, select_threshold, threshold_key
from models.evaluation.manifest import load_manifest
from models.evaluation.normalize import shingle_tokens, tokenize
from models.evaluation.splits import SplitConfig, build_split, write_manifest
from models.graphcodebert.v2 import cache as C
from models.graphcodebert.v2 import evaluate as E
from models.graphcodebert.v2 import pairs as P
from models.graphcodebert.v2.runs import RUN_FAILED_EXIT, REFUSED_EXIT, STATUS_COMPLETE, STATUS_FAILED
from test_gcb_v2_pairs import pairset, sample

DIM = 64


def _bag(tokens, dim=DIM):
    v = np.zeros(dim, dtype=np.float32)
    for t in tokens:
        v[int(hashlib.md5(t.encode("utf-8")).hexdigest()[:8], 16) % dim] += 1.0
    return v


class HashEmbedder:
    """Deterministic stub: `cls` = hashed bag of tokens, `mean` = hashed bag of abstracted tokens.
    Raises when asked for a test-only file before any `selection.json` exists (stage order)."""

    def __init__(self, variant, guard=None, poolings=("cls", "mean"), fail_on=None):
        self.variant = variant
        self.poolings = poolings
        self.guard = guard  # (runs_root, test_only_shas, val_shas_seen)
        self.fail_on = fail_on
        self.calls = []

    def key_fields(self):
        return {"input_version": "stub", "variant": self.variant, "model_revision": "stub-rev"}

    def embed(self, code, language):
        digest = hashlib.sha256(code.encode("utf-8")).hexdigest()
        if self.guard is not None:
            runs_root, test_only, seen = self.guard
            if digest in test_only and not list(Path(runs_root).glob("graphcodebert/*/selection.json")):
                raise AssertionError("test file embedded before selection.json")
            if not list(Path(runs_root).glob("graphcodebert/*/selection.json")):
                seen.add(digest)
        if self.fail_on and self.fail_on(digest):
            raise RuntimeError("stub failure")
        self.calls.append(digest)
        vectors = {"cls": _bag(tokenize(code)), "mean": _bag(shingle_tokens(code))}
        return C.FileEmbedding(
            success=True,
            vectors={k: v for k, v in vectors.items() if k in self.poolings},
            flags={"n_windows": 1, "truncated": False, "parse_errors": False, "dfg_nodes_used": 1},
        )


@pytest.fixture(scope="module")
def corpus(tmp_path_factory):
    tree = make_tree(tmp_path_factory.mktemp("corpus"))
    config = SplitConfig(
        seed=7, repo_root=tree.repo_root, raw_root=tree.raw_root, ai_root=tree.ai_root,
        gt_static=tree.gt_static, gt_ambiguous=(tree.gt_dynamic,),
    )
    path = write_manifest(build_split(config), tree.repo_root / "data" / "splits" / "split_v1.json")
    return tree, path, load_manifest(path)


def _shas(manifest, split):
    return {
        s.sha256 for s in manifest.samples(split, source="human") if s.gt_status in ("positive", "negative")
    }


def _install(monkeypatch, embedders, statuses=None):
    def load(methods, **kwargs):
        chosen = {m: embedders[m] for m in methods if m in embedders}
        status = {m: {"status": "ok", "variant": embedders[m].variant, "reason": None} for m in chosen}
        status.update(statuses or {})
        return chosen, status

    monkeypatch.setattr(E, "load_embedders", load)


def _argv(tree, manifest_path, runs_root, *extra):
    return [
        "--manifest", str(manifest_path), "--root", str(tree.repo_root), "--runs-root", str(runs_root),
        "--device", "cpu", "--n-boot", "20", *extra,
    ]


def _json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def full_run(corpus, tmp_path_factory):
    tree, manifest_path, manifest = corpus
    work = tmp_path_factory.mktemp("work")
    runs_root = work / "runs"
    test_only = _shas(manifest, "test") - _shas(manifest, "val")
    seen = set()
    guard = (runs_root, test_only, seen)
    embedders = {"v2": HashEmbedder("dfg", guard), "v2_nodfg": HashEmbedder("nodfg", guard)}
    skipped = {"legacy": {"status": "skipped", "variant": None, "reason": "peft_unavailable: stub"}}
    with pytest.MonkeyPatch.context() as mp:
        mp.chdir(work)
        _install(mp, embedders, skipped)
        code = E.main(_argv(tree, manifest_path, runs_root))
    run_dirs = [p for p in (runs_root / "graphcodebert").iterdir() if p.name != "_cache"]
    return {"code": code, "work": work, "runs_root": runs_root, "run": run_dirs[0] if len(run_dirs) == 1 else None,
            "embedders": embedders, "seen_before_selection": seen, "manifest": manifest, "tree": tree,
            "manifest_path": manifest_path}


def test_full_run_completes_with_every_artifact(full_run):
    assert full_run["code"] == 0
    run = full_run["run"]
    config = _json(run / "config.json")
    assert config["status"] == STATUS_COMPLETE and config["failure"] is None
    assert config["channel"] == "graphcodebert" and config["mode"] == "zero_shot"
    versions = config["config"]["versions"]
    assert {"transformers", "tree-sitter", "tree-sitter-c", "tree-sitter-cpp", "torch"} <= set(versions)
    assert config["manifest_sha256"] == full_run["manifest"].sha256
    for name in ("selection.json", "thresholds_val.json", "calibration.json", "summary.json", "data_summary.json", "report.md"):
        assert (run / name).exists(), name
    for method in E.METHODS:
        for view in P.VIEWS:
            if method == "legacy":
                assert not (run / f"{method}__{view}").exists()
                continue
            d = run / f"{method}__{view}"
            assert (d / "metrics.json").exists() and (d / "report.md").exists(), d


def test_outputs_stay_under_runs_graphcodebert(full_run):
    created = [p for p in full_run["work"].rglob("*") if p.is_file()]
    base = full_run["runs_root"] / "graphcodebert"
    assert created and all(p.is_relative_to(full_run["run"]) or p.is_relative_to(base / "_cache") for p in created)


def test_every_method_key_and_view_is_reported_with_identical_pair_counts(full_run):
    summary = _json(full_run["run"] / "summary.json")
    assert set(summary["methods"]) == set(E.METHODS)
    assert summary["methods"]["legacy"]["status"] == "skipped"
    assert "peft_unavailable" in summary["methods"]["legacy"]["reason"]
    for view in P.VIEWS:
        counts = {
            m: summary["methods"][m]["views"][view]["n"] for m in E.METHODS if summary["methods"][m]["status"] == "ok"
        }
        assert len(set(counts.values())) == 1, (view, counts)


def test_selection_uses_val_files_only_and_test_after_selection(full_run):
    manifest = full_run["manifest"]
    val_ids = sorted(full_run_ids(manifest, "val"))
    selection = _json(full_run["run"] / "selection.json")
    assert selection["split"] == "val"
    assert selection["files_sha256"] == hashlib.sha256("\n".join(val_ids).encode("utf-8")).hexdigest()
    assert full_run["seen_before_selection"] and full_run["seen_before_selection"] <= _shas(manifest, "val")
    for method in ("v2", "v2_nodfg"):
        entry = selection["methods"][method]
        assert entry["pooling"] in ("cls", "mean") and set(entry["candidates"]) == {"cls", "mean"}
    assert selection["methods"]["jaccard"]["pooling"] is None


def full_run_ids(manifest, split):
    return {s.id for s in manifest.samples(split, source="human") if s.gt_status in ("positive", "negative")}


def test_thresholds_are_selected_on_raw_val_scores(full_run):
    manifest = full_run["manifest"]
    selection = _json(full_run["run"] / "selection.json")
    thresholds = _json(full_run["run"] / "thresholds_val.json")
    ep = P.EvalPairs.from_manifest(manifest, "val")
    pooling = selection["methods"]["v2"]["pooling"]
    root = full_run["tree"].repo_root
    stub = HashEmbedder("dfg")
    entries = [stub.embed((root / s.id).read_bytes().decode("utf-8"), s.lang) for s in ep.samples]
    emb, _ = P.stack_embeddings(entries, pooling)
    scores = P.score_pairs(P.embedding_similarity(emb), ep).scores
    entry = thresholds["methods"]["v2"]
    assert entry["split"] == "val" and entry["view"] == "all" and entry["space"] == "raw"
    for target in DEFAULT_TARGETS:
        expected = select_threshold(ep.pairs.label, scores, target)
        got = entry["thresholds"][threshold_key(target)]
        assert got["threshold"] == pytest.approx(expected["threshold"]) and got["n_neg"] == expected["n_neg"]


def test_test_metrics_bootstrap_by_assignment_with_val_operating_points(full_run):
    metrics = _json(full_run["run"] / "v2__all" / "metrics.json")
    assert metrics["split"] == "test" and metrics["bootstrap"]["unit"] == "assignment"
    ep = P.EvalPairs.from_manifest(full_run["manifest"], "test")
    assert metrics["bootstrap"]["n_units"] == len(set(ep.pairs.assignment))
    assert metrics["n"] == ep.pairs.a.size and metrics["n_pos"] == int(ep.pairs.label.sum())
    m = metrics["threshold_free"]["map_at_r"]
    assert m["unit"] == "assignment" and "value" in m and "ci95" in m
    for key, point in metrics["operating_points"].items():
        assert point["source"] == "val_raw_score"
        assert ("observed" in point) == (point["threshold"] is not None)  # unachievable on val -> no test counts
    no_id = _json(full_run["run"] / "v2__no_identical" / "metrics.json")
    assert no_id["n"] == ep.pairs.a.size - ep.dropped("no_identical")
    assert metrics["secondary_pooling"]["pooling"] != metrics["pooling"]


def test_calibration_is_isotonic_fit_on_val_pairs(full_run):
    loaded = load_calibration(full_run["run"] / "calibration.json")
    art = loaded.artifact
    assert art["method"] == "isotonic" and art["fit_set"]["split"] == "val"
    ep = P.EvalPairs.from_manifest(full_run["manifest"], "val")
    assert art["fit_set"]["n"] == ep.pairs.a.size
    assert art["manifest"]["sha256"] == full_run["manifest"].sha256


def test_data_summary_counts_exclusions_and_rates(full_run):
    data = _json(full_run["run"] / "data_summary.json")
    manifest = full_run["manifest"]
    for split in ("val", "test"):
        ep = P.EvalPairs.from_manifest(manifest, split)
        d = data["splits"][split]
        assert d["exclusions"] == ep.exclusions
        assert d["n_files"] == len(ep.pairs.ids) and d["views"]["all"]["n_pairs"] == ep.pairs.a.size
        assert d["views"]["no_identical"]["dropped"] == ep.dropped("no_identical")
        assert d["same_student_pairs"] == ep.same_student_pairs
    emb = data["embeddings"]["v2"]
    assert emb["failed"] == 0 and emb["parse_error_rate"] == 0.0 and emb["truncation_rate"] == 0.0


def test_curves_are_thinned_and_compressed(full_run):
    d = full_run["run"] / "v2__all"
    metrics = _json(d / "metrics.json")
    curves = metrics["curves"]
    assert curves["compressed"] == "gzip" and curves["max_points"] == E.CURVE_MAX_POINTS
    with gzip.open(d / "roc.csv.gz", "rt", encoding="utf-8") as fh:
        rows = fh.read().splitlines()
    assert rows[0] == "threshold,fpr,tpr" and 2 <= len(rows) - 1 <= E.CURVE_MAX_POINTS + 2
    assert not (d / "roc.csv").exists() and not (d / "pr.csv").exists()


def test_rerun_hits_the_cache(full_run, monkeypatch, tmp_path):
    tree, manifest_path = full_run["tree"], full_run["manifest_path"]
    embedders = {"v2": HashEmbedder("dfg"), "v2_nodfg": HashEmbedder("nodfg")}
    _install(monkeypatch, embedders)
    cache_dir = full_run["runs_root"] / "graphcodebert" / "_cache"
    code = E.main(_argv(tree, manifest_path, tmp_path / "runs", "--methods", "v2,v2_nodfg", "--cache-dir", str(cache_dir)))
    assert code == 0
    assert embedders["v2"].calls == [] and embedders["v2_nodfg"].calls == []
    run = next(p for p in (tmp_path / "runs" / "graphcodebert").iterdir())
    data = _json(run / "data_summary.json")
    assert data["embeddings"]["v2"]["cache"]["misses"] == 0 and data["embeddings"]["v2"]["cache"]["hits"] > 0


def test_no_cache_writes_no_cache_dir(full_run, monkeypatch, tmp_path):
    _install(monkeypatch, {"v2": HashEmbedder("dfg")})
    code = E.main(_argv(full_run["tree"], full_run["manifest_path"], tmp_path / "runs", "--methods", "v2,jaccard", "--no-cache"))
    assert code == 0 and not (tmp_path / "runs" / "graphcodebert" / "_cache").exists()


def test_expected_sha256_mismatch_refuses_without_writing(full_run, monkeypatch, tmp_path):
    _install(monkeypatch, {"v2": HashEmbedder("dfg")})
    code = E.main(_argv(full_run["tree"], full_run["manifest_path"], tmp_path / "runs", "--expected-sha256", "0" * 64))
    assert code == REFUSED_EXIT and not (tmp_path / "runs").exists()


def test_file_sha_mismatch_refuses_without_writing(corpus, monkeypatch, tmp_path):
    tree, manifest_path, manifest = corpus
    copy = tmp_path / "copy"
    shutil.copytree(tree.repo_root, copy)
    victim = sorted(full_run_ids(manifest, "test"))[0]
    (copy / victim).write_text("int tampered;\n", encoding="utf-8")
    _install(monkeypatch, {"v2": HashEmbedder("dfg")})
    code = E.main([
        "--manifest", str(manifest_path), "--root", str(copy), "--runs-root", str(tmp_path / "runs"),
        "--device", "cpu", "--n-boot", "5",
    ])
    assert code == REFUSED_EXIT and not (tmp_path / "runs").exists()


def test_local_files_only_without_model_refuses(full_run, monkeypatch, tmp_path):
    monkeypatch.setattr(E, "_model_available", lambda name: False)
    code = E.main(_argv(full_run["tree"], full_run["manifest_path"], tmp_path / "runs", "--local-files-only", "--methods", "v2"))
    assert code == REFUSED_EXIT and not (tmp_path / "runs").exists()


def test_unknown_method_refuses(full_run, tmp_path):
    code = E.main(_argv(full_run["tree"], full_run["manifest_path"], tmp_path / "runs", "--methods", "v2,bert"))
    assert code == REFUSED_EXIT and not (tmp_path / "runs").exists()


def test_failure_marks_the_run_failed_with_exit_3(full_run, monkeypatch, tmp_path):
    test_only = _shas(full_run["manifest"], "test") - _shas(full_run["manifest"], "val")
    _install(monkeypatch, {"v2": HashEmbedder("dfg", fail_on=lambda sha: sha in test_only)})
    code = E.main(_argv(full_run["tree"], full_run["manifest_path"], tmp_path / "runs", "--methods", "v2", "--no-cache"))
    assert code == RUN_FAILED_EXIT
    run = next((tmp_path / "runs" / "graphcodebert").iterdir())
    config = _json(run / "config.json")
    assert config["status"] == STATUS_FAILED and config["failure"]["stage"] == "test"
    assert "stub failure" in config["failure"]["reason"]


def test_limit_assignments_is_recorded(full_run, monkeypatch, tmp_path):
    _install(monkeypatch, {"v2": HashEmbedder("dfg")})
    code = E.main(_argv(full_run["tree"], full_run["manifest_path"], tmp_path / "runs", "--methods", "v2", "--limit-assignments", "1"))
    assert code == 0
    run = next((tmp_path / "runs" / "graphcodebert").iterdir())
    assert _json(run / "config.json")["config"]["limit_assignments"] == 1
    data = _json(run / "data_summary.json")
    assert data["splits"]["val"]["n_assignments"] == 1 and data["splits"]["test"]["n_assignments"] == 1


# --- stage guards and pure helpers ------------------------------------------------------------


def _tiny_evaluation(tmp_path, labels_positive=True):
    samples = [
        sample("x1", "X", "s1", "c1" if labels_positive else None, "h1"),
        sample("x2", "X", "s2", "c1" if labels_positive else None, "h2"),
        sample("x3", "X", "s3", None, "h3"),
    ]
    ep = P.EvalPairs.build(*pairset(samples), split="val")
    test_ep = P.EvalPairs.build(*pairset(samples), split="test")
    files = {
        s.id: E.FileRecord(id=s.id, sha256=hashlib.sha256(s.id.encode()).hexdigest(), text=f"int {s.id} = 1;", lang="c")
        for s in samples
    }
    run = tmp_path / "run"
    run.mkdir()
    return E.Evaluation(
        run, val=ep, test=test_ep, files=files, embedders={"v2": HashEmbedder("dfg")},
        statuses={"v2": {"status": "ok", "variant": "dfg", "reason": None}}, methods=("v2", "jaccard"),
        cache_root=None, n_boot=5, seed=1, manifest_sha256="f" * 64, manifest_path=None,
    )


def test_test_stage_requires_selection_and_runs_once(tmp_path):
    ev = _tiny_evaluation(tmp_path)
    with pytest.raises(RuntimeError, match="selection"):
        ev.evaluate_test()
    ev.run_val()
    ev.select()
    ev.evaluate_test()
    with pytest.raises(RuntimeError, match="once"):
        ev.evaluate_test()


def test_undefined_metrics_are_null_with_reason(tmp_path):
    ev = _tiny_evaluation(tmp_path, labels_positive=False)
    ev.run_val()
    ev.select()
    ev.evaluate_test()
    metrics = _json(tmp_path / "run" / "v2__all" / "metrics.json")
    assert metrics["threshold_free"]["pr_auc"]["value"] is None
    assert metrics["threshold_free"]["pr_auc"]["reason"] == "single_class"
    assert metrics["threshold_free"]["map_at_r"]["value"] is None
    assert metrics["threshold_free"]["map_at_r"]["reason"] == "no_queries"


@pytest.mark.parametrize(
    "candidates, expected",
    [
        ({"cls": {"pr_auc": 0.4, "map_at_r": 0.9}, "mean": {"pr_auc": 0.5, "map_at_r": 0.1}}, "mean"),
        ({"cls": {"pr_auc": 0.5, "map_at_r": 0.3}, "mean": {"pr_auc": 0.5, "map_at_r": 0.4}}, "mean"),
        ({"cls": {"pr_auc": 0.5, "map_at_r": 0.4}, "mean": {"pr_auc": 0.5, "map_at_r": 0.4}}, "cls"),
        ({"cls": {"pr_auc": None, "map_at_r": None}, "mean": {"pr_auc": None, "map_at_r": None}}, "cls"),
        ({"cls": {"pr_auc": None, "map_at_r": None}, "mean": {"pr_auc": 0.1, "map_at_r": None}}, "mean"),
    ],
)
def test_choose_pooling_by_val_pr_auc_then_map_then_cls(candidates, expected):
    assert E.choose_pooling(candidates) == expected


def test_thin_curve_keeps_endpoints_and_caps_points():
    x = np.linspace(0, 1, 10_000)
    idx = E.thin_indices(x, x ** 2, 50)
    assert idx[0] == 0 and idx[-1] == 9_999 and len(idx) <= 52 and np.all(np.diff(idx) > 0)
    assert list(E.thin_indices(x[:5], x[:5], 50)) == [0, 1, 2, 3, 4]
