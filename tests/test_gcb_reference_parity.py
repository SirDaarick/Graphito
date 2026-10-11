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
