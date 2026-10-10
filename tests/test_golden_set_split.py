"""Golden set rebuilt from the split manifest: provenance, split purity, determinism (GS1-GS5)."""

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from eval_factory import make_tree
from models.evaluation.manifest import load_manifest
from models.evaluation.provenance import file_sha256
from models.evaluation.splits import SplitConfig, build_split, write_manifest

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "tests" / "fixtures" / "golden_set_tiny"
CLASSES = ("reference", "original", "copy", "ai")


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


corpus_builder = _load("build_corpus", ROOT / "data" / "golden_set" / "build_corpus.py")
manifest_builder = _load("build_manifest", ROOT / "data" / "golden_set" / "build_manifest.py")


def _snapshot(root: Path):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def _code_files(root: Path):
    return sorted(
        p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file() and p.suffix in (".c", ".cpp")
    )


@pytest.fixture(scope="module")
def split_env(tmp_path_factory):
    """A synthetic tree, its split manifest on disk and the test/val golden corpora built from it."""
    base = tmp_path_factory.mktemp("golden")
    tree = make_tree(base / "repo")
    config = SplitConfig(
        seed=7,
        repo_root=tree.repo_root,
        raw_root=tree.raw_root,
        ai_root=tree.ai_root,
        gt_static=tree.gt_static,
        gt_ambiguous=(tree.gt_dynamic,),
    )
    split_path = write_manifest(build_split(config), base / "split.json")
    manifest = load_manifest(split_path)
    corpora = {}
    for split in ("test", "val"):
        out = base / f"corpus_{split}"
        corpus_builder.build_corpus(split_path, split, out, repo_root=tree.repo_root, seed=42, cap=10)
        corpora[split] = out
    return tree, split_path, manifest, corpora


def _provenance(out: Path):
    return json.loads((out / "provenance.json").read_text(encoding="utf-8"))


# --- build_corpus ------------------------------------------------------------------------------


class TestBuildCorpus:
    def test_test_corpus_holds_only_test_ids(self, split_env):
        _, _, manifest, corpora = split_env
        prov = _provenance(corpora["test"])
        ids = {f["id"] for f in prov["files"].values()}
        assert ids, "the synthetic test split must yield a non-empty golden set"
        assert {manifest.split_of(i) for i in ids} == {"test"}
        held = {s.id for s in manifest.entries if s.split in ("train", "val")}
        assert ids.isdisjoint(held)
        assert prov["split"] == "test"
        assert all(f["split"] == "test" for f in prov["files"].values())

    def test_every_corpus_file_is_in_provenance(self, split_env):
        _, _, _, corpora = split_env
        out = corpora["test"]
        prov = _provenance(out)
        assert _code_files(out) == sorted(prov["files"])
        for rel, meta in prov["files"].items():
            problem, cls, _ = rel.split("/")
            assert cls in CLASSES and meta["class"] == cls
            assert problem == meta["assignment"].replace("/", "_")
            for key in ("id", "split", "model", "profile", "dup_group", "source", "lang", "gt_status"):
                assert key in meta

    def test_broken_and_excluded_entries_are_absent(self, split_env):
        _, _, manifest, corpora = split_env
        dropped = {s.id for s in manifest.entries if s.broken or s.excluded}
        for out in corpora.values():
            ids = {f["id"] for f in _provenance(out)["files"].values()}
            assert ids.isdisjoint(dropped)

    def test_human_classes_follow_gt_status(self, split_env):
        _, _, manifest, corpora = split_env
        by_id = {s.id: s for s in manifest.entries}
        for out in corpora.values():
            for meta in _provenance(out)["files"].values():
                sample = by_id[meta["id"]]
                if meta["class"] == "ai":
                    assert sample.source == "ai"
                elif meta["class"] == "copy":
                    assert sample.gt_status == "positive"
                else:  # reference / original: honest humans only
                    assert sample.gt_status == "negative"
                # unlabeled (e.g. B2017) and ambiguous humans never reach a human class
                assert sample.gt_status not in ("unlabeled", "ambiguous")

    def test_file_bytes_match_the_split_sources(self, split_env):
        tree, _, _, corpora = split_env
        out = corpora["test"]
        for rel, meta in _provenance(out)["files"].items():
            assert (out / rel).read_bytes() == (tree.repo_root / meta["id"]).read_bytes()

    def test_source_manifest_sha256_matches_the_split_file(self, split_env):
        _, split_path, _, corpora = split_env
        for out in corpora.values():
            assert _provenance(out)["source_manifest_sha256"] == file_sha256(split_path)

    def test_val_corpus_holds_only_val_ids(self, split_env):
        _, _, manifest, corpora = split_env
        ids = {f["id"] for f in _provenance(corpora["val"])["files"].values()}
        assert ids and {manifest.split_of(i) for i in ids} == {"val"}

    def test_rebuild_is_byte_identical(self, split_env, tmp_path):
        tree, split_path, _, corpora = split_env
        again = tmp_path / "again"
        corpus_builder.build_corpus(split_path, "test", again, repo_root=tree.repo_root, seed=42, cap=10)
        assert _snapshot(again) == _snapshot(corpora["test"])

    def test_train_split_is_refused(self, split_env, tmp_path):
        tree, split_path, _, _ = split_env
        with pytest.raises(ValueError, match="train"):
            corpus_builder.build_corpus(split_path, "train", tmp_path / "x", repo_root=tree.repo_root)
        with pytest.raises(SystemExit):
            corpus_builder.main(["--split-manifest", str(split_path), "--split", "train", "--out", str(tmp_path / "y")])

    def test_entry_id_escaping_the_repo_root_is_refused(self, tmp_path, monkeypatch):
        repo = tmp_path / "repo"
        (repo / "data" / "raw").mkdir(parents=True)
        (repo / "data" / "raw" / "h.c").write_text("int h;\n", encoding="utf-8")
        (tmp_path / "outside.c").write_text("int secret;\n", encoding="utf-8")

        def sample(id_, source, gt_status):
            return SimpleNamespace(
                id=id_, split="test", assignment="A2016/Z1/Z1", source=source, lang="c", model=None,
                profile=None, dup_group=None, cluster_id=None, gt_status=gt_status,
            )

        samples = [sample("data/raw/h.c", "human", "negative"), sample("../outside.c", "ai", "n/a")]
        fake = SimpleNamespace(samples=lambda split: samples, path=tmp_path / "split.json", sha256="f" * 64)
        monkeypatch.setattr(corpus_builder, "load_manifest", lambda path, sha=None: fake)
        with pytest.raises(ValueError, match=r"\.\./outside\.c"):
            corpus_builder.build_corpus(tmp_path / "split.json", "test", tmp_path / "out", repo_root=repo)
        assert not list((tmp_path / "out").rglob("outside.c"))

    def test_val_corpus_goes_to_corpus_val_by_default(self):
        assert corpus_builder.default_out("test").name == "corpus"
        assert corpus_builder.default_out("val").name == "corpus_val"

    def test_cli_builds_from_the_split_manifest(self, split_env, tmp_path):
        tree, split_path, _, corpora = split_env
        out = tmp_path / "cli"
        code = corpus_builder.main([
            "--split-manifest", str(split_path), "--split", "test", "--repo-root", str(tree.repo_root),
            "--out", str(out), "--seed", "42",
        ])
        assert code == 0
        assert _snapshot(out) == _snapshot(corpora["test"])


# --- build_manifest ----------------------------------------------------------------------------


class TestBuildManifest:
    def test_manifest_carries_provenance_and_no_train(self, split_env):
        _, split_path, _, corpora = split_env
        m = manifest_builder.build_manifest(corpora["test"])
        assert m["source_manifest_sha256"] == file_sha256(split_path)
        assert m["samples"]
        assert {s["split"] for s in m["samples"]} == {"test"}
        prov = _provenance(corpora["test"])["files"]
        for s in m["samples"]:
            assert s["split_id"] == prov[s["path"]]["id"]
            assert "sha256" not in s

    def test_manifest_rebuild_is_byte_identical(self, split_env, tmp_path):
        _, _, _, corpora = split_env
        a, b = tmp_path / "a.json", tmp_path / "b.json"
        for out in (a, b):
            assert manifest_builder.main([str(corpora["test"]), "--out", str(out)]) == 0
        assert a.read_bytes() == b.read_bytes()

    def test_train_entry_in_provenance_raises_naming_it(self, tmp_path):
        corpus = tmp_path / "corpus"
        (corpus / "P" / "ai").mkdir(parents=True)
        (corpus / "P" / "ai" / "a.c").write_text("int main(void) { return 0; }\n", encoding="utf-8")
        prov = {
            "schema": "graphito.golden_provenance/v1", "split": "test", "seed": 42,
            "source_manifest_sha256": "f" * 64,
            "files": {"P/ai/a.c": {"id": "data/output/X/Z1/Z1/leak.c", "split": "train", "class": "ai",
                                   "source": "ai", "lang": "c", "model": None, "profile": None,
                                   "dup_group": None, "cluster_id": None, "gt_status": "n/a",
                                   "assignment": "X/Z1/Z1"}},
        }
        (corpus / "provenance.json").write_text(json.dumps(prov), encoding="utf-8")
        with pytest.raises(ValueError, match="data/output/X/Z1/Z1/leak.c"):
            manifest_builder.build_manifest(corpus)

    def test_corpus_file_missing_from_provenance_raises(self, tmp_path):
        corpus = tmp_path / "corpus"
        (corpus / "P" / "ai").mkdir(parents=True)
        (corpus / "P" / "ai" / "a.c").write_text("int a;\n", encoding="utf-8")
        (corpus / "provenance.json").write_text(
            json.dumps({"schema": "graphito.golden_provenance/v1", "split": "test", "seed": 1,
                        "source_manifest_sha256": "f" * 64, "files": {}}),
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="P/ai/a.c"):
            manifest_builder.build_manifest(corpus)

    def test_without_provenance_requires_synthetic(self, tmp_path):
        corpus = tmp_path / "corpus"
        (corpus / "P" / "ai").mkdir(parents=True)
        (corpus / "P" / "ai" / "a.c").write_text("int a;\n", encoding="utf-8")
        with pytest.raises(ValueError, match="--synthetic"):
            manifest_builder.build_manifest(corpus)
        m = manifest_builder.build_manifest(corpus, synthetic=True)
        assert [s["split"] for s in m["samples"]] == ["test"]
        assert m["source_manifest_sha256"] is None
        assert manifest_builder.main([str(corpus), "--out", str(tmp_path / "m.json")]) != 0

    @staticmethod
    def _synthetic_corpus(root, files):
        for rel, text in files:
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).write_bytes(text.encode("utf-8"))
        return root

    def test_synthetic_corpus_dedups_identical_files_within_problem_and_class(self, tmp_path):
        corpus = self._synthetic_corpus(tmp_path / "corpus", (
            ("P/copy/a.c", "int a;\n"), ("P/copy/b.c", "int a;\n"), ("P/ai/c.c", "int c;\n"),
            ("Q/original/d.c", "int a;\n"),
        ))
        m = manifest_builder.build_manifest(corpus, synthetic=True)
        # only P/copy/b.c collapses onto P/copy/a.c; Q is another problem, so d.c is kept
        assert [s["path"] for s in m["samples"]] == ["P/copy/a.c", "P/ai/c.c", "Q/original/d.c"]
        assert m["duplicates_removed"] == ["P/copy/b.c"]

    def test_synthetic_exact_copy_of_its_original_is_a_kept_positive(self, tmp_path):
        """A byte-identical copy of an original (or reference) in the same problem is the
        textbook plagiarism positive: content dedup must never drop it across classes."""
        corpus = self._synthetic_corpus(tmp_path / "corpus", (
            ("P/reference/r.c", "int s(int a){return a;}\n"), ("P/original/o.c", "int s(int a){return a;}\n"),
            ("P/copy/k.c", "int s(int a){return a;}\n"),
        ))
        m = manifest_builder.build_manifest(corpus, synthetic=True)
        by_path = {s["path"]: s for s in m["samples"]}
        assert sorted(by_path) == ["P/copy/k.c", "P/original/o.c", "P/reference/r.c"]
        assert by_path["P/copy/k.c"]["label_copy"] is True
        assert by_path["P/original/o.c"]["label_copy"] is False
        assert m["duplicates_removed"] == []

    def test_tiny_fixture_dedups_by_dup_group(self):
        m = manifest_builder.build_manifest(FIXTURE)
        paths = [s["path"] for s in m["samples"]]
        assert "p01_sum/copy/c1.c" in paths
        assert "p01_sum/copy/c1_dup.c" not in paths
        assert m["duplicates_removed"] == ["p01_sum/copy/c1_dup.c"]

    def test_tiny_fixture_labels_and_warnings(self):
        m = manifest_builder.build_manifest(FIXTURE)
        assert m["counts"]["by_label"]["ai"] == 4
        assert m["counts"]["by_label"]["reference"] == 4
        assert m["counts"]["by_split"] == {"test": len(m["samples"])}
        assert m["warnings"], "fixture has < 6 LLM files per problem, a warning is expected"

    def test_tiny_fixture_is_deterministic(self):
        assert manifest_builder.build_manifest(FIXTURE) == manifest_builder.build_manifest(FIXTURE)

    def test_no_split_hashing_left(self):
        assert not hasattr(manifest_builder, "assign_split")
        assert not hasattr(manifest_builder, "sha256_bytes")
