"""Upstream GraphCodeBERT encoder forward on Hugging Face transformers 5.x (design D5, D6).

Port of the vendored `GraphCodeBERT/clonedetection/model.py` forward without the pair classifier:

1. node input embedding = mean of the word embeddings of its aligned code tokens
   (`nodes & tokens & mask`, normalised with `+1e-10`); code and padding keep their word embedding;
2. `roberta(inputs_embeds, attention_mask, position_ids, token_type_ids=0)`, so Hugging Face adds
   the token-type and position embeddings, LayerNorm and dropout itself.

Upstream passes the `[B, L, L]` boolean mask and relied on transformers 4.x to expand it to a 4D
additive mask. transformers 5.14 raises on a 3D mask and *adds* a 4D boolean mask as 0/1, so the
mask is converted here to the 4.x form `[B, 1, L, L]` with 0 (attend) / `finfo(dtype).min`
(blocked), which 5.x passes through unchanged to eager attention. The encoder refuses any
non-eager attention and probes the model once: if blocked positions influence a protected one,
`MaskNotHonouredError` is raised instead of silently attending everything (GE4.4).

fp32, `eval()` and `no_grad` only; fp16 is out of scope (D6).
"""

from typing import Sequence

import numpy as np
import torch

DEFAULT_MODEL = "microsoft/graphcodebert-base"
PROBE_ATOL = 1e-5


class MaskNotHonouredError(RuntimeError):
    """The loaded model/transformers cannot apply the graph-guided mask faithfully."""


def additive_mask(mask: torch.Tensor, dtype: torch.dtype) -> torch.Tensor:
    """`[B, L, L]` bool (row attends column) -> `[B, 1, L, L]` additive (0 / `finfo.min`)."""
    if mask.dim() != 3:
        raise ValueError(f"expected a [B, L, L] mask, got shape {tuple(mask.shape)}")
    return (1.0 - mask[:, None, :, :].to(dtype)) * torch.finfo(dtype).min


def node_input_embeddings(
    word_embeddings: torch.nn.Embedding,
    input_ids: torch.Tensor,
    position_idx: torch.Tensor,
    attn_mask: torch.Tensor,
) -> torch.Tensor:
    """Upstream `model.py`: word embeddings, with each DFG node (position 0) replaced by the mean of
    the word embeddings of the code tokens (position >= 2) it attends."""
    nodes_mask = position_idx.eq(0)
    token_mask = position_idx.ge(2)
    inputs_embeddings = word_embeddings(input_ids)
    nodes_to_token_mask = nodes_mask[:, :, None] & token_mask[:, None, :] & attn_mask
    nodes_to_token_mask = nodes_to_token_mask / (nodes_to_token_mask.sum(-1) + 1e-10)[:, :, None]
    avg_embeddings = torch.einsum("abc,acd->abd", nodes_to_token_mask, inputs_embeddings)
    return inputs_embeddings * (~nodes_mask)[:, :, None] + avg_embeddings * nodes_mask[:, :, None]


def encoder_forward(roberta, inputs_embeds: torch.Tensor, position_idx: torch.Tensor, attn_mask: torch.Tensor) -> torch.Tensor:
    """Last hidden states of `roberta` with the graph-guided mask (token type 0, as upstream)."""
    return roberta(
        inputs_embeds=inputs_embeds,
        attention_mask=additive_mask(attn_mask, inputs_embeds.dtype),
        position_ids=position_idx,
        token_type_ids=torch.zeros_like(position_idx),
    )[0]


def forward_hidden(roberta, input_ids: torch.Tensor, position_idx: torch.Tensor, attn_mask: torch.Tensor) -> torch.Tensor:
    """Upstream forward up to the encoder output: `[B, L, H]` last hidden states."""
    embeds = node_input_embeddings(roberta.embeddings.word_embeddings, input_ids, position_idx, attn_mask)
    return encoder_forward(roberta, embeds, position_idx, attn_mask)


def require_eager(roberta) -> None:
    impl = getattr(roberta.config, "_attn_implementation", None)
    if impl != "eager":
        raise MaskNotHonouredError(f"attn_implementation must be 'eager' for the additive graph mask, got {impl!r}")


def check_mask_honoured(roberta, atol: float = PROBE_ATOL) -> None:
    """Probe: two attention blocks that never see each other. Perturbing an input of one block
    must leave the other block's outputs unchanged, and must move them under a full mask."""
    length, hidden = 6, roberta.config.hidden_size
    device = next(roberta.parameters()).device
    gen = torch.Generator().manual_seed(0)
    emb = torch.randn(1, length, hidden, generator=gen).to(device)
    perturbed = emb.clone()
    perturbed[0, 4] = torch.randn(hidden, generator=gen).to(device)
    pos = torch.arange(2, 2 + length, device=device)[None]
    mask = torch.zeros(1, length, length, dtype=torch.bool, device=device)
    mask[0, :3, :3] = True
    mask[0, 3:, 3:] = True
    full = torch.ones_like(mask)
    was_training = roberta.training
    roberta.eval()
    try:
        with torch.no_grad():
            blocked = (encoder_forward(roberta, perturbed, pos, mask) - encoder_forward(roberta, emb, pos, mask))[0, :3]
            control = (encoder_forward(roberta, perturbed, pos, full) - encoder_forward(roberta, emb, pos, full))[0, :3]
    finally:
        roberta.train(was_training)
    if blocked.abs().max().item() > atol or control.abs().max().item() <= atol:
        raise MaskNotHonouredError(
            "the attention mask is not honoured by this model/transformers version "
            f"(blocked change {blocked.abs().max().item():.3g}, control change {control.abs().max().item():.3g})"
        )


def batch_tensors(inputs: Sequence) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """`EncodedInput`s -> `(input_ids, position_idx, attn_mask)` tensors `[B, L]`, `[B, L]`, `[B, L, L]`."""
    ids = torch.tensor([x.input_ids for x in inputs], dtype=torch.long)
    pos = torch.tensor([x.position_idx for x in inputs], dtype=torch.long)
    mask = torch.from_numpy(np.stack([x.attn_mask for x in inputs]))
    return ids, pos, mask


class GraphCodeBERTV2Encoder:
    """Batched, deterministic fp32 encoder over `EncodedInput`s (eager attention, eval mode)."""

    def __init__(self, roberta, device: str | torch.device = "cpu", batch_size: int = 16, verify_mask: bool = True):
        require_eager(roberta)
        self.device = torch.device(device)
        self.roberta = roberta.to(device=self.device, dtype=torch.float32).eval()
        self.batch_size = max(1, int(batch_size))
        if verify_mask:
            check_mask_honoured(self.roberta)

    @classmethod
    def from_pretrained(
        cls,
        name: str = DEFAULT_MODEL,
        local_files_only: bool = False,
        device: str | torch.device = "cpu",
        batch_size: int = 16,
    ) -> "GraphCodeBERTV2Encoder":
        from transformers import RobertaModel

        roberta = RobertaModel.from_pretrained(
            name, attn_implementation="eager", local_files_only=local_files_only, add_pooling_layer=False, dtype=torch.float32
        )
        return cls(roberta, device=device, batch_size=batch_size)

    @property
    def hidden_size(self) -> int:
        return self.roberta.config.hidden_size

    def encode(self, inputs: Sequence) -> torch.Tensor:
        """Last hidden states `[N, L, H]` (CPU, fp32) for `N` encoded inputs."""
        if len(inputs) == 0:
            return torch.zeros(0, 0, self.hidden_size)
        outputs = []
        with torch.no_grad():
            for start in range(0, len(inputs), self.batch_size):
                ids, pos, mask = batch_tensors(inputs[start : start + self.batch_size])
                hidden = forward_hidden(self.roberta, ids.to(self.device), pos.to(self.device), mask.to(self.device))
                outputs.append(hidden.float().cpu())
        return torch.cat(outputs)
