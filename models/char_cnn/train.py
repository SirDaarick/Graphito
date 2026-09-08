#!/usr/bin/env python3
"""
train.py — Entrenamiento del clasificador CharCNN para detección de código sintético.

Estrategia:
  - Clasificación binaria (humano=0, sintético=1)
  - Mini-batches, dropout, early stopping
  - Métricas: accuracy, precision, recall, F1
  - Checkpoint del mejor modelo (val loss)
  - Logs en CSV para análisis post-entrenamiento
"""

import argparse
import csv
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import torch
import torch.nn as nn
from torch.optim import Adam
from torch.optim.lr_scheduler import ReduceLROnPlateau
from torch.utils.data import DataLoader
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

from models.char_cnn.config import CharCNNConfig
from models.char_cnn.dataset import CharCNNDataset
from models.char_cnn.model import CharCNN
from models.char_cnn.preprocess import CharPreprocessor

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


def save_checkpoint(
    model: CharCNN,
    optimizer: torch.optim.Optimizer,
    epoch: int,
    val_loss: float,
    metrics: dict,
    path: Path,
    config: CharCNNConfig,
) -> None:

    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "epoch": epoch,
            "model_state_dict": model.state_dict(),
            "optimizer_state_dict": optimizer.state_dict(),
            "val_loss": val_loss,
            "metrics": metrics,
            "config": {
                "alphabet": config.alphabet,
                "seq_length": config.seq_length,
                "vocab_size": model.vocab_size,
                "embedding_dim": config.embedding_dim,
                "num_classes": config.num_classes,
            },
        },
        path,
    )


def setup_model(config: CharCNNConfig, preprocessor: CharPreprocessor) -> CharCNN:
    config.vocab_size = preprocessor.vocab_size
    model = CharCNN(config).to(DEVICE)

    dummy = torch.randint(0, config.vocab_size, (2, config.seq_length)).to(DEVICE)
    model(dummy)

    total_params = sum(p.numel() for p in model.parameters())
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"Modelo inicializado en: {DEVICE}")
    print(f"  Vocab size:   {config.vocab_size}")
    print(f"  Parámetros:   {total_params:,} total / {trainable_params:,} entrenables")
    return model


def run_training(config: CharCNNConfig, preprocessor: CharPreprocessor) -> Path:

    print(f"\n{'='*60}")
    print(f"Entrenamiento CharCNN — Graphito")
    print(f"{'='*60}\n")

    train_ds = CharCNNDataset.from_manifest(config.manifest_path, preprocessor, "train")
    val_ds = CharCNNDataset.from_manifest(config.manifest_path, preprocessor, "val")
    test_ds = CharCNNDataset.from_manifest(config.manifest_path, preprocessor, "test")

    print(f"Train: {len(train_ds)} | Val: {len(val_ds)} | Test: {len(test_ds)}")

    train_loader = DataLoader(
        train_ds, batch_size=config.batch_size, shuffle=True, num_workers=0,
    )
    val_loader = DataLoader(
        val_ds, batch_size=config.batch_size, shuffle=False, num_workers=0,
    )
    test_loader = DataLoader(
        test_ds, batch_size=config.batch_size, shuffle=False, num_workers=0,
    )

    model = setup_model(config, preprocessor)
    criterion = nn.CrossEntropyLoss()
    optimizer = Adam(
        model.parameters(),
        lr=config.learning_rate,
        weight_decay=config.weight_decay,
    )
    scheduler = ReduceLROnPlateau(
        optimizer, mode="min", factor=config.lr_factor,
        patience=config.lr_patience, verbose=True,
    )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    best_path = config.weights_dir / f"char_cnn_best_{timestamp}.pth"
    last_path = config.weights_dir / f"char_cnn_last_{timestamp}.pth"
    log_path = config.logs_dir / f"training_{timestamp}.csv"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    best_val_loss = float("inf")
    patience_counter = 0
    log_rows: list[dict] = []

    print(f"\nCheckpoints: {config.weights_dir}/")
    print(f"Logs:        {log_path}")
    print(f"\n{'Epoch':>6} {'TrainLoss':>10} {'ValLoss':>10} {'Acc':>7} {'Prec':>7} {'Rec':>7} {'F1':>7} {'Time':>8}")
    print("-" * 70)

    for epoch in range(1, config.epochs + 1):
        t_start = time.time()

        train_loss = train_epoch(model, train_loader, optimizer, criterion)
        val_loss, val_metrics, _, _ = evaluate(model, val_loader, criterion)
        scheduler.step(val_loss)

        elapsed = time.time() - t_start

        row = {
            "epoch": epoch,
            "train_loss": f"{train_loss:.4f}",
            "val_loss": f"{val_loss:.4f}",
            "accuracy": f"{val_metrics['accuracy']:.4f}",
            "precision": f"{val_metrics['precision']:.4f}",
            "recall": f"{val_metrics['recall']:.4f}",
            "f1": f"{val_metrics['f1']:.4f}",
            "lr": f"{optimizer.param_groups[0]['lr']:.6f}",
            "time_s": f"{elapsed:.1f}",
        }
        log_rows.append(row)

        print(
            f"{epoch:>6} {float(row['train_loss']):>10.4f} {float(row['val_loss']):>10.4f} "
            f"{float(row['accuracy']):>7.4f} {float(row['precision']):>7.4f} "
            f"{float(row['recall']):>7.4f} {float(row['f1']):>7.4f} {elapsed:>7.1f}s"
        )

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            patience_counter = 0
            save_checkpoint(
                model, optimizer, epoch, val_loss, val_metrics, best_path, config,
            )
            print(f"  >> Mejor modelo guardado (val_loss={val_loss:.4f})")
        else:
            patience_counter += 1

        if patience_counter >= config.early_stop_patience:
            print(f"\nEarly stopping en epoch {epoch} (paciencia={config.early_stop_patience})")
            break

    save_checkpoint(model, optimizer, epoch, val_loss, val_metrics, last_path, config)

    with open(log_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=log_rows[0].keys())
        writer.writeheader()
        writer.writerows(log_rows)

    print(f"\n--- Evaluación final (test) ---")
    checkpoint = torch.load(best_path, map_location=DEVICE, weights_only=False)
    model.load_state_dict(checkpoint["model_state_dict"])
    test_loss, test_metrics, _, _ = evaluate(model, test_loader, criterion)
    print(f"  Loss:      {test_loss:.4f}")
    for k, v in test_metrics.items():
        print(f"  {k:>10}: {v:.4f}")

    final_metrics = {
        "test_loss": test_loss,
        **{f"test_{k}": v for k, v in test_metrics.items()},
        "best_val_loss": best_val_loss,
        "best_epoch": checkpoint["epoch"],
        "total_epochs": epoch,
        "model_path": str(best_path.resolve()),
    }
    result_path = log_path.with_suffix(".json")
    with open(result_path, "w") as f:
        json.dump(final_metrics, f, indent=2)

    print(f"\nResultados:  {result_path}")
    print(f"Mejor modelo: {best_path.resolve()}")
    return best_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Entrena CharCNN para Graphito")
    parser.add_argument("--manifest", type=Path, default=None,
                        help="Ruta al dataset manifest JSON")
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--lr", type=float, default=0.001)
    parser.add_argument("--early-stop", type=int, default=7)
    parser.add_argument("--device", type=str, default=None)
    args = parser.parse_args()

    config = CharCNNConfig()
    if args.manifest:
        config.manifest_path = args.manifest
    config.batch_size = args.batch_size
    config.epochs = args.epochs
    config.learning_rate = args.lr
    config.early_stop_patience = args.early_stop

    if args.device:
        global DEVICE
        DEVICE = torch.device(args.device)

    preprocessor = CharPreprocessor(config)
    config.vocab_size = preprocessor.vocab_size

    run_training(config, preprocessor)


if __name__ == "__main__":
    main()
