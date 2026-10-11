"""GraphCodeBERT v2 feature builder and attention mask (GE1-GE3).

The golden tests run the vendored upstream `convert_examples_to_features` and
`TextDataset.__getitem__` (extracted by `tests/reference/graphcodebert/harness.py`) and `encode` on
the same `(code_tokens, dfg)` input and require every array to be equal. The fake tokenizer runs
offline; the real tokenizer case needs the cached `microsoft/graphcodebert-base`.
"""

import copy
import importlib.util
import sys
import zlib
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from models.graphcodebert.v2 import encode as v2_encode
from models.graphcodebert.v2.config import GCBV2Config
from models.graphcodebert.v2.dfg import extract_dfg_v2

REF_DIR = Path(__file__).resolve().parent / "reference" / "graphcodebert"


def _load_harness():
    name = "gcb_reference_harness"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, REF_DIR / "harness.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


harness = _load_harness()


class FakeTokenizer:
    """Deterministic RoBERTa-like tokenizer: words split on spaces, chunks of 3 chars, `Ġ` marks a
    word after a space. Special ids follow RoBERTa (`<s>`=0, `<pad>`=1, `</s>`=2, `<unk>`=3), which
    upstream hard-codes in the mask (`i in [0, 2]`)."""

    cls_token, pad_token, sep_token, unk_token = "<s>", "<pad>", "</s>", "<unk>"
    cls_token_id, pad_token_id, sep_token_id, unk_token_id = 0, 1, 2, 3
    _special = {"<s>": 0, "<pad>": 1, "</s>": 2, "<unk>": 3}

    def tokenize(self, text):
        out = []
        for w, word in enumerate(text.split(" ")):
            if not word:
                continue
            chunks = [word[i : i + 3] for i in range(0, len(word), 3)]
            if w > 0:
                chunks[0] = "Ġ" + chunks[0]
            out += chunks
        return out

    def convert_tokens_to_ids(self, tokens):
        return [self._special.get(t, 4 + zlib.crc32(t.encode("utf-8")) % 5000) for t in tokens]


def _upstream(code_tokens, dfg, tokenizer, code_length=384, data_flow_length=128):
    """Vendored run.py features + mask for one input (url1 == url2)."""

    def extract_dataflow(func, parser, lang):
        return copy.deepcopy(func)

    ref = harness.load_run_reference(extract_dataflow)
    args = SimpleNamespace(code_length=code_length, data_flow_length=data_flow_length)
    item = ("u", "u", 0, tokenizer, args, {}, {"u": (list(code_tokens), copy.deepcopy(list(dfg)))})
    feats = ref.convert_examples_to_features(item)
    ids, pos, mask, *_ = ref.getitem(SimpleNamespace(examples=[feats], args=args), 0)
    return feats, ids.numpy(), pos.numpy(), mask.numpy()


def _assert_golden(code_tokens, dfg, tokenizer, code_length=384, data_flow_length=128):
    feats, ids, pos, mask = _upstream(code_tokens, dfg, tokenizer, code_length, data_flow_length)
    cfg = GCBV2Config(code_length=code_length, data_flow_length=data_flow_length)
    enc = v2_encode.encode(code_tokens, copy.deepcopy(list(dfg)), tokenizer, cfg)
    assert enc.source_tokens == feats.input_tokens_1
    assert enc.input_ids == feats.input_ids_1 == ids.tolist()
    assert enc.position_idx == feats.position_idx_1 == pos.tolist()
    assert enc.dfg_to_code == feats.dfg_to_code_1
    assert enc.dfg_to_dfg == feats.dfg_to_dfg_1
    assert enc.attn_mask.dtype == np.bool_ and enc.attn_mask.shape == mask.shape
    assert np.array_equal(enc.attn_mask, mask)
    return enc


SNIPPETS = {
    "decl": ("c", "int f(int a){ int b = a; int c = b + a; return c; }"),
    "loop": ("c", "int s(int n){ int t = 0; for (int i = 0; i < n; i++) { t += i; } return t; }"),
    "branch": ("c", "int g(int x){ int y; if (x > 0) y = x; else y = -x; while (y > 10) y = y - 10; return y; }"),
    "strings": ("c", '#include <stdio.h>\nint main(void){ char *s = "hola mundo"; printf("%s\\n", s); return 0; }'),
    "cpp_range": ("cpp", "int sum(std::vector<int> v){ int acc = 0; for (int x : v) acc = acc + x; return acc; }"),
}


def _synthetic(n_tokens, n_nodes, word="identifier"):
    """`n_tokens` tokens (each 4 subtokens with the fake tokenizer) and a chain DFG of
    `n_nodes` nodes over the first tokens (node k comes from node k-1)."""
    tokens = [f"{word}{i}" for i in range(n_tokens)]
    dfg = []
    for k in range(n_nodes):
        idx = (k * 3) % n_tokens
        parents = [((k - 1) * 3) % n_tokens] if k else []
        dfg.append((tokens[idx], idx, "comesFrom", [tokens[p] for p in parents], parents))
    return tokens, sorted(dfg, key=lambda x: x[1])


# --- GE1.1: alignment ---------------------------------------------------------------------


def test_token_split_in_three_is_contiguous():
    tok = FakeTokenizer()
    subtokens, ori2cur = v2_encode.subtokenize(["int", "abcdefghi", "x"], tok)
    assert ori2cur[-1] == (0, 0)
    assert ori2cur[0] == (0, 1)
    assert ori2cur[1] == (1, 4) and ori2cur[1][1] - ori2cur[1][0] == 3
    assert ori2cur[2] == (4, 5)
    assert subtokens[1:4] == ["Ġabc", "def", "ghi"]


def test_first_token_is_tokenized_without_prefix():
    tok = FakeTokenizer()
    subtokens, _ = v2_encode.subtokenize(["main", "main"], tok)
    assert subtokens == ["mai", "n", "Ġmai", "n"]


# --- GE1.2 / GE1.3: budgets ---------------------------------------------------------------


def test_budget_follows_upstream_rule():
    assert v2_encode.TRUNCATION_K == harness.truncation_constant(REF_DIR) == 3
    assert v2_encode.code_budget(0, 384, 128) == 509
    assert v2_encode.code_budget(10, 384, 128) == 499
    assert v2_encode.code_budget(500, 384, 128) == 381


def test_config_450_plus_128_rejected():
    with pytest.raises(ValueError):
        GCBV2Config(code_length=450, data_flow_length=128)


def test_400_subtokens_with_full_dfg_are_truncated_to_384_minus_specials():
    tok = FakeTokenizer()
    tokens, dfg = _synthetic(100, 128)  # 100 tokens x 4 subtokens = 400 subtokens
    enc = _assert_golden(tokens, dfg, tok)
    assert enc.n_code_subtokens == 400 and enc.n_code_kept == 381
    assert len(enc.input_ids) == 512
    assert enc.truncated is True


def test_small_input_is_not_truncated_and_has_fixed_length():
    tok = FakeTokenizer()
    lang, code = SNIPPETS["decl"]
    df = extract_dfg_v2(code, lang)
    enc = v2_encode.encode(df.code_tokens, df.dfg, tok)
    assert enc.truncated is False
    assert len(enc.input_ids) == len(enc.position_idx) == 512
    assert enc.n_dfg_kept == enc.n_dfg == len(df.dfg)


def test_short_code_lends_its_unused_budget_to_nodes():
    # Upstream keeps `code_length + data_flow_length - len(source)` nodes, so a short file may
    # carry more than `data_flow_length` nodes (240 code subtokens -> 270 node slots).
    tok = FakeTokenizer()
    tokens, dfg = _synthetic(60, 200)
    enc = _assert_golden(tokens, dfg, tok)
    assert enc.n_dfg_kept == 200 and enc.truncated is False


def test_excess_nodes_are_cut_in_order_and_flag_truncated():
    tok = FakeTokenizer()
    tokens, dfg = _synthetic(100, 200)  # 400 subtokens -> 381 kept, 129 node slots
    enc = _assert_golden(tokens, dfg, tok)
    assert enc.n_dfg == 200 and enc.n_dfg_kept < 200
    assert enc.source_tokens[enc.node_index : enc.node_index + enc.n_dfg_kept] == [x[0] for x in dfg[: enc.n_dfg_kept]]
    assert enc.truncated is True


# --- GE2: positions -----------------------------------------------------------------------


def test_positions_code_from_2_nodes_0_padding_1():
    tok = FakeTokenizer()
    lang, code = SNIPPETS["loop"]
    df = extract_dfg_v2(code, lang)
    enc = v2_encode.encode(df.code_tokens, df.dfg, tok)
    ni = enc.node_index
    assert enc.position_idx[:ni] == list(range(2, ni + 2))
    assert enc.position_idx[ni : ni + enc.n_dfg_kept] == [0] * enc.n_dfg_kept
    assert set(enc.position_idx[ni + enc.n_dfg_kept :]) == {1}
    assert enc.input_ids[ni : ni + enc.n_dfg_kept] == [tok.unk_token_id] * enc.n_dfg_kept


def test_node_position_does_not_depend_on_target_token():
    # GE2.2: moving a node's token does not change its position id (always 0).
    tok = FakeTokenizer()
    tokens = ["a", "b", "c", "d", "e"]
    early = v2_encode.encode(tokens, [("a", 0, "comesFrom", [], [])], tok)
    late = v2_encode.encode(tokens, [("e", 4, "comesFrom", [], [])], tok)
    assert early.position_idx == late.position_idx


# --- GE3: mask ----------------------------------------------------------------------------


def test_mask_rules_on_a_small_graph():
    tok = FakeTokenizer()
    tokens = ["int", "a", "=", "b", ";"]
    dfg = [("a", 1, "comesFrom", ["b"], [3]), ("b", 3, "comesFrom", [], [])]
    enc = v2_encode.encode(tokens, dfg, tok)
    m, ni = enc.attn_mask, enc.node_index
    assert ni == 7  # CLS + 5 code tokens + SEP
    assert m[:ni, :ni].all()  # code (incl. CLS/SEP) attends all code
    assert m[0, : ni + 2].all() and m[ni - 1, : ni + 2].all()  # CLS/SEP attend nodes
    assert m[ni, 2] and m[2, ni]  # node a <-> its token (seq position 2)
    assert m[ni, ni + 1]  # a attends its parent b
    assert not m[ni + 1, ni]  # the parent does not attend its child (upstream)
    pad = ni + 2
    assert not m[pad:, :].any() and not m[:, pad:].any()  # padding rows/cols empty


def test_isolated_node_row_is_empty_as_upstream():
    # GE3.3 deviation: upstream gives a node with no in-sequence code and no parent an empty row.
    tok = FakeTokenizer()
    tokens, _ = _synthetic(200, 0)  # 800 subtokens: the code is cut at 509
    dfg = [(tokens[150], 150, "comesFrom", [], []), (tokens[199], 199, "comesFrom", [tokens[150]], [150])]
    enc = _assert_golden(tokens, dfg, tok)
    ni = enc.node_index
    assert enc.dfg_to_code[0][0] >= ni  # token 150 lies beyond the retained code
    assert not enc.attn_mask[ni, :].any()  # isolated node: no self-attention upstream
    assert enc.attn_mask[ni + 1, ni]  # its child still attends it


def test_parents_cut_from_the_sequence_are_dropped_on_reindex():
    tok = FakeTokenizer()
    tokens, dfg = _synthetic(60, 200)
    enc = v2_encode.encode(tokens, dfg, tok)
    assert all(0 <= p < enc.n_dfg_kept for parents in enc.dfg_to_dfg for p in parents)


# --- golden ------------------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(SNIPPETS))
def test_golden_fake_tokenizer_real_dfg(name):
    lang, code = SNIPPETS[name]
    df = extract_dfg_v2(code, lang)
    assert df.dfg, "fixture must have a DFG"
    _assert_golden(df.code_tokens, df.dfg, FakeTokenizer())


@pytest.mark.parametrize(
    "n_tokens,n_nodes,code_length,data_flow_length",
    [(1, 0, 384, 128), (30, 0, 384, 128), (100, 128, 384, 128), (60, 200, 384, 128), (200, 40, 384, 128), (50, 20, 64, 32), (40, 50, 256, 64)],
)
def test_golden_fake_tokenizer_synthetic(n_tokens, n_nodes, code_length, data_flow_length):
    tokens, dfg = _synthetic(n_tokens, n_nodes)
    _assert_golden(tokens, dfg, FakeTokenizer(), code_length, data_flow_length)


def test_golden_without_dfg_matches_upstream():
    lang, code = SNIPPETS["branch"]
    df = extract_dfg_v2(code, lang)
    enc = _assert_golden(df.code_tokens, [], FakeTokenizer())
    assert enc.n_dfg == 0 and not enc.truncated


@pytest.fixture(scope="module")
def real_tokenizer():
    from transformers import RobertaTokenizer

    return RobertaTokenizer.from_pretrained("microsoft/graphcodebert-base", local_files_only=True)


@pytest.mark.requires_graphcodebert
@pytest.mark.parametrize("name", sorted(SNIPPETS))
def test_golden_real_tokenizer(real_tokenizer, name):
    assert (real_tokenizer.cls_token_id, real_tokenizer.pad_token_id, real_tokenizer.sep_token_id) == (0, 1, 2)
    lang, code = SNIPPETS[name]
    df = extract_dfg_v2(code, lang)
    _assert_golden(df.code_tokens, df.dfg, real_tokenizer)


@pytest.mark.requires_graphcodebert
def test_golden_real_tokenizer_truncation(real_tokenizer):
    tokens, dfg = _synthetic(300, 150, word="variable_name_")
    enc = _assert_golden(tokens, dfg, real_tokenizer)
    assert enc.truncated
