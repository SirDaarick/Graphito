"""Windowed scoring shared by validation, test and inference, plus the seeded training crop.

Inputs up to `window` encoded chars are one window. Longer inputs use windows of `window` chars
every `stride`, the last one aligned to the end of the input; beyond `max_windows` the starts
are `linspace`-spaced from 0 to `n - window`. Logits and embeddings are averaged over windows and
the score is `softmax(mean logits)[1]`.
"""

from typing import Any, Optional, Sequence

import numpy as np
import torch
import torch.nn as nn

from models.char_cnn.v2.config import PAD_IDX, CharCNNV2Config
from models.char_cnn.v2.preprocess import effective_length_v2, encode, preprocess_v2
from models.evaluation.seed import stable_rng

__all__ = ["window_starts", "score_arrays", "predict_one", "random_crop"]


def window_starts(n: int, cfg: CharCNNV2Config) -> list[int]:
    """Deterministic window start offsets for an encoded length `n`.

    Every window lies inside the input and, for `n > window`, the last one ends exactly at `n`
    (with `max_windows == 1` only the first window is kept).
    """
    w, s, cap = cfg.window, cfg.stride, cfg.max_windows
    if n <= w:
        return [0]
    count = -(-(n - w) // s) + 1
    if count <= cap:
        return [i * s for i in range(count - 1)] + [n - w]
    return [int(round(x)) for x in np.linspace(0, n - w, cap)]


def _mean_window_outputs(
    model: nn.Module,
    arrays: Sequence[np.ndarray],
    device: str | torch.device,
    batch_size: int,
    cfg: CharCNNV2Config,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return per-array mean logits (N, C), mean embeddings (N, D) and window counts (N,)."""
    pieces = [
        (i, arr[start : start + cfg.window])
        for i, arr in enumerate(arrays)
        for start in window_starts(len(arr), cfg)
    ]
    n_windows = np.bincount([i for i, _ in pieces], minlength=len(arrays)).astype(np.int64)
    if not pieces:
        return np.zeros((0, cfg.num_classes)), np.zeros((0, cfg.fc_units)), n_windows

    logit_sums: Optional[np.ndarray] = None
    emb_sums: Optional[np.ndarray] = None
    was_training = model.training
    model.eval()
    try:
        with torch.no_grad():
            for b in range(0, len(pieces), batch_size):
                chunk = pieces[b : b + batch_size]
                width = max(1, max(len(window) for _, window in chunk))
                batch = np.full((len(chunk), width), PAD_IDX, dtype=np.int64)
                for row, (_, window) in enumerate(chunk):
                    batch[row, : len(window)] = window
                logits, emb = model(torch.from_numpy(batch).to(device), return_embedding=True)
                logits = logits.detach().cpu().double().numpy()
                emb = emb.detach().cpu().double().numpy()
                if logit_sums is None:
                    logit_sums = np.zeros((len(arrays), logits.shape[1]))
                    emb_sums = np.zeros((len(arrays), emb.shape[1]))
                owners = [i for i, _ in chunk]
                np.add.at(logit_sums, owners, logits)
                np.add.at(emb_sums, owners, emb)
    finally:
        model.train(was_training)

    denom = n_windows[:, None]
    return logit_sums / denom, emb_sums / denom, n_windows


def score_arrays(
    model: nn.Module,
    arrays: Sequence[np.ndarray],
    device: str | torch.device = "cpu",
    batch_size: int = 32,
    with_embeddings: bool = False,
    cfg: Optional[CharCNNV2Config] = None,
) -> tuple[np.ndarray, Optional[np.ndarray], np.ndarray]:
    """Score encoded arrays in eval mode (training mode is restored afterwards).

    Returns `(p_synth, embeddings or None, n_windows)`; `cfg` defaults to `model.config`.
    """
    cfg = cfg or model.config
    logits, emb, n_windows = _mean_window_outputs(model, arrays, device, batch_size, cfg)
    p_synth = torch.softmax(torch.from_numpy(logits), dim=1)[:, 1].numpy() if len(logits) else np.zeros(0)
    return p_synth, (emb if with_embeddings else None), n_windows


def predict_one(
    model: nn.Module, text: str, device: str | torch.device = "cpu", cfg: Optional[CharCNNV2Config] = None
) -> dict[str, Any]:
    """Preprocess, encode and score one raw text.

    `abstained` reports `effective_length < min_non_ws_chars`; the model is still run (an empty
    normalized text is scored as `[UNK]`) and placeholder policy is left to the caller.
    """
    cfg = cfg or model.config
    normalized = preprocess_v2(text)
    logits, emb, n_windows = _mean_window_outputs(
        model, [encode(normalized)], device, cfg.max_windows, cfg
    )
    probs = torch.softmax(torch.from_numpy(logits[0]), dim=0).numpy()
    effective = effective_length_v2(normalized)
    return {
        "normalized": normalized,
        "logits": logits[0],
        "probs": probs,
        "p_synthetic": float(probs[1]),
        "embedding": emb[0],
        "n_windows": int(n_windows[0]),
        "effective_length": effective,
        "abstained": effective < cfg.min_non_ws_chars,
        "empty": not normalized,
    }


def random_crop(array: np.ndarray, window: int, seed: int, key: str) -> np.ndarray:
    """Contiguous crop of at most `window` items; the offset depends only on `(seed, key)`."""
    if len(array) <= window:
        return array
    offset = stable_rng(seed, key).randint(0, len(array) - window)
    return array[offset : offset + window]
