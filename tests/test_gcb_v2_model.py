"""GraphCodeBERT v2 encoder forward (GE4, design D5/D6).

Offline on a tiny random `RobertaConfig` (2 layers, eager, CPU): the graph-guided mask is honoured,
node embeddings are the mean of aligned code word embeddings, token-type and position embeddings
are added by Hugging Face, and the hidden states equal the vendored upstream `model.py` forward.
"""

import copy
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch
import transformers
from transformers import RobertaConfig, RobertaModel

from models.graphcodebert.v2 import model as v2_model
from models.graphcodebert.v2.config import GCBV2Config
from models.graphcodebert.v2.dfg import extract_dfg_v2
from models.graphcodebert.v2.encode import encode

REF_DIR = Path(__file__).resolve().parent / "reference" / "graphcodebert"
CFG = GCBV2Config(code_length=48, data_flow_length=16)  # L = 64
ATOL = 1e-6
TRANSFORMERS_MAJOR = int(transformers.__version__.split(".")[0])
# transformers 5.x expands a 3D mask to 5D inside `masking_utils.sdpa_mask` and fails there.
RAW_3D_MASK_ERROR = r"expand\(.*number of sizes provided"


def _load(name, path):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


harness = _load("gcb_reference_harness", REF_DIR / "harness.py")
FakeTokenizer = _load("gcb_v2_encode_tests", Path(__file__).resolve().parent / "test_gcb_v2_encode.py").FakeTokenizer


def _tiny_roberta(seed=0, attn="eager", **overrides) -> RobertaModel:
    torch.manual_seed(seed)
    kwargs = dict(
        vocab_size=5010,
        hidden_size=32,
        num_hidden_layers=2,
        num_attention_heads=4,
        intermediate_size=64,
        max_position_embeddings=CFG.code_length + 4,
        hidden_dropout_prob=0.1,
        attention_probs_dropout_prob=0.1,
    )
    kwargs.update(overrides)
    config = RobertaConfig(**kwargs, attn_implementation=attn)
    return RobertaModel(config, add_pooling_layer=False)  # train mode on purpose


@pytest.fixture(scope="module")
def roberta():
    return _tiny_roberta()


def _encoded(code, lang="c"):
    df = extract_dfg_v2(code, lang)
    return encode(df.code_tokens, df.dfg, FakeTokenizer(), CFG)


SNIPPET_A = "int f(int a){ int b = a; int c = b + a; return c; }"
SNIPPET_B = "int g(int n){ int t = 0; for (int i = 0; i < n; i++) t = t + i; return t; }"


# --- mask conversion ------------------------------------------------------------------------


def test_additive_mask_is_4d_zero_or_finfo_min():
    mask = torch.tensor([[[True, False], [False, True]]])
    add = v2_model.additive_mask(mask, torch.float32)
    assert add.shape == (1, 1, 2, 2) and add.dtype == torch.float32
    assert add[0, 0, 0, 0] == 0 and add[0, 0, 0, 1] == torch.finfo(torch.float32).min


def test_additive_mask_keeps_row_attends_column_orientation():
    # Asymmetric mask: row 0 may attend column 1, row 1 may not attend column 0.
    mask = torch.tensor([[[True, True, False], [False, True, False], [True, False, True]]])
    add = v2_model.additive_mask(mask, torch.float32)
    low = torch.finfo(torch.float32).min
    expected = torch.tensor([[0.0, 0.0, low], [low, 0.0, low], [0.0, low, 0.0]])
    assert torch.equal(add[0, 0], expected)


def test_mask_honoured_is_directional(roberta):
    # Position 0 attends position 3 but not position 4; position 4 attends everything. Perturbing 4
    # must leave 0 unchanged in every layer while perturbing 3 must move it.
    roberta.eval()
    L, H = 6, roberta.config.hidden_size
    torch.manual_seed(2)
    emb = torch.randn(1, L, H)
    pos = torch.arange(2, 2 + L)[None]
    mask = torch.zeros(1, L, L, dtype=torch.bool)
    mask[0, :4, :4] = True  # rows 0-3 attend 0-3 only
    mask[0, 4:, :] = True  # rows 4-5 attend everything
    with torch.no_grad():
        out = v2_model.encoder_forward(roberta, emb, pos, mask)
        p4 = emb.clone()
        p4[0, 4] = torch.randn(H)
        p3 = emb.clone()
        p3[0, 3] = torch.randn(H)
        out4 = v2_model.encoder_forward(roberta, p4, pos, mask)
        out3 = v2_model.encoder_forward(roberta, p3, pos, mask)
    assert (out4[0, :4] - out[0, :4]).abs().max() <= ATOL
    assert (out3[0, 0] - out[0, 0]).abs().max() > 1e-3
    assert (out3[0, 5] - out[0, 5]).abs().max() > 1e-3  # rows 4-5 see position 3


# --- GE4.3: mask honoured -------------------------------------------------------------------


def test_mask_honoured_block_mask(roberta):
    roberta.eval()
    L, H = 10, roberta.config.hidden_size
    torch.manual_seed(1)
    emb = torch.randn(1, L, H)
    pos = torch.arange(2, 2 + L)[None]
    mask = torch.zeros(1, L, L, dtype=torch.bool)
    mask[0, :5, :5] = True  # positions 0-4 never see 5-9, in any layer
    mask[0, 5:, 5:] = True
    perturbed = emb.clone()
    perturbed[0, 7] = torch.randn(H)
    with torch.no_grad():
        out = v2_model.encoder_forward(roberta, emb, pos, mask)
        out_p = v2_model.encoder_forward(roberta, perturbed, pos, mask)
        full = torch.ones_like(mask)
        ctl = v2_model.encoder_forward(roberta, emb, pos, full)
        ctl_p = v2_model.encoder_forward(roberta, perturbed, pos, full)
    assert (out_p[0, :5] - out[0, :5]).abs().max() <= ATOL  # protected positions unchanged
    assert (out_p[0, 7] - out[0, 7]).abs().max() > 1e-3
    assert (ctl_p[0, :5] - ctl[0, :5]).abs().max() > 1e-3  # full-mask control does change


def test_mask_honoured_on_an_encoded_input(roberta):
    # Padding columns are attended by no code/node row, so changing padding ids must not move any
    # non-padding output; with a full mask it does.
    roberta.eval()
    enc = _encoded(SNIPPET_A)
    ids, pos, mask = v2_model.batch_tensors([enc])
    real = pos[0] != 1
    ids_p = ids.clone()
    ids_p[0, ~real] = 777
    with torch.no_grad():
        out = v2_model.forward_hidden(roberta, ids, pos, mask)
        out_p = v2_model.forward_hidden(roberta, ids_p, pos, mask)
        full = torch.ones_like(mask)
        ctl = v2_model.forward_hidden(roberta, ids, pos, full)
        ctl_p = v2_model.forward_hidden(roberta, ids_p, pos, full)
    assert (out_p[0, real] - out[0, real]).abs().max() <= ATOL
    assert (ctl_p[0, real] - ctl[0, real]).abs().max() > 1e-3


def test_3d_mask_is_rejected_or_equivalent_to_4d(roberta):
    # transformers 5.14 raises on a 3D mask (upstream model.py passes one); if a later version
    # accepts it, it must equal the explicit 4D additive form we pass.
    roberta.eval()
    enc = _encoded(SNIPPET_A)
    ids, pos, mask = v2_model.batch_tensors([enc])
    assert not bool(mask.all())  # an all-True mask is skipped by HF and would prove nothing
    with torch.no_grad():
        embeds = v2_model.node_input_embeddings(roberta.embeddings.word_embeddings, ids, pos, mask)
        out4 = v2_model.encoder_forward(roberta, embeds, pos, mask)

        def raw_3d():
            return roberta(inputs_embeds=embeds, attention_mask=mask, position_ids=pos, token_type_ids=torch.zeros_like(pos))[0]

        if TRANSFORMERS_MAJOR >= 5:
            with pytest.raises(RuntimeError, match=RAW_3D_MASK_ERROR):
                raw_3d()
        else:
            assert (raw_3d() - out4).abs().max() <= ATOL


def test_bool_4d_mask_is_not_used_because_eager_adds_it(roberta):
    # Documents why the mask is converted to additive form: eager adds a 4D bool mask as 0/1.
    roberta.eval()
    enc = _encoded(SNIPPET_A)
    ids, pos, mask = v2_model.batch_tensors([enc])
    with torch.no_grad():
        embeds = v2_model.node_input_embeddings(roberta.embeddings.word_embeddings, ids, pos, mask)
        out4 = v2_model.encoder_forward(roberta, embeds, pos, mask)
        bool4 = roberta(inputs_embeds=embeds, attention_mask=mask[:, None], position_ids=pos)[0]
    assert (bool4 - out4).abs().max() > 1e-3


# --- GE4.1: node embeddings -----------------------------------------------------------------


def test_node_embedding_is_mean_of_aligned_word_embeddings():
    # Spec scenario: a node aligned to subtokens 3 and 4.
    word = torch.nn.Embedding(20, 4)
    ids = torch.tensor([[0, 5, 6, 7, 8, 2, 3, 3, 1]])
    pos = torch.tensor([[2, 3, 4, 5, 6, 7, 0, 0, 1]])
    mask = torch.zeros(1, 9, 9, dtype=torch.bool)
    mask[0, 6, 3:5] = True  # node 0 <- subtokens 3, 4
    # node 1 (row 7) has no aligned code: upstream gives it 0 (the +1e-10 rule)
    with torch.no_grad():
        embeds = v2_model.node_input_embeddings(word, ids, pos, mask)
        w = word.weight
    assert torch.allclose(embeds[0, 6], (w[7] + w[8]) / 2, atol=ATOL)
    assert torch.allclose(embeds[0, 7], torch.zeros(4))
    assert torch.equal(embeds[0, :6], w[ids[0, :6]])  # code tokens keep their word embeddings
    assert torch.equal(embeds[0, 8], w[1])  # padding keeps the pad embedding


def test_node_embedding_on_encoded_input_uses_its_code_span(roberta):
    enc = _encoded(SNIPPET_A)
    ids, pos, mask = v2_model.batch_tensors([enc])
    with torch.no_grad():
        embeds = v2_model.node_input_embeddings(roberta.embeddings.word_embeddings, ids, pos, mask)
        w = roberta.embeddings.word_embeddings.weight
    for k, (a, b) in enumerate(enc.dfg_to_code):
        expected = w[ids[0, a:b]].mean(0)
        assert torch.allclose(embeds[0, enc.node_index + k], expected, atol=1e-5)


# --- GE4.2: HF adds token-type and position embeddings --------------------------------------


def test_token_type_and_position_embeddings_are_added_by_hf(roberta):
    roberta.eval()
    enc = _encoded(SNIPPET_A)
    ids, pos, mask = v2_model.batch_tensors([enc])
    captured = {}
    handle = roberta.embeddings.register_forward_hook(lambda m, i, o: captured.setdefault("emb", o))
    try:
        with torch.no_grad():
            v2_model.forward_hidden(roberta, ids, pos, mask)
            e = roberta.embeddings
            embeds = v2_model.node_input_embeddings(e.word_embeddings, ids, pos, mask)
            manual = e.LayerNorm(embeds + e.token_type_embeddings.weight[0] + e.position_embeddings(pos))
            without_tt = e.LayerNorm(embeds + e.position_embeddings(pos))
    finally:
        handle.remove()
    assert torch.allclose(captured["emb"], manual, atol=1e-5)
    assert (captured["emb"] - without_tt).abs().max() > 1e-3  # token type really contributes


def test_changing_token_type_embedding_changes_output():
    model = _tiny_roberta(seed=3).eval()
    enc = _encoded(SNIPPET_A)
    ids, pos, mask = v2_model.batch_tensors([enc])
    with torch.no_grad():
        before = v2_model.forward_hidden(model, ids, pos, mask)
        model.embeddings.token_type_embeddings.weight[0] += torch.randn(model.config.hidden_size)
        after = v2_model.forward_hidden(model, ids, pos, mask)
    assert (after - before).abs().max() > 1e-3


# --- GE4.4: refuse when the mask cannot be honoured -----------------------------------------


def test_non_eager_attention_is_refused():
    with pytest.raises(v2_model.MaskNotHonouredError):
        v2_model.GraphCodeBERTV2Encoder(_tiny_roberta(attn="sdpa"))


def test_mask_probe_raises_when_the_mask_is_ignored(monkeypatch):
    model = _tiny_roberta()
    real_forward = model.forward

    def ignore_mask(*args, **kwargs):
        kwargs["attention_mask"] = None
        return real_forward(*args, **kwargs)

    monkeypatch.setattr(model, "forward", ignore_mask)
    with pytest.raises(v2_model.MaskNotHonouredError):
        v2_model.check_mask_honoured(model)


def test_mask_probe_passes_on_eager_roberta():
    v2_model.check_mask_honoured(_tiny_roberta())


# --- encoder wrapper ------------------------------------------------------------------------


def test_encoder_is_eval_fp32_deterministic_and_batched():
    model = _tiny_roberta(seed=5)
    assert model.training
    encoder = v2_model.GraphCodeBERTV2Encoder(model, batch_size=1)
    assert not model.training
    inputs = [_encoded(SNIPPET_A), _encoded(SNIPPET_B), _encoded(SNIPPET_A)]
    first = encoder.encode(inputs)
    second = encoder.encode(inputs)
    assert first.shape == (3, CFG.code_length + CFG.data_flow_length, model.config.hidden_size)
    assert first.dtype == torch.float32 and not first.requires_grad
    assert torch.equal(first, second)
    assert torch.allclose(first[0], first[2], atol=ATOL)
    batched = v2_model.GraphCodeBERTV2Encoder(model, batch_size=16).encode(inputs)
    assert torch.allclose(first, batched, atol=1e-5)


def test_empty_batch_gives_empty_tensor():
    encoder = v2_model.GraphCodeBERTV2Encoder(_tiny_roberta())
    out = encoder.encode([])
    assert out.shape[0] == 0


# --- golden: upstream model.py --------------------------------------------------------------


def _extended_mask_4x(mask: torch.Tensor, dtype: torch.dtype) -> torch.Tensor:
    """Independent reference for transformers 4.x `get_extended_attention_mask` on a 3D mask:
    `[B, L, L]` -> `[B, 1, L, L]`, 0.0 where row attends column, `finfo(dtype).min` elsewhere.
    Built element by element from the documented semantics, not from `additive_mask`."""
    b, rows, cols = mask.shape
    low = torch.finfo(dtype).min
    out = torch.empty(b, 1, rows, cols, dtype=dtype)
    for i in range(b):
        for r in range(rows):
            for c in range(cols):
                out[i, 0, r, c] = 0.0 if bool(mask[i, r, c]) else low
    return out


class _Roberta4xShim(torch.nn.Module):
    """`encoder.roberta` as upstream saw it under transformers 4.x: the 3D bool mask expanded to
    a 4D additive mask by `_extended_mask_4x` (independent of the code under test)."""

    def __init__(self, roberta):
        super().__init__()
        self.inner = roberta
        self.embeddings = roberta.embeddings

    def forward(self, inputs_embeds, attention_mask, position_ids, token_type_ids):
        extended = _extended_mask_4x(attention_mask, inputs_embeds.dtype).to(inputs_embeds.device)
        return self.inner(inputs_embeds=inputs_embeds, attention_mask=extended, position_ids=position_ids, token_type_ids=token_type_ids)


def test_reference_4x_mask_matches_additive_mask():
    gen = torch.Generator().manual_seed(7)
    mask = torch.rand(2, 5, 5, generator=gen) > 0.5
    assert torch.equal(_extended_mask_4x(mask, torch.float32), v2_model.additive_mask(mask, torch.float32))


class _Capture(torch.nn.Module):
    def forward(self, features, **kwargs):
        self.features = features
        return features[:, 0, :]


def test_hidden_states_equal_upstream_model_forward(roberta):
    roberta.eval()
    Model = harness.load_upstream_model_class()
    upstream = Model(SimpleNamespace(roberta=_Roberta4xShim(roberta)), roberta.config, FakeTokenizer(), SimpleNamespace())
    upstream.classifier = _Capture()
    upstream.eval()
    a, b = _encoded(SNIPPET_A), _encoded(SNIPPET_B)
    ids, pos, mask = v2_model.batch_tensors([a, b])
    with torch.no_grad():
        upstream(ids[:1], pos[:1], mask[:1], ids[1:], pos[1:], mask[1:])
        expected = upstream.classifier.features  # interleaved pairs: [a, b]
        got = v2_model.forward_hidden(roberta, ids, pos, mask)
    assert expected.shape == got.shape
    assert (expected - got).abs().max() <= ATOL


def test_upstream_model_forward_fails_loudly_with_a_raw_3d_mask_on_this_transformers(roberta):
    # Evidence for design D5: passing upstream's 3D mask unchanged does not silently attend
    # everything; it raises (or, on a version that accepts it, matches the 4D path).
    roberta.eval()
    Model = harness.load_upstream_model_class()
    upstream = Model(SimpleNamespace(roberta=roberta), roberta.config, FakeTokenizer(), SimpleNamespace())
    upstream.classifier = _Capture()
    upstream.eval()
    a = _encoded(SNIPPET_A)
    ids, pos, mask = v2_model.batch_tensors([a, a])
    with torch.no_grad():
        if TRANSFORMERS_MAJOR >= 5:
            with pytest.raises(RuntimeError, match=RAW_3D_MASK_ERROR):
                upstream(ids[:1], pos[:1], mask[:1], ids[1:], pos[1:], mask[1:])
            return
        upstream(ids[:1], pos[:1], mask[:1], ids[1:], pos[1:], mask[1:])
        got = v2_model.forward_hidden(roberta, ids, pos, mask)
    assert (upstream.classifier.features - got).abs().max() <= ATOL


# --- real weights ---------------------------------------------------------------------------


@pytest.mark.requires_graphcodebert
def test_real_model_loads_offline_and_honours_the_mask():
    from transformers import RobertaTokenizer

    tok = RobertaTokenizer.from_pretrained("microsoft/graphcodebert-base", local_files_only=True)
    encoder = v2_model.GraphCodeBERTV2Encoder.from_pretrained(local_files_only=True)
    assert encoder.roberta.config._attn_implementation == "eager"
    df = extract_dfg_v2(SNIPPET_B, "c")
    enc = encode(df.code_tokens, df.dfg, tok)
    out = encoder.encode([enc])
    assert out.shape == (1, 512, 768)
    assert torch.isfinite(out).all()
