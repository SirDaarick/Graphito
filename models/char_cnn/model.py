import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Optional

from models.char_cnn.config import CharCNNConfig


class MultiScaleCharCNN(nn.Module):
    """
    Modern Multi-Scale 1D CNN for Code Authorship and AI-generated Code Detection.
    - Parallel 1D convolutions with diverse kernel sizes (3, 5, 7, 9) capturing character n-grams.
    - Global Adaptive Max + Avg Pooling: invariant to arbitrary sequence lengths,
      eliminates rigid positional bottlenecks and drastically reduces parameters.
    - Fully compatible with GraphCodeBERT 1024-dim style embeddings.
    """

    def __init__(self, config: Optional[CharCNNConfig] = None):
        super().__init__()
        self.config = config or CharCNNConfig()

        self.embedding = nn.Embedding(
            self.config.vocab_size, self.config.embedding_dim, padding_idx=0
        )

        self.convs = nn.ModuleList([
            nn.Sequential(
                nn.Conv1d(
                    self.config.embedding_dim,
                    out_channels,
                    kernel_size=k,
                    padding=k // 2,
                ),
                nn.BatchNorm1d(out_channels),
                nn.ReLU(inplace=True),
            )
            for k, out_channels in zip(
                self.config.conv_kernel_sizes, self.config.conv_filters
            )
        ])

        total_channels = sum(self.config.conv_filters)
        pooled_dim = total_channels * 2  # MaxPool + AvgPool

        latent_dim = self.config.fc_units[0] if self.config.fc_units else 1024
        self.fc1 = nn.Linear(pooled_dim, latent_dim)
        self.bn_fc1 = nn.BatchNorm1d(latent_dim)
        self.fc2 = nn.Linear(latent_dim, self.config.num_classes)

        self.dropout = nn.Dropout(self.config.dropout)

    def forward(
        self, x: torch.Tensor, return_embedding: bool = False
    ) -> torch.Tensor | tuple[torch.Tensor, torch.Tensor]:
        # x: (batch_size, seq_len)
        x = self.embedding(x)  # (batch_size, seq_len, embed_dim)
        x = x.transpose(1, 2)  # (batch_size, embed_dim, seq_len)

        pooled_feats: list[torch.Tensor] = []
        for conv in self.convs:
            c = conv(x)
            max_p = F.adaptive_max_pool1d(c, 1).squeeze(2)
            avg_p = F.adaptive_avg_pool1d(c, 1).squeeze(2)
            pooled_feats.extend([max_p, avg_p])

        feat = torch.cat(pooled_feats, dim=1)

        feat = self.dropout(feat)
        if feat.size(0) > 1 or not self.training:
            embedding = self.dropout(F.relu(self.bn_fc1(self.fc1(feat))))
        else:
            embedding = self.dropout(F.relu(self.fc1(feat)))
        logits = self.fc2(embedding)

        if return_embedding:
            return logits, embedding
        return logits

    @property
    def vocab_size(self) -> int:
        return self.config.vocab_size


# Aliases for backward compatibility
CharCNN = MultiScaleCharCNN
ParallelCharCNN = MultiScaleCharCNN

