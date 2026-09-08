import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Optional

from models.char_cnn.config import CharCNNConfig


class CharCNN(nn.Module):

    def __init__(self, config: Optional[CharCNNConfig] = None):
        super().__init__()
        self.config = config or CharCNNConfig()

        self.embedding = nn.Embedding(
            self.config.vocab_size, self.config.embedding_dim, padding_idx=0
        )

        conv_blocks: list[nn.Module] = []
        in_channels = self.config.embedding_dim

        for i in range(self.config.num_conv_layers):
            out_channels = self.config.conv_filters[i]
            kernel = self.config.conv_kernel_sizes[i]
            pool = self.config.pool_sizes[i]

            conv_blocks.append(
                nn.Conv1d(in_channels, out_channels, kernel_size=kernel, padding=0)
            )
            conv_blocks.append(nn.ReLU(inplace=True))
            if pool > 0:
                conv_blocks.append(nn.MaxPool1d(kernel_size=pool))
            in_channels = out_channels

        self.conv = nn.Sequential(*conv_blocks)

        conv_output_dim = self._compute_conv_output_dim()
        self.fc1 = nn.Linear(conv_output_dim, self.config.fc_units[0])
        self.fc2 = nn.Linear(self.config.fc_units[0], self.config.fc_units[1])
        self.fc3 = nn.Linear(self.config.fc_units[1], self.config.num_classes)

        self.dropout = nn.Dropout(self.config.dropout)

    def _compute_conv_output_dim(self) -> int:
        length = self.config.seq_length
        channels = self.config.embedding_dim
        for i in range(self.config.num_conv_layers):
            kernel = self.config.conv_kernel_sizes[i]
            pool = self.config.pool_sizes[i]
            length = length - kernel + 1
            if pool > 0:
                length = length // pool
            channels = self.config.conv_filters[i]
        return channels * length

    def forward(
        self, x: torch.Tensor, return_embedding: bool = False
    ) -> torch.Tensor | tuple[torch.Tensor, torch.Tensor]:

        x = self.embedding(x)
        x = x.transpose(1, 2)

        x = self.conv(x)

        x = x.view(x.size(0), -1)

        x = self.dropout(F.relu(self.fc1(x)))
        embedding = self.dropout(F.relu(self.fc2(x)))
        logits = self.fc3(embedding)

        if return_embedding:
            return logits, embedding
        return logits

    @property
    def vocab_size(self) -> int:
        return self.config.vocab_size
