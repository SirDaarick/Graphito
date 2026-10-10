#!/usr/bin/env python3
"""
train.py — legacy CharCNN training helpers; the entry point delegates to the v2 trainer.

`python -m models.char_cnn.train ...` runs `models.char_cnn.v2.train.main` with the same
arguments (see that module for flags; runs go to `runs/char_cnn/<ts>/`). The legacy loop that
wrote `models/char_cnn/weights/` and overwrote the deployed checkpoint was removed; promoting a
checkpoint is the separate, guarded `models.char_cnn.v2.promote` CLI.

`compute_metrics`, `evaluate` and `train_epoch` are kept unchanged because
`scripts/generate_tt_figures.py` and the legacy robustness tests import them.
"""

import sys
from typing import Optional, Sequence

import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

from models.char_cnn.model import CharCNN

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


def compute_metrics(y_true: list[int], y_pred: list[int]) -> dict:
    return {
        "accuracy": accuracy_score(y_true, y_pred),
        "precision": precision_score(y_true, y_pred, zero_division=0),
        "recall": recall_score(y_true, y_pred, zero_division=0),
        "f1": f1_score(y_true, y_pred, zero_division=0),
    }


def evaluate(
    model: CharCNN, dataloader: DataLoader, criterion: nn.Module
) -> tuple[float, dict, list[int], list[int]]:

    model.eval()
    total_loss = 0.0
    all_preds: list[int] = []
    all_labels: list[int] = []

    with torch.no_grad():
        for inputs, labels in dataloader:
            inputs, labels = inputs.to(DEVICE), labels.to(DEVICE)
            logits = model(inputs)
            loss = criterion(logits, labels)
            total_loss += loss.item() * inputs.size(0)
            preds = logits.argmax(dim=1).cpu().tolist()
            all_preds.extend(preds)
            all_labels.extend(labels.cpu().tolist())

    avg_loss = total_loss / len(dataloader.dataset)
    metrics = compute_metrics(all_labels, all_preds)
    return avg_loss, metrics, all_preds, all_labels


def train_epoch(
    model: CharCNN,
    dataloader: DataLoader,
    optimizer: torch.optim.Optimizer,
    criterion: nn.Module,
) -> float:

    model.train()
    total_loss = 0.0

    for inputs, labels in dataloader:
        inputs, labels = inputs.to(DEVICE), labels.to(DEVICE)
        optimizer.zero_grad()
        logits = model(inputs)
        loss = criterion(logits, labels)
        loss.backward()
        optimizer.step()
        total_loss += loss.item() * inputs.size(0)

    return total_loss / len(dataloader.dataset)


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Delegate to the v2 trainer (`models.char_cnn.v2.train.main`)."""
    from models.char_cnn.v2 import train as v2_train  # lazy: the helpers above do not need it

    return v2_train.main(argv)


if __name__ == "__main__":
    sys.exit(main())
