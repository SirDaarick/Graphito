"""Unit tests for the CharCNN v2 model and windowed scoring (tiny CPU models, synthetic inputs)."""

import json
from pathlib import Path

import numpy as np
import pytest
import torch
import torch.nn as nn

from models.char_cnn.v2.config import PAD_IDX, VOCAB_SIZE, CharCNNV2Config
from models.char_cnn.v2.model import CharCNNV2, masked_pool
from models.char_cnn.v2.scoring import predict_one, random_crop, score_arrays, window_starts

# Key names and shapes of the legacy v1 `CharCNN` (default `CharCNNConfig`, vocab 123).
V1_SHAPES = Path(__file__).resolve().parent / "fixtures" / "charcnn_v1_state_dict_shapes.json"

TINY = CharCNNV2Config(
    embedding_dim=8, conv_kernel_sizes=(3, 5), conv_filters=(4, 6), fc_units=16, dropout=0.4
)


def _tiny_model(seed: int = 0) -> CharCNNV2:
    torch.manual_seed(seed)
    return CharCNNV2(TINY).eval()


def _seq(length: int, seed: int = 1) -> torch.Tensor:
    g = torch.Generator().manual_seed(seed)
    return torch.randint(2, VOCAB_SIZE, (length,), generator=g)


def _pad(seq: torch.Tensor, extra: int) -> torch.Tensor:
    return torch.cat([seq, torch.full((extra,), PAD_IDX, dtype=seq.dtype)])


class TestModel:
    def test_has_no_batchnorm(self):
        model = CharCNNV2(TINY)
        assert not any(isinstance(m, nn.modules.batchnorm._BatchNorm) for m in model.modules())

    def test_single_dropout(self):
        model = CharCNNV2(TINY)
        assert sum(isinstance(m, nn.Dropout) for m in model.modules()) == 1

    def test_output_shapes_and_embedding(self):
        model = _tiny_model()
        x = torch.stack([_seq(20, 1), _seq(20, 2)])
        logits, emb = model(x, return_embedding=True)
        assert logits.shape == (2, 2)
        assert emb.shape == (2, 16)
        assert torch.equal(model(x), logits)

    def test_default_embedding_is_fusion_compatible(self):
        model = CharCNNV2().eval()
        _, emb = model(_seq(12).unsqueeze(0), return_embedding=True)
        assert emb.shape == (1, 1024)

    @torch.no_grad()
    def test_padding_invariance(self):
        model = _tiny_model()
        seq = _seq(300)
        base = model(seq.unsqueeze(0))
        for extra in (100, 3000):
            padded = model(_pad(seq, extra).unsqueeze(0))
            torch.testing.assert_close(padded, base, atol=1e-5, rtol=0)

    @torch.no_grad()
    def test_batch_matches_single(self):
        model = _tiny_model()
        seqs = [_seq(n, seed=n) for n in (5, 50, 300, 1)]
        width = max(len(s) for s in seqs)
        batch = torch.stack([_pad(s, width - len(s)) for s in seqs])
        logits, emb = model(batch, return_embedding=True)
        for i, s in enumerate(seqs):
            single_logits, single_emb = model(s.unsqueeze(0), return_embedding=True)
            torch.testing.assert_close(logits[i : i + 1], single_logits, atol=1e-5, rtol=0)
            torch.testing.assert_close(emb[i : i + 1], single_emb, atol=1e-5, rtol=0)

    def test_masked_pool_ignores_pad_values(self):
        torch.manual_seed(0)
        feats = torch.randn(2, 3, 6)
        mask = torch.tensor([[1, 1, 1, 0, 0, 0], [1, 1, 1, 1, 1, 0]], dtype=torch.bool)
        noisy = feats.clone()
        noisy[0, :, 3:] = 1e6
        noisy[1, :, 5:] = -1e6
        pooled = masked_pool(noisy, mask)
        torch.testing.assert_close(pooled, masked_pool(feats, mask))
        expected0 = torch.cat([feats[0, :, :3].amax(dim=1), feats[0, :, :3].mean(dim=1)])
        torch.testing.assert_close(pooled[0], expected0)
        assert pooled.shape == (2, 6)

    def test_all_pad_row_is_finite(self):
        model = _tiny_model()
        x = torch.zeros((2, 7), dtype=torch.long)
        x[0, :3] = _seq(3)
        assert torch.isfinite(model(x)).all()

    def test_batch_of_one_in_train_mode(self):
        model = _tiny_model().train()
        logits = model(_seq(30).unsqueeze(0))
        assert logits.shape == (1, 2)

    def test_accepts_uint8_input(self):
        model = _tiny_model()
        x = _seq(40).unsqueeze(0)
        torch.testing.assert_close(model(x.to(torch.uint8)), model(x))

    def test_state_dict_round_trip_strict(self):
        source = _tiny_model(seed=3)
        target = CharCNNV2(CharCNNV2Config.from_dict(source.config.to_dict()))
        target.load_state_dict(source.state_dict(), strict=True)
        x = _seq(64).unsqueeze(0)
        torch.testing.assert_close(target.eval()(x), source(x), atol=1e-6, rtol=0)

    def test_v1_model_matches_frozen_state_dict_fixture(self, tmp_path, monkeypatch):
        # The legacy config creates weights/ and logs/ relative to cwd; keep that out of the repo.
        monkeypatch.chdir(tmp_path)
        from models.char_cnn.config import CharCNNConfig
        from models.char_cnn.model import CharCNN
        from models.char_cnn.preprocess import CharPreprocessor

        frozen = json.loads(V1_SHAPES.read_text(encoding="utf-8"))
        cfg = CharCNNConfig()
        assert CharPreprocessor(cfg).vocab_size == frozen["vocab_size"]
        cfg.vocab_size = frozen["vocab_size"]
        model = CharCNN(cfg)
        assert [[k, list(v.shape)] for k, v in model.state_dict().items()] == frozen["state_dict"]

        # A state_dict built only from the frozen key names and shapes loads strictly.
        state = {
            key: torch.zeros(shape, dtype=torch.long if key.endswith("num_batches_tracked") else torch.float32)
            for key, shape in frozen["state_dict"]
        }
        model.load_state_dict(state, strict=True)


class _StubModel(nn.Module):
    """Returns logits [0, first_token / 10] and embedding [first_token, second_token] per window."""

    def __init__(self, config: CharCNNV2Config):
        super().__init__()
        self.config = config
        self.windows_seen: list[list[int]] = []

    def forward(self, x, return_embedding=False):
        self.windows_seen.extend(x.tolist())
        first = x[:, 0].float()
        logits = torch.stack([torch.zeros_like(first), first / 10], dim=1)
        emb = x[:, :2].float()
        return (logits, emb) if return_embedding else logits


STUB_CFG = CharCNNV2Config(window=8, stride=4, max_windows=3)


class TestWindows:
    @pytest.mark.parametrize(
        "n,expected",
        [
            (1, [0]),
            (4096, [0]),
            (6144, [0, 2048]),
            (6145, [0, 2048, 2049]),
            (4096 + 7 * 2048, [i * 2048 for i in range(8)]),
        ],
    )
    def test_window_starts_regular(self, n, expected):
        assert window_starts(n, CharCNNV2Config()) == expected

    @pytest.mark.parametrize("n", [4096 + 7 * 2048 + 1, 100000])
    def test_window_starts_capped_linspace(self, n):
        cfg = CharCNNV2Config()
        starts = window_starts(n, cfg)
        assert len(starts) == 8
        assert starts[0] == 0
        assert starts[-1] + cfg.window == n
        assert starts == sorted(set(starts))
        assert starts == window_starts(n, cfg)

    def test_every_window_ends_inside_input(self):
        cfg = CharCNNV2Config()
        for n in (4097, 5000, 8193, 20000, 100000):
            assert all(0 <= s and s + cfg.window <= n for s in window_starts(n, cfg))
            assert window_starts(n, cfg)[-1] + cfg.window == n

    def test_score_is_softmax_of_mean_window_logits(self):
        model = _StubModel(STUB_CFG)
        long = np.full(16, 2, dtype=np.uint8)
        long[[0, 4, 8]] = [10, 20, 60]  # window starts for n=16, window 8, stride 4
        short = np.array([30, 5, 5, 5, 5], dtype=np.uint8)
        p, emb, n_windows = score_arrays(model, [long, short], "cpu", batch_size=2, with_embeddings=True)
        assert n_windows.tolist() == [3, 1]
        mean_logit = (1.0 + 2.0 + 6.0) / 3
        expected = torch.softmax(torch.tensor([0.0, mean_logit]), dim=0)[1].item()
        mean_of_probs = np.mean([torch.sigmoid(torch.tensor(v)).item() for v in (1.0, 2.0, 6.0)])
        assert p[0] == pytest.approx(expected, abs=1e-6)
        assert abs(p[0] - mean_of_probs) > 1e-3
        assert p[1] == pytest.approx(torch.sigmoid(torch.tensor(3.0)).item(), abs=1e-6)
        np.testing.assert_allclose(emb[0], [(10 + 20 + 60) / 3, 2.0])
        np.testing.assert_allclose(emb[1], [30.0, 5.0])
        assert all(len(w) == 8 for w in model.windows_seen[:3])

    def test_score_without_embeddings(self):
        p, emb, n_windows = score_arrays(_StubModel(STUB_CFG), [np.array([20], dtype=np.uint8)], "cpu")
        assert emb is None
        assert n_windows.tolist() == [1]
        assert p.shape == (1,)

    @torch.no_grad()
    def test_score_matches_direct_forward_and_restores_mode(self):
        model = _tiny_model()
        model.train()
        arr = _seq(50).numpy().astype(np.uint8)
        p, emb, _ = score_arrays(model, [arr], "cpu", with_embeddings=True)
        assert model.training
        model.eval()
        logits, direct_emb = model(torch.from_numpy(arr).long().unsqueeze(0), return_embedding=True)
        assert p[0] == pytest.approx(torch.softmax(logits, dim=1)[0, 1].item(), abs=1e-6)
        np.testing.assert_allclose(emb[0], direct_emb[0].numpy(), atol=1e-6)

    def test_predict_one(self):
        model = _tiny_model()
        text = "int main() {\n    int total = 0;\n    for (int i = 0; i < 10; i++) total += i;\n    return total;\n}\n"
        out = predict_one(model, text)
        assert 0.0 <= out["p_synthetic"] <= 1.0
        assert isinstance(out["p_synthetic"], float)
        assert out["n_windows"] == 1
        assert out["embedding"].shape == (16,)
        assert out["logits"].shape == (2,)
        assert out["normalized"].startswith("int main() {\nint total = 0;")
        assert out["abstained"] is False
        short = predict_one(model, "int x;")
        assert short["abstained"] is True
        assert short["effective_length"] == 5

    def test_random_crop_is_deterministic_per_key(self):
        arr = np.arange(9000)
        a = random_crop(arr, 4096, seed=7, key="epoch0:crop:x.c")
        b = random_crop(arr, 4096, seed=7, key="epoch0:crop:x.c")
        assert len(a) == 4096
        np.testing.assert_array_equal(a, b)
        np.testing.assert_array_equal(a, np.arange(a[0], a[0] + 4096))
        offsets = {int(random_crop(arr, 4096, seed=7, key=f"epoch{e}:crop:x.c")[0]) for e in range(10)}
        assert len(offsets) > 1

    def test_random_crop_keeps_short_arrays(self):
        arr = np.arange(100)
        np.testing.assert_array_equal(random_crop(arr, 4096, seed=1, key="k"), arr)