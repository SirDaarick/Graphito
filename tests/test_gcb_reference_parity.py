"""Vendored upstream GraphCodeBERT reference: integrity (GD1.1) and harness smoke tests.

The reference lives in `tests/reference/graphcodebert/` (read-only, MIT, pinned commit in
`SOURCE.md`). The vendored files are never imported as modules; `harness.py` extracts only the
functions the golden tests need.
"""

import importlib.util
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REF_DIR = Path(__file__).resolve().parent / "reference" / "graphcodebert"


def _load_harness():
    spec = importlib.util.spec_from_file_location("gcb_reference_harness", REF_DIR / "harness.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


harness = _load_harness()


# --- GD1.1: integrity ---------------------------------------------------------------------


@pytest.mark.parametrize("rel", harness.VENDORED_FILES)
def test_vendored_file_present(rel):
    assert (REF_DIR / rel).is_file(), f"missing vendored reference file {rel}"


def test_source_md_pins_a_40_hex_commit():
    commit = harness.pinned_commit(REF_DIR)
    assert commit is not None and len(commit) == 40


def test_vendored_files_are_byte_identical_to_recorded_hashes():
    assert harness.check_reference(REF_DIR) == []


def test_license_is_mit():
    assert "MIT License" in (REF_DIR / "LICENSE").read_text(encoding="utf-8")


def test_truncation_constant_recorded():
    # run.py truncates code to `code_length + data_flow_length - k - min(n_dfg, D)`, then `[:512 - k]`.
    assert harness.truncation_constant(REF_DIR) == 3


@pytest.fixture
def ref_copy(tmp_path):
    dst = tmp_path / "graphcodebert"
    shutil.copytree(REF_DIR, dst, ignore=shutil.ignore_patterns("__pycache__"))
    return dst


@pytest.mark.parametrize("rel", harness.VENDORED_FILES)
def test_check_fails_when_a_reference_file_is_missing(ref_copy, rel):
    (ref_copy / rel).unlink()
    problems = harness.check_reference(ref_copy)
    assert any(rel in p for p in problems), problems


def test_check_fails_when_source_md_lacks_commit(ref_copy):
    src = ref_copy / "SOURCE.md"
    text = src.read_text(encoding="utf-8")
    src.write_text(text.replace(harness.pinned_commit(REF_DIR), "<no commit>"), encoding="utf-8")
    assert any("commit" in p for p in harness.check_reference(ref_copy))


def test_check_fails_when_a_reference_file_is_modified(ref_copy):
    target = ref_copy / "parser" / "DFG.py"
    target.write_bytes(target.read_bytes() + b"\n# local edit\n")
    assert any("parser/DFG.py" in p for p in harness.check_reference(ref_copy))


def test_vendored_files_are_not_collected_by_pytest():
    for path in REF_DIR.rglob("*.py"):
        name = path.name
        assert not (name.startswith("test_") or name.endswith("_test.py")), path


# --- harness smoke ------------------------------------------------------------------------


class FakeTokenizer:
    """Deterministic char-level tokenizer with the RoBERTa special-token layout."""

    cls_token, sep_token = "<s>", "</s>"
    pad_token_id, unk_token_id = 1, 3

    def __init__(self):
        self.vocab = {"<s>": 0, "<pad>": 1, "</s>": 2, "<unk>": 3, "@": 4}

    def tokenize(self, text):
        # '@ x' -> ['@', 'x'...] so `[1:]` drops the marker as with the BPE tokenizer.
        return [c for c in text if c != " "]

    def convert_tokens_to_ids(self, tokens):
        return [self.vocab.setdefault(t, len(self.vocab)) for t in tokens]


def test_harness_loads_upstream_dfg_java_and_utils():
    dfg_java = harness.load_dfg_java()
    utils = harness.load_utils()
    assert callable(dfg_java)
    assert callable(utils.tree_to_token_index) and callable(utils.tree_to_variable_index)


def test_extracted_run_features_and_mask_run_on_fake_tokenizer():
    tokens = ["int", "a", "=", "b", ";"]
    dfg = [("a", 1, "comesFrom", ["b"], [3]), ("b", 3, "comesFrom", [], [])]
    run = harness.load_run_reference(lambda code, parser, lang: (list(tokens), list(dfg)))
    args = SimpleNamespace(code_length=16, data_flow_length=4)
    tok = FakeTokenizer()
    item = ("u1", "u2", 1, tok, args, {}, {"u1": "x", "u2": "y"})
    feats = run.convert_examples_to_features(item)
    assert len(feats.input_ids_1) == 20 and len(feats.position_idx_1) == 20
    assert feats.dfg_to_dfg_1 == [[1], []]
    # 'int' -> 3 chars, 'a' -> 1 char after the CLS offset.
    assert feats.dfg_to_code_1[0] == (4, 5)
    dataset = SimpleNamespace(examples=[feats], args=args)
    out = run.getitem(dataset, 0)
    mask = out[2].numpy()
    assert mask.shape == (20, 20)
    node_index = sum(p > 1 for p in feats.position_idx_1)
    assert mask[node_index, node_index + 1]  # node a -> its parent b


# --- GD1.2: walker golden parity (design D2/D3) --------------------------------------------
#
# The vendored `DFG_java` walks the same tree-sitter tree through `JavaView`, so token indices
# coincide and the comparison is exact. Snippets cover only constructs shared with the Java
# walker and avoid the documented C deviations (design D4; e.g. no variable defined before an
# if/else and redefined in both branches, no compound assignment, no pointer/array declarator
# names, declaration-initialised `for` only). Parent code lists are compared as sets because
# upstream builds them with `list(set(...))` in loops and does not align them with the indices.

GOLDEN = [
    ("decl_init_chain", "c", "int f(){ int a = 1; int b = a; return b; }"),
    ("decl_without_init", "c", "int f(){ int a; a = 1; int c = a; return c; }"),
    ("multi_declarators", "c", "int f(int x){ int a = x, b, c = a; b = c; return b; }"),
    ("last_definition", "c", "int f(){ int a = 1; a = 2; int c = a; return c; }"),
    ("update", "c", "int f(int i){ i++; --i; int j = i; return j; }"),
    ("if_braced_no_else", "c", "int f(int c){ int a = 0; if (c) { a = 1; } int b = a; return b; }"),
    ("if_braceless_else", "c", "int f(int c){ int x = c; if (x > 0) y = x; else y = 2; return y; }"),
    ("else_if_chain", "c", "int f(int c){ if (c > 1) r = 1; else if (c > 0) r = c; else r = 3; return r; }"),
    ("for_decl_init", "c", "int f(int n){ int s = 0; for (int i = 0; i < n; i++) s = s + i; return s; }"),
    ("for_block_body", "c", "int f(int n){ int s = 1; for (int i = 0; i < n; i++) { int t = s; s = t * 2; } return s; }"),
    ("while", "c", "int f(int x){ int y = 0; while (x > 0) { y = y + x; x = x - 1; } return y; }"),
    ("call", "c", "int f(int a, int b){ int x = g(a, b); return x; }"),
    ("return_expression", "c", "int f(int a, int b){ return a * b + a; }"),
    ("literals", "c", "int f(){ char c = 'x'; char *s = \"hi\"; int n = c; return n; }"),
    ("nested_block", "c", "int f(int a){ { int b = a; a = b; } return a; }"),
    ("cpp_range_for", "cpp", "int f(std::vector<int> v){ int s = 0; for (int x : v) s = s + x; return s; }"),
    ("cpp_while_braceless", "cpp", "int f(int x){ while (x) x--; return x; }"),
    ("cpp_if_else", "cpp", "int f(int c){ int a = c; if (a) b = a; else b = c; return b; }"),
]


def _normalise(dfg):
    return [(code, idx, rel, tuple(sorted(set(codes))), tuple(idxs)) for code, idx, rel, codes, idxs in dfg]


def _v2_raw(code, lang):
    from models.graphcodebert.v2 import dfg as v2_dfg

    source = v2_dfg.prepare_source(code)
    root = v2_dfg.parse_source(source, lang).root_node
    tokens, index_to_code = v2_dfg.index_tokens(root, source)
    return tokens, v2_dfg.walk_dfg(root, index_to_code)


@pytest.mark.parametrize("name,lang,code", GOLDEN, ids=[g[0] for g in GOLDEN])
def test_token_parity_with_upstream(name, lang, code):
    ref_tokens, _ = harness.upstream_raw_dfg(code, lang)
    v2_tokens, _ = _v2_raw(code, lang)
    assert v2_tokens == ref_tokens


@pytest.mark.parametrize("name,lang,code", GOLDEN, ids=[g[0] for g in GOLDEN])
def test_raw_walker_parity_with_upstream_dfg_java(name, lang, code):
    _, ref = harness.upstream_raw_dfg(code, lang)
    _, ours = _v2_raw(code, lang)
    assert ref, "upstream walker produced nothing; the JavaView proxy is broken"
    assert _normalise(ours) == _normalise(ref)


@pytest.mark.parametrize("name,lang,code", GOLDEN, ids=[g[0] for g in GOLDEN])
def test_filtered_dataflow_parity_with_upstream_extract_dataflow(name, lang, code):
    from models.graphcodebert.v2.dfg import extract_dfg_v2

    ref_tokens, ref = harness.upstream_dataflow(code, lang)
    result = extract_dfg_v2(code, lang)
    assert ref, "upstream extract_dataflow produced nothing (it swallows exceptions)"
    assert result.code_tokens == ref_tokens
    assert _normalise(result.dfg) == _normalise(ref)
    assert result.parse_errors is False and result.dfg_error is None


def test_parity_detects_a_divergence():
    """Guard against a vacuous comparison: a C deviation (else does not union the pre-if
    definitions, design D4) must show up as a difference."""
    code = "int f(int c){ int a = 0; if (c) a = 1; else a = 2; int b = a; return b; }"
    _, ref = harness.upstream_raw_dfg(code, "c")
    _, ours = _v2_raw(code, "c")
    assert _normalise(ours) != _normalise(ref)
