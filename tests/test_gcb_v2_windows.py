"""GraphCodeBERT v2 sliding windows (GE5, design D7/D8).

Offline: a deterministic fake tokenizer and synthetic `(code_tokens, dfg)` inputs. The DFG is
extracted once on the full file; windows only slice the subtoken sequence.
"""

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

from models.graphcodebert.v2.config import GCBV2Config
from models.graphcodebert.v2.dfg import extract_dfg_v2
from models.graphcodebert.v2.encode import code_budget, encode, subtokenize
from models.graphcodebert.v2.windows import build_windows, plan_windows, window_starts


def _load(name, path):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


FakeTokenizer = _load("gcb_v2_encode_tests", Path(__file__).resolve().parent / "test_gcb_v2_encode.py").FakeTokenizer
CFG = GCBV2Config()  # 384 / 128 / 16 -> window 382, stride 191


def _tokens(n):
    """`n` code tokens that are one fake subtoken each (<= 3 chars)."""
    return [f"t{i % 97}" for i in range(n)]


def _chain_dfg(idxs):
    """Nodes at code positions `idxs`, each a `comesFrom` of the previous one."""
    nodes = []
    prev = None
    for i in idxs:
        parents = [prev] if prev is not None else []
        nodes.append((f"t{i % 97}", i, "comesFrom", [f"t{p % 97}" for p in parents], parents))
        prev = i
    return nodes


# --- window_starts / plan_windows -----------------------------------------------------------


def test_starts_for_1000_subtokens_follow_the_spec_scenario():
    starts, capped = window_starts(1000, 382, 191, 16)
    assert starts == [0, 191, 382, 573, 618]
    assert capped is False


def test_short_sequence_gives_one_window():
    assert window_starts(100, 382, 191, 16) == ([0], False)
    assert window_starts(382, 382, 191, 16) == ([0], False)


def test_last_window_ends_at_the_last_subtoken():
    for n in (383, 573, 764, 765, 1500, 2999):
        starts, _ = window_starts(n, 382, 191, 16)
        assert starts[-1] + 382 == n
        assert starts == sorted(set(starts))
        assert all(b - a <= 191 for a, b in zip(starts, starts[1:]))


def test_cap_gives_evenly_spaced_starts_ending_at_file_end():
    n = 382 * 20
    starts, capped = window_starts(n, 382, 191, 16)
    assert capped is True and len(starts) == 16
    assert starts[0] == 0 and starts[-1] == n - 382
    gaps = np.diff(starts)
    assert gaps.max() - gaps.min() <= 1


def test_plan_fits_budget_is_a_single_upstream_input():
    plan = plan_windows(300, 40, CFG)
    assert plan.single and plan.n_windows == 1 and plan.spans == [(0, 300)]
    # Exactly at the dynamic budget still fits; one more subtoken does not.
    limit = code_budget(200, CFG.code_length, CFG.data_flow_length)
    assert plan_windows(limit, 200, CFG).single
    over = plan_windows(limit + 1, 200, CFG)
    assert not over.single and over.spans == [(0, limit + 1)]


def test_plan_long_file_uses_382_191_windows():
    plan = plan_windows(1000, 10, CFG)
    assert not plan.single and not plan.capped
    assert plan.starts == [0, 191, 382, 573, 618]
    assert all(e - s == 382 for s, e in plan.spans)


# --- build_windows --------------------------------------------------------------------------


def _arrays(enc):
    return enc.input_ids, enc.position_idx, enc.dfg_to_code, enc.dfg_to_dfg


def test_fitting_file_is_bit_identical_to_upstream_encode():
    df = extract_dfg_v2("int f(int a){ int b = a; int c = b + a; return c; }", "c")
    tok = FakeTokenizer()
    win = build_windows(df.code_tokens, df.dfg, tok, CFG)
    ref = encode(df.code_tokens, df.dfg, tok, CFG)
    assert win.n_windows == 1 and win.plan.single
    assert _arrays(win.inputs[0]) == _arrays(ref)
    assert np.array_equal(win.inputs[0].attn_mask, ref.attn_mask)
    assert win.dfg_nodes_used == ref.n_dfg_kept == len(df.dfg)
    assert win.dfg_node_count == len(df.dfg)
    assert win.truncated is False


def test_long_file_windows_restrict_nodes_shift_spans_and_reindex_parents():
    tokens = _tokens(1000)
    dfg = _chain_dfg([10, 200, 380, 381, 400, 599, 600, 700, 990])
    win = build_windows(tokens, dfg, FakeTokenizer(), CFG)
    assert win.plan.starts == [0, 191, 382, 573, 618] and win.n_windows == 5
    by_idx = {node[1]: k for k, node in enumerate(dfg)}
    for (start, end), enc, kept in zip(win.plan.spans, win.inputs, win.node_ids):
        expected = [k for k, node in enumerate(dfg) if start <= node[1] and node[1] + 1 <= end]
        assert kept == expected  # nodes fully inside the window, in idx order
        assert len(enc.input_ids) == CFG.code_length + CFG.data_flow_length
        assert enc.n_code_kept == end - start
        kept_idx = [dfg[k][1] for k in kept]
        for j, k in enumerate(kept):
            node = dfg[k]
            assert enc.dfg_to_code[j] == (node[1] - start + 1, node[1] - start + 2)  # shift -start+1
            parents = [kept_idx.index(p) for p in node[4] if p in kept_idx]
            assert enc.dfg_to_dfg[j] == parents
        assert enc.source_tokens[enc.node_index : enc.node_index + len(kept)] == [dfg[k][0] for k in kept]
    containing = [i for i, (s, e) in enumerate(win.plan.spans) if s <= 600 < e]
    placed = [i for i, kept in enumerate(win.node_ids) if by_idx[600] in kept]
    assert placed == containing == [2, 3]
    assert win.dfg_nodes_used == len(dfg)  # distinct nodes, not the per-window sum
    assert sum(len(k) for k in win.node_ids) > win.dfg_nodes_used
    assert win.truncated is False


def test_window_over_whole_file_equals_upstream_when_nothing_is_dropped():
    # The first window of a long file, with every node inside the node budget, must equal the
    # upstream encoding of the same code slice (window 46 = code_length 48 - CLS - SEP).
    small = GCBV2Config(code_length=48, data_flow_length=16)
    tokens = _tokens(60)
    dfg = _chain_dfg([1, 5, 9])
    win = build_windows(tokens, dfg, FakeTokenizer(), small)
    assert not win.plan.single and win.plan.spans == [(0, 46), (14, 60)]
    first = win.inputs[0]
    sub, _ = subtokenize(tokens[:46], FakeTokenizer())
    ref = encode(tokens[:46], dfg, FakeTokenizer(), small)
    assert len(sub) == 46
    assert _arrays(first) == _arrays(ref)
    assert np.array_equal(first.attn_mask, ref.attn_mask)


def test_dfg_nodes_used_counts_distinct_nodes_and_node_budget_truncates():
    small = GCBV2Config(code_length=48, data_flow_length=4)  # window 46, 4 node slots
    tokens = _tokens(100)
    dfg = _chain_dfg(list(range(0, 100, 2)))  # 50 nodes, about 23 per window
    win = build_windows(tokens, dfg, FakeTokenizer(), small)
    assert win.n_windows > 1
    assert all(len(k) <= 4 for k in win.node_ids)
    assert win.dfg_nodes_used == len(set().union(*map(set, win.node_ids)))
    assert win.dfg_nodes_used < len(dfg)
    assert win.dfg_node_count == 50
    assert win.truncated is True  # nodes dropped by the per-window budget


def test_cap_sets_truncated():
    small = GCBV2Config(code_length=12, data_flow_length=4, max_windows=3)  # window 10, stride 5
    win = build_windows(_tokens(200), [], FakeTokenizer(), small)
    assert win.n_windows == 3 and win.plan.capped and win.truncated
    assert win.plan.spans[-1][1] == 200


def test_ablation_without_dfg_shares_window_starts():
    tokens = _tokens(1000)
    dfg = _chain_dfg(list(range(0, 1000, 7)))
    with_dfg = build_windows(tokens, dfg, FakeTokenizer(), CFG)
    no_dfg = build_windows(tokens, dfg, FakeTokenizer(), CFG, use_dfg=False)
    assert no_dfg.plan.spans == with_dfg.plan.spans
    assert no_dfg.dfg_nodes_used == 0 and all(k == [] for k in no_dfg.node_ids)
    assert no_dfg.dfg_node_count == len(dfg)
    for a, b in zip(with_dfg.inputs, no_dfg.inputs):
        assert a.input_ids[: a.node_index] == b.input_ids[: b.node_index]  # same code context
        assert b.n_dfg_kept == 0


def test_ablation_on_a_fitting_file_keeps_the_same_code():
    df = extract_dfg_v2("int f(int a){ int b = a; return b; }", "c")
    win = build_windows(df.code_tokens, df.dfg, FakeTokenizer(), CFG, use_dfg=False)
    ref = encode(df.code_tokens, df.dfg, FakeTokenizer(), CFG)
    assert win.plan.single
    assert win.inputs[0].input_ids[: ref.node_index] == ref.input_ids[: ref.node_index]
    assert win.dfg_nodes_used == 0


def test_windows_do_not_split_by_lines():
    # Subtokens, not lines, drive windowing: one long line gives several windows.
    tokens = _tokens(1000)
    win = build_windows(tokens, [], FakeTokenizer(), CFG)
    assert win.n_windows == 5


@pytest.mark.parametrize("use_dfg", [True, False])
def test_empty_input_gives_a_single_cls_sep_input(use_dfg):
    win = build_windows([], [], FakeTokenizer(), CFG, use_dfg=use_dfg)
    assert win.n_windows == 1 and win.n_code_subtokens == 0 and win.dfg_nodes_used == 0
