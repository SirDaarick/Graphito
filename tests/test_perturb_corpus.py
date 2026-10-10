"""perturb_corpus: strip-comments transform, problem filter and layout preservation."""

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


perturb = _load("perturb_corpus", ROOT / "data" / "golden_set" / "perturb_corpus.py")


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


def test_problems_from_manifest_converts_slashes_and_filters_split(tmp_path):
    manifest = tmp_path / "m.json"
    manifest.write_text(
        json.dumps({"subproblems": {"train": ["A2016/Z1/Z1"], "test": ["B2017/Z6/Z4"]}}), encoding="utf-8"
    )
    assert perturb.problems_from_manifest(manifest, "test") == {"B2017_Z6_Z4"}
