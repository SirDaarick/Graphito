"""GraphCodeBERT v2: configuration (GE1.2) and the public contract of the DFG extractor.

Construct-level DFG behaviour lives in `tests/test_dfg_parser.py` (v2 classes) and upstream
parity in `tests/test_gcb_reference_parity.py`.
"""

import dataclasses
import json
import sys

import pytest

from models.graphcodebert.v2 import config as v2_config
from models.graphcodebert.v2 import dfg as v2_dfg
from models.graphcodebert.v2.config import GCBV2Config


# --- config -------------------------------------------------------------------------------


def test_config_defaults_match_design():
    cfg = GCBV2Config()
    assert (cfg.code_length, cfg.data_flow_length, cfg.max_windows) == (384, 128, 16)
    assert cfg.pooling == "cls" and cfg.use_dfg is True
    assert cfg.attn_implementation == "eager" and cfg.dtype == "float32"
    assert v2_config.INPUT_VERSION == "v2"


def test_window_geometry_is_derived_from_code_length():
    cfg = GCBV2Config()
    assert cfg.window_code_tokens == 382
    assert cfg.window_stride == 191


def test_config_is_frozen():
    with pytest.raises(dataclasses.FrozenInstanceError):
        GCBV2Config().code_length = 10


def test_to_dict_is_json_serialisable_and_versioned():
    d = GCBV2Config().to_dict()
    json.dumps(d)
    assert d["input_version"] == "v2"
    assert d["walker_version"] == v2_dfg.WALKER_VERSION
    assert d["window_code_tokens"] == 382 and d["window_stride"] == 191


def test_to_dict_changes_with_any_field():
    assert GCBV2Config().to_dict() != GCBV2Config(max_windows=8).to_dict()


@pytest.mark.parametrize(
    "kwargs",
    [
        {"code_length": 450, "data_flow_length": 128},  # 578 > 512 positions
        {"code_length": 512, "data_flow_length": 1},
        {"code_length": 2},  # no room for a code token besides CLS/SEP
        {"data_flow_length": -1},
        {"max_windows": 0},
        {"pooling": "max"},
        {"attn_implementation": "sdpa"},
        {"dtype": "float16"},
    ],
)
def test_invalid_config_rejected(kwargs):
    with pytest.raises(ValueError):
        GCBV2Config(**kwargs)


def test_nodfg_budget_is_valid():
    cfg = GCBV2Config(code_length=512, data_flow_length=0, use_dfg=False)
    assert cfg.code_length + cfg.data_flow_length == v2_config.MAX_SEQUENCE_LENGTH


# --- DFG extractor contract ---------------------------------------------------------------


def test_walker_version():
    assert v2_dfg.WALKER_VERSION == "c-cpp-2"


def test_dataflow_fields_and_nodes_alias():
    r = v2_dfg.extract_dfg_v2("int f(){ int a = 1; int b = a; return b; }", "c")
    assert isinstance(r, v2_dfg.Dataflow)
    assert r.nodes == r.dfg
    assert r.parse_errors is False and r.dfg_error is None
    assert r.n_nodes_raw >= len(r.dfg) > 0


def test_accepts_bytes_and_str_equally():
    code = "int f(){ int a = 1; int b = a; return b; }"
    assert v2_dfg.extract_dfg_v2(code, "c") == v2_dfg.extract_dfg_v2(code.encode(), "c")


def test_unknown_language_rejected():
    with pytest.raises(ValueError):
        v2_dfg.extract_dfg_v2("int a;", "java")


def test_empty_input_gives_empty_result():
    r = v2_dfg.extract_dfg_v2("", "c")
    assert r.code_tokens == [] and r.dfg == [] and r.dfg_error is None


def test_walker_failure_keeps_tokens_and_records_error(monkeypatch):
    def boom(*args, **kwargs):
        raise RecursionError("too deep")

    monkeypatch.setattr(v2_dfg, "walk_dfg", boom)
    r = v2_dfg.extract_dfg_v2("int f(){ int a = 1; return a; }", "c")
    assert r.dfg == [] and r.n_nodes_raw == 0
    assert "RecursionError" in r.dfg_error
    assert "a" in r.code_tokens


def _nested(depth: int) -> str:
    return "int f(int a){ int b = " + "(" * depth + "a" + ")" * depth + "; return b; }"


def test_deep_nesting_within_the_guard_keeps_the_dfg():
    r = v2_dfg.extract_dfg_v2(_nested(200), "c")
    assert r.dfg_error is None
    assert any(n[0] == "b" and n[3] == ["a"] for n in r.dfg)


@pytest.mark.parametrize("depth", [v2_dfg.MAX_DEPTH + 10, 5000])
def test_nesting_beyond_the_guard_gives_max_depth_error(depth):
    # Deterministic, walker-local guard: no RecursionError, no crash, tokens kept.
    r = v2_dfg.extract_dfg_v2(_nested(depth), "c")
    assert r.dfg == [] and r.n_nodes_raw == 0
    assert r.dfg_error == "max_depth"
    assert "a" in r.code_tokens


def test_max_depth_is_configurable_per_call():
    code = _nested(40)
    assert v2_dfg.extract_dfg_v2(code, "c", max_depth=20).dfg_error == "max_depth"
    assert v2_dfg.extract_dfg_v2(code, "c", max_depth=200).dfg_error is None


def test_tree_depth_is_iterative_and_counts_levels():
    root = v2_dfg.parse_source(b"int a;", "c").root_node
    assert v2_dfg.tree_depth(root) >= 3
    deep = v2_dfg.parse_source(_nested(5000).encode(), "c").root_node
    assert v2_dfg.tree_depth(deep) > 5000


def test_process_recursion_limit_is_never_changed(monkeypatch):
    before = sys.getrecursionlimit()
    calls = []
    monkeypatch.setattr(sys, "setrecursionlimit", lambda n: calls.append(n))
    for depth in (10, 200, v2_dfg.MAX_DEPTH + 10):
        v2_dfg.extract_dfg_v2(_nested(depth), "c")
    assert calls == []
    assert sys.getrecursionlimit() == before


def test_concurrent_extraction_is_deterministic():
    import threading

    codes = [_nested(d) for d in (5, 50, 150)] + [
        "int f(int n){ int s = 0; for (int i = 0; i < n; i++) { if (i % 2) s += i; else s -= i; } return s; }",
        "struct P { int x; }; int g(struct P *p){ p->x = 3; return p->x; }",
        _nested(v2_dfg.MAX_DEPTH + 10),
    ]
    expected = [v2_dfg.extract_dfg_v2(c, "c") for c in codes]
    results: dict[int, list] = {0: [], 1: []}
    errors = []

    def run(slot):
        try:
            for _ in range(20):
                results[slot].append([v2_dfg.extract_dfg_v2(c, "c") for c in codes])
        except Exception as exc:  # pragma: no cover - surfaced by the assert below
            errors.append(exc)

    threads = [threading.Thread(target=run, args=(i,)) for i in (0, 1)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    for slot in (0, 1):
        assert len(results[slot]) == 20
        assert all(batch == expected for batch in results[slot])
