"""Lexical baselines and embedder adapters for the GraphCodeBERT v2 evaluation (GV5)."""

import itertools
from dataclasses import replace

import numpy as np
import pytest

from eval_factory import program
from models.evaluation import dedup
from models.evaluation.normalize import shingle_tokens
from models.graphcodebert.v2 import baselines as B
from models.graphcodebert.v2 import pairs as P
from models.graphcodebert.v2.embed import EmbedResult
from test_gcb_v2_pairs import pairset, sample

CODES = [
    program("a", "c"),
    program("a", "c", mutate=4),
    program("b", "c"),
    program("c", "cpp"),
    "int main(void) { return 0; }",
]


def reference_jaccard(x, y, k=5):
    def shingles(code):
        toks = shingle_tokens(code)
        if len(toks) < k:
            return {tuple(toks)}
        return {tuple(toks[i : i + k]) for i in range(len(toks) - k + 1)}

    sx, sy = shingles(x), shingles(y)
    return len(sx & sy) / len(sx | sy)


def test_token_jaccard_equals_reference_set_jaccard():
    sets = [B.jaccard_set(c) for c in CODES]
    for i, j in itertools.combinations(range(len(CODES)), 2):
        assert dedup.jaccard(sets[i], sets[j]) == pytest.approx(reference_jaccard(CODES[i], CODES[j]), abs=1e-9)


def test_set_similarity_block_equals_pairwise_jaccard():
    sets = [B.jaccard_set(c) for c in CODES]
    sim = B.SetSimilarity(sets)(0, len(CODES))
    for i, j in itertools.product(range(len(CODES)), repeat=2):
        expected = 1.0 if i == j else dedup.jaccard(sets[i], sets[j])
        assert sim[i, j] == pytest.approx(expected, abs=1e-12)
    sub = B.SetSimilarity(sets)(1, 3)
    assert sub.shape == (2, 2) and sub[0, 1] == pytest.approx(dedup.jaccard(sets[1], sets[2]))


def test_empty_sets_score_zero():
    sim = B.SetSimilarity([np.empty(0, dtype=np.uint32), np.empty(0, dtype=np.uint32)])(0, 2)
    assert sim[0, 1] == 0.0


def test_winnowing_hand_case():
    # Schleimer et al. 2003, Fig. 2: robust winnowing (rightmost minimum), w = 4.
    h = np.array([77, 72, 42, 17, 98, 50, 17, 98, 8, 88, 67, 39, 77, 72, 42, 17, 98], dtype=np.uint64)
    assert list(B.winnow_positions(h, 4)) == [3, 6, 8, 11, 15]
    assert list(B.winnow(h, 4)) == [8, 17, 39]
    assert list(B.winnow(np.array([5, 3], dtype=np.uint64), 4)) == [3]  # shorter than a window
    assert B.winnow(np.empty(0, dtype=np.uint64), 4).size == 0


def test_positional_hashes_match_shingle_hashes_as_a_set():
    ids = dedup.token_ids(shingle_tokens(CODES[0]))
    assert np.array_equal(np.unique(B.positional_hashes(ids, 5)).astype(np.uint32), dedup.shingle_hashes(ids, 5))


def test_winnowing_similarity_bounds():
    a, b = B.winnowing_set(CODES[0]), B.winnowing_set(CODES[0])
    c = B.winnowing_set("x = y;")
    assert dedup.jaccard(a, b) == 1.0 and dedup.jaccard(a, c) == 0.0
    near = dedup.jaccard(a, B.winnowing_set(CODES[1]))
    assert 0.0 < near < 1.0


def test_all_methods_score_identical_pair_sets_per_view():
    samples = [
        sample("x1", "X", "s1", "c1", "same"),
        sample("x2", "X", "s2", "c1", "same"),
        sample("x3", "X", "s3", None, "same"),
        sample("y1", "Y", "s1"),
        sample("y2", "Y", "s2"),
    ]
    ep = P.EvalPairs.build(*pairset(samples))
    codes = CODES[: len(ep.pairs.ids)]
    methods = {
        "jaccard": B.SetSimilarity([B.jaccard_set(c) for c in codes]),
        "winnowing": B.SetSimilarity([B.winnowing_set(c) for c in codes]),
        "embedding": P.embedding_similarity(np.random.default_rng(0).normal(size=(len(codes), 4))),
    }
    scored = {name: P.score_pairs(fn, ep) for name, fn in methods.items()}
    for view in P.VIEWS:
        mask = ep.view_mask(view)
        sizes = {name: s.scores[mask].size for name, s in scored.items()}
        assert len(set(sizes.values())) == 1 and set(scored["jaccard"].map_at_r) == set(P.VIEWS)


# --- embedder adapters --------------------------------------------------------------------------


class StubV2:
    model_revision = "rev1"

    def __init__(self):
        from models.graphcodebert.v2.config import GCBV2Config

        self.config = GCBV2Config()
        self.calls = []

    def embed(self, code, language="c", use_dfg=None):
        self.calls.append((code, language, use_dfg))
        if not code:
            return EmbedResult(success=False, error="empty", use_dfg=use_dfg)
        return EmbedResult(
            success=True, cls=np.ones(4, np.float32), mean=np.full(4, 2.0, np.float32), use_dfg=use_dfg,
            n_windows=1, truncated=False, dfg_nodes_used=3 if use_dfg else 0, dfg_node_count=3,
            code_tokens_count=9, parse_errors=False,
        )


def test_v2_file_embedder_variants_keys_and_flags():
    stub = StubV2()
    dfg, nodfg = B.V2FileEmbedder(stub, use_dfg=True), B.V2FileEmbedder(stub, use_dfg=False)
    assert dfg.variant == "dfg" and nodfg.variant == "nodfg" and dfg.poolings == ("cls", "mean")
    kd, kn = dfg.key_fields(), nodfg.key_fields()
    assert kd["input_version"] == "v2" and kd["walker_version"] and kd["model_revision"] == "rev1"
    assert {k: v for k, v in kd.items() if k != "variant"} == {k: v for k, v in kn.items() if k != "variant"}
    assert "pooling" not in kd and "use_dfg" not in kd  # both poolings cached; variant carries use_dfg
    out = dfg.embed("int a;", "cpp")
    assert stub.calls[-1] == ("int a;", "cpp", True)
    assert out.success and list(out.vectors["mean"]) == [2.0] * 4
    assert out.flags["dfg_nodes_used"] == 3 and out.flags["parse_errors"] is False
    assert nodfg.embed("int a;", "c").flags["dfg_nodes_used"] == 0
    failed = dfg.embed("", "c")
    assert failed.success is False and failed.vectors == {} and failed.flags["error"] == "empty"


class StubLegacy:
    applied = True
    raise_on_init = None
    instances = []

    def __init__(self, config=None, device=None, load_adapter=False):
        if self.raise_on_init:
            raise self.raise_on_init
        self.load_adapter = load_adapter
        self.is_lora_loaded = self.applied
        self.config = config
        self.encoder = type("Enc", (), {"config": type("Cfg", (), {"_commit_hash": "legacyrev"})()})()
        StubLegacy.instances.append(self)

    def predict_code(self, code, language="c"):
        return {"embedding": [1.0, 0.0], "success": bool(code), "used_graph": True, "dfg_node_count": 2,
                "code_tokens_count": 4, "language": language}


@pytest.fixture()
def legacy_stub(monkeypatch):
    StubLegacy.applied, StubLegacy.raise_on_init, StubLegacy.instances = True, None, []
    monkeypatch.setattr(B, "LegacyGraphCodeBERTInference", StubLegacy)
    monkeypatch.setattr(B, "_peft_available", lambda: True)
    return StubLegacy


def test_legacy_adapter_loaded(legacy_stub):
    emb, status = B.load_legacy(device="cpu")
    assert legacy_stub.instances[-1].load_adapter is True
    assert status == {"status": "ok", "variant": "legacy_adapter", "reason": None, "adapter_loaded": True}
    assert emb.variant == "legacy_adapter" and emb.poolings == ("cls",)
    assert emb.key_fields()["input_version"] == "legacy" and emb.key_fields()["model_revision"] == "legacyrev"
    out = emb.embed("int a;", "c")
    assert out.success and list(out.vectors["cls"]) == [1.0, 0.0]
    assert emb.embed("", "c").success is False


def test_legacy_falls_back_to_base_when_weights_not_applied(legacy_stub):
    legacy_stub.applied = False
    emb, status = B.load_legacy(device="cpu")
    assert status["variant"] == "legacy_base" and status["reason"] == "adapter_weights_not_applied"
    assert emb.variant == "legacy_base" and status["status"] == "ok"


def test_legacy_falls_back_to_base_without_peft(legacy_stub, monkeypatch):
    legacy_stub.applied = False
    monkeypatch.setattr(B, "_peft_available", lambda: False)
    emb, status = B.load_legacy(device="cpu")
    assert status["variant"] == "legacy_base" and status["reason"] == "peft_unavailable"


def test_legacy_skipped_when_weights_unavailable(legacy_stub):
    legacy_stub.raise_on_init = OSError("model not found")
    emb, status = B.load_legacy(device="cpu")
    assert emb is None and status["status"] == "skipped" and "model not found" in status["reason"]
