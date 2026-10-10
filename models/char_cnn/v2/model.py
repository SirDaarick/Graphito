"""CharCNN architecture v2 (`ARCH_VERSION = 2`): padding-invariant, batch-independent multi-scale CNN.

Embeddings are masked, each kernel branch is one Conv1d followed by a per-position channel
LayerNorm, ReLU and the mask, and pooling (max + mean) runs over real positions only. With right
padding a zero (masked) PAD embedding equals the conv's implicit zero padding, so valid positions
see identical inputs and the output does not depend on padding or batch composition.
"""

from typing import Optional

import torch
import torch.nn as nn
import torch.nn.functional as F

from models.char_cnn.v2.config import ARCH_VERSION, PAD_IDX, CharCNNV2Config

__all__ = ["ARCH_VERSION", "CharCNNV2", "masked_pool"]


def masked_pool(features: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
    """Concatenate masked max and masked mean over the length axis.

    `features` is (B, C, L) and `mask` is (B, L) bool. Rows without any real position pool to 0.
    Returns (B, 2C).
    """
    m = mask.unsqueeze(1)
    has_any = mask.any(dim=1, keepdim=True)
    max_p = features.masked_fill(~m, float("-inf")).amax(dim=2)
    max_p = torch.where(has_any, max_p, torch.zeros_like(max_p))
    lengths = mask.sum(dim=1, keepdim=True).clamp(min=1).to(features.dtype)
    mean_p = features.masked_fill(~m, 0.0).sum(dim=2) / lengths
    return torch.cat([max_p, mean_p], dim=1)


class CharCNNV2(nn.Module):
    """Multi-scale character CNN with masked pooling; `fc1` output is the 1024-d style embedding."""

    def __init__(self, config: Optional[CharCNNV2Config] = None):
        super().__init__()
        self.config = config or CharCNNV2Config()
        cfg = self.config
        self.embedding = nn.Embedding(cfg.vocab_size, cfg.embedding_dim, padding_idx=PAD_IDX)
        self.convs = nn.ModuleList(
            nn.Conv1d(cfg.embedding_dim, filters, kernel_size=k, padding=k // 2)
            for k, filters in zip(cfg.conv_kernel_sizes, cfg.conv_filters)
        )
        self.norms = nn.ModuleList(nn.LayerNorm(filters) for filters in cfg.conv_filters)
        self.dropout = nn.Dropout(cfg.dropout)
        self.fc1 = nn.Linear(2 * sum(cfg.conv_filters), cfg.fc_units)
        self.fc2 = nn.Linear(cfg.fc_units, cfg.num_classes)

    def forward(
        self, x: torch.Tensor, return_embedding: bool = False
    ) -> torch.Tensor | tuple[torch.Tensor, torch.Tensor]:
        # x: (B, L) indices, right-padded with PAD; the mask is derived from it.
        x = x.long()
        mask = x != PAD_IDX
        mask_f = mask.unsqueeze(1).to(self.embedding.weight.dtype)
        h = self.embedding(x).transpose(1, 2) * mask_f  # (B, E, L)

        pooled = []
        for conv, norm in zip(self.convs, self.norms):
            c = norm(conv(h).transpose(1, 2)).transpose(1, 2)  # LayerNorm over channels per position
            c = F.relu(c) * mask_f
            pooled.append(masked_pool(c, mask))

        feat = self.dropout(torch.cat(pooled, dim=1))
        embedding = F.relu(self.fc1(feat))
        logits = self.fc2(embedding)
        if return_embedding:
            return logits, embedding
        return logits
