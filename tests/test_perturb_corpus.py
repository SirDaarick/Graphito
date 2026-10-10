"""perturb_corpus: strip-comments transform, problem filter and layout preservation."""

import importlib.util
import json
from pathlib import Path

import pytest

from eval_factory import make_tree
from models.evaluation.manifest import load_manifest
from models.evaluation.splits import SplitConfig, build_split, write_manifest

ROOT = Path(__file__).resolve().parent.parent


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


perturb = _load("perturb_corpus", ROOT / "data" / "golden_set" / "perturb_corpus.py")
corpus_builder = _load("build_corpus", ROOT / "data" / "golden_set" / "build_corpus.py")


def test_strip_removes_line_and_block_comments():
    code = "int a; // tail\n/* block\n spans */ int b;\n"
    out = perturb.strip_comments(code)
    assert "tail" not in out and "block" not in out and "spans" not in out
    assert "int a;" in out and "int b;" in out


def test_strip_keeps_comment_markers_inside_literals():
    code = 'char *s = "// not a comment";\nchar c = \'/\';\nchar *t = "/* nor this */";\n'
    assert perturb.strip_comments(code) == code


def test_strip_handles_escaped_quote_in_string():
    code = 'char *s = "a\\" // still string"; // real comment\n'
    out = perturb.strip_comments(code)
    assert '"a\\" // still string"' in out
    assert "real comment" not in out


def test_strip_preserves_line_count_for_block_comments():
    code = "a\n/* x\ny\nz */\nb\n"
    assert perturb.strip_comments(code).count("\n") == code.count("\n")


def _write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def test_build_keeps_layout_and_applies_to_every_class(tmp_path):
    src, out = tmp_path / "src", tmp_path / "out"
    for cls in ("reference", "original", "copy", "ai"):
        _write(src / "A2016_Z1_Z2" / cls / f"{cls}.c", f"int {cls}; // note\n")
    _write(src / "A2016_Z1_Z1" / "ai" / "x.c", "int x; // note\n")

    n = perturb.build_perturbed(src, out, "strip-comments", only_problems={"A2016_Z1_Z2"})

    assert n == 4
    assert not (out / "A2016_Z1_Z1").exists()
    for cls in ("reference", "original", "copy", "ai"):
        text = (out / "A2016_Z1_Z2" / cls / f"{cls}.c").read_text(encoding="utf-8")
        assert "note" not in text and f"int {cls};" in text


def test_none_transform_is_identity_copy(tmp_path):
    src, out = tmp_path / "src", tmp_path / "out"
    _write(src / "P" / "ai" / "a.c", "int a; // keep\n")
    assert perturb.build_perturbed(src, out, "none") == 1
    assert (out / "P" / "ai" / "a.c").read_text(encoding="utf-8") == "int a; // keep\n"


def test_line_endings_are_preserved_byte_for_byte(tmp_path):
    src, out = tmp_path / "src", tmp_path / "out"
    (src / "P" / "ai").mkdir(parents=True)
    (src / "P" / "ai" / "lf.c").write_bytes(b"int a;\nint b;\n")
    (src / "P" / "ai" / "crlf.c").write_bytes(b"int a;\r\nint b;\r\n")
    for transform in ("none", "strip-comments"):
        perturb.build_perturbed(src, out / transform, transform)
        assert (out / transform / "P" / "ai" / "lf.c").read_bytes() == b"int a;\nint b;\n"
        assert (out / transform / "P" / "ai" / "crlf.c").read_bytes() == b"int a;\r\nint b;\r\n"


def test_strip_comments_is_the_evaluation_package_function():
    from models.evaluation.normalize import strip_comments

    assert perturb.strip_comments is strip_comments
    assert not hasattr(perturb, "problems_from_manifest")


@pytest.fixture(scope="module")
def golden(tmp_path_factory):
    """A split manifest from the synthetic factory tree and the test golden set rebuilt from it."""
    base = tmp_path_factory.mktemp("perturb")
    tree = make_tree(base / "repo")
    config = SplitConfig(
        seed=7, repo_root=tree.repo_root, raw_root=tree.raw_root, ai_root=tree.ai_root,
        gt_static=tree.gt_static, gt_ambiguous=(tree.gt_dynamic,),
    )
    split_path = write_manifest(build_split(config), base / "split.json")
    corpus = base / "corpus"
    corpus_builder.build_corpus(split_path, "test", corpus, repo_root=tree.repo_root)
    return split_path, load_manifest(split_path), corpus


def test_problems_from_split_lists_only_that_split(golden):
    split_path, manifest, _ = golden
    test = perturb.problems_from_split(split_path, "test")
    assert test == {s.assignment.replace("/", "_") for s in manifest.samples("test")}
    others = {s.assignment.replace("/", "_") for s in manifest.samples() if s.split != "test"}
    assert test and test.isdisjoint(others)
    with pytest.raises(ValueError, match="train"):
        perturb.problems_from_split(split_path, "train")


def test_perturbs_the_rebuilt_golden_set_without_train_or_val(golden, tmp_path):
    split_path, manifest, corpus = golden
    out = tmp_path / "strip"
    code = perturb.main([
        "--src", str(corpus), "--transform", "strip-comments", "--out", str(out),
        "--split-manifest", str(split_path), "--split", "test",
    ])
    assert code == 0
    prov = json.loads((out / "provenance.json").read_text(encoding="utf-8"))
    assert prov == json.loads((corpus / "provenance.json").read_text(encoding="utf-8"))
    written = sorted(p.relative_to(out).as_posix() for p in out.rglob("*.c*"))
    assert written and written == sorted(prov["files"])
    assert {manifest.split_of(f["id"]) for f in prov["files"].values()} == {"test"}
