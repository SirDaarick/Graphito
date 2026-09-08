#!/usr/bin/env python3
"""
CharCNN rápido: clasificador binario código estudiante vs referencia.
Prueba de concepto para ver si el modelo aprende a distinguirlos.
"""
import json
import random
import sys
from pathlib import Path
from collections import defaultdict

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader

# ── Config ──────────────────────────────────────────────────
MAX_LEN = 4096          # caracteres por muestra
BATCH_SIZE = 32
EPOCHS = 15
LR = 1e-3
TRAIN_SPLIT = 0.8
EMBED_DIM = 128
NUM_FILTERS = 256
KERNEL_SIZES = [3, 5, 7]  # char n-gramas
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

BASE = Path(__file__).parent
SRC_DIR = BASE / "raw" / "normalized"  # código indentado
OUT_DIR = BASE / "output"

# ── Alfabeto ────────────────────────────────────────────────
# Todos los caracteres que aparecen en código C/C++ + BCS
CHARS = sorted(set(
    " abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789"
    "!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~"
    "čćđšžČĆĐŠŽ"  # BCS diacríticos
    "\n\t\r"
))
CHAR2IDX = {c: i + 1 for i, c in enumerate(CHARS)}  # 0 = padding
VOCAB_SIZE = len(CHAR2IDX) + 1
print(f"Vocabulario: {VOCAB_SIZE} caracteres | Device: {DEVICE}")

# ── Dataset ─────────────────────────────────────────────────
def load_code(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")[:MAX_LEN * 2]
    except Exception:
        return None

def build_datasets(max_problems: int = 80):
    """Carga códigos de estudiante (label=0) y referencia (label=1)."""
    state_path = OUT_DIR / ".generation_state.json"
    if not state_path.exists():
        print("❌ No hay estado de generación. Ejecuta generar_referencias.py primero.")
        sys.exit(1)

    with open(state_path) as f:
        state = json.load(f)

    student_codes: list[str] = []
    ref_codes: list[str] = []

    problems = list(state["problems"].items())
    random.shuffle(problems)
    problems = problems[:max_problems]

    for key, info in problems:
        curso, carpeta, subcarpeta = key.split("/")
        prob_dir = SRC_DIR / curso / carpeta / subcarpeta

        # Códigos de estudiantes (máx 10 por problema)
        student_files = list(prob_dir.glob("*.c")) + list(prob_dir.glob("*.cpp"))
        random.shuffle(student_files)
        for sf in student_files[:10]:
            code = load_code(sf)
            if code:
                student_codes.append(code)

        # Códigos de referencia
        ref_dir = OUT_DIR / curso / carpeta / subcarpeta
        ref_files = list(ref_dir.glob("*.c")) + list(ref_dir.glob("*.cpp"))
        for rf in ref_files:
            code = load_code(rf)
            if code:
                ref_codes.append(code)

    return student_codes, ref_codes


def char_to_tensor(code: str) -> torch.Tensor:
    ids = [CHAR2IDX.get(c, 0) for c in code[:MAX_LEN]]
    ids += [0] * (MAX_LEN - len(ids))
    return torch.tensor(ids, dtype=torch.long)


class CodeDataset(Dataset):
    def __init__(self, codes: list[str], labels: list[int]):
        self.codes = codes
        self.labels = labels

    def __len__(self):
        return len(self.codes)

    def __getitem__(self, idx):
        return char_to_tensor(self.codes[idx]), self.labels[idx]


# ── Modelo CharCNN ──────────────────────────────────────────
class CharCNN(nn.Module):
    def __init__(self):
        super().__init__()
        self.embed = nn.Embedding(VOCAB_SIZE, EMBED_DIM, padding_idx=0)

        self.convs = nn.ModuleList([
            nn.Conv1d(EMBED_DIM, NUM_FILTERS, k, padding=k // 2)
            for k in KERNEL_SIZES
        ])
        self.dropout = nn.Dropout(0.3)
        self.fc1 = nn.Linear(NUM_FILTERS * len(KERNEL_SIZES), 256)
        self.fc2 = nn.Linear(256, 2)

    def forward(self, x):
        # x: (batch, seq_len)
        x = self.embed(x)          # (batch, seq, embed)
        x = x.transpose(1, 2)      # (batch, embed, seq)

        conv_outs = []
        for conv in self.convs:
            out = F.relu(conv(x))  # (batch, filters, seq)
            out = F.max_pool1d(out, out.size(2)).squeeze(2)  # global max pool
            conv_outs.append(out)

        x = torch.cat(conv_outs, dim=1)  # (batch, filters * num_kernels)
        x = self.dropout(x)
        x = F.relu(self.fc1(x))
        x = self.dropout(x)
        x = self.fc2(x)
        return x


# ── Entrenamiento ───────────────────────────────────────────
def train(model, loader, optimizer, criterion):
    model.train()
    total_loss, correct, total = 0, 0, 0
    for x, y in loader:
        x, y = x.to(DEVICE), y.to(DEVICE)
        optimizer.zero_grad()
        out = model(x)
        loss = criterion(out, y)
        loss.backward()
        optimizer.step()
        total_loss += loss.item()
        correct += (out.argmax(1) == y).sum().item()
        total += y.size(0)
    return total_loss / len(loader), correct / total


def evaluate(model, loader):
    model.eval()
    correct, total = 0, 0
    all_preds, all_labels = [], []
    with torch.no_grad():
        for x, y in loader:
            x, y = x.to(DEVICE), y.to(DEVICE)
            out = model(x)
            pred = out.argmax(1)
            correct += (pred == y).sum().item()
            total += y.size(0)
            all_preds.extend(pred.cpu().tolist())
            all_labels.extend(y.cpu().tolist())
    return correct / total, all_preds, all_labels


def main():
    print("Cargando datos...")
    student_codes, ref_codes = build_datasets(max_problems=80)

    n_students = len(student_codes)
    n_refs = len(ref_codes)
    print(f"  Estudiantes: {n_students}  |  Referencias: {n_refs}")

    # Balancear: usar min de ambas clases
    min_size = min(n_students, n_refs)
    random.shuffle(student_codes)
    random.shuffle(ref_codes)
    student_codes = student_codes[:min_size]
    ref_codes = ref_codes[:min_size]

    # Split train/val
    split = int(min_size * TRAIN_SPLIT)
    train_codes = student_codes[:split] + ref_codes[:split]
    train_labels = [0] * split + [1] * split
    val_codes = student_codes[split:] + ref_codes[split:]
    val_labels = [0] * (min_size - split) + [1] * (min_size - split)

    # Mezclar
    train_pairs = list(zip(train_codes, train_labels))
    val_pairs = list(zip(val_codes, val_labels))
    random.shuffle(train_pairs)
    random.shuffle(val_pairs)

    train_codes_s, train_labels_s = zip(*train_pairs)
    val_codes_s, val_labels_s = zip(*val_pairs)

    train_loader = DataLoader(
        CodeDataset(list(train_codes_s), list(train_labels_s)), BATCH_SIZE, shuffle=True
    )
    val_loader = DataLoader(
        CodeDataset(list(val_codes_s), list(val_labels_s)), BATCH_SIZE
    )

    print(f"  Train: {len(train_pairs)}  |  Val: {len(val_pairs)}")

    # Modelo
    model = CharCNN().to(DEVICE)
    print(f"  Parámetros: {sum(p.numel() for p in model.parameters()):,}")

    optimizer = torch.optim.Adam(model.parameters(), lr=LR)
    criterion = nn.CrossEntropyLoss()

    print("\nEntrenando...")
    for epoch in range(1, EPOCHS + 1):
        train_loss, train_acc = train(model, train_loader, optimizer, criterion)
        val_acc, preds, labels = evaluate(model, val_loader)

        # F1 rápido
        tp = sum(1 for p, l in zip(preds, labels) if p == 1 and l == 1)
        fp = sum(1 for p, l in zip(preds, labels) if p == 1 and l == 0)
        fn = sum(1 for p, l in zip(preds, labels) if p == 0 and l == 1)
        precision = tp / (tp + fp + 1e-8)
        recall = tp / (tp + fn + 1e-8)
        f1 = 2 * precision * recall / (precision + recall + 1e-8)

        print(f"  Epoch {epoch:2d}: loss={train_loss:.4f}  "
              f"train_acc={train_acc:.3f}  val_acc={val_acc:.3f}  f1={f1:.3f}")

    print(f"\n✅ Entrenamiento completado. Mejor val_acc en última epoch: {val_acc:.3f}")
    if val_acc > 0.55:
        print("🎉 El modelo APRENDE — las referencias tienen patrones detectables.")
        print("   Continuar generando más referencias para mejorar el modelo.")
    else:
        print("🤔 El modelo no distingue bien — las referencias son muy realistas.")
        print("   O se necesitan más datos/épocas.")


if __name__ == "__main__":
    main()
