#!/usr/bin/env python3
"""
contrastive_graphcodebert.py — Fine-tuning contrastivo de GraphCodeBERT

Objetivo: mejorar la discriminación entre código de distintos problemas.
Aprende a separar embeddings: mismo problema → similar, distinto problema → diferente.

Requisitos:
  pip install torch transformers peft bitsandbytes

Uso:
  python contrastive_graphcodebert.py --epochs 3 --save-to ./adaptador-contrastivo
"""

import argparse
import json
import math
import random
from collections import defaultdict
from pathlib import Path
from itertools import combinations

import torch
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
from transformers import RobertaModel, RobertaTokenizer
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
import bitsandbytes as bnb

SEED = 42
random.seed(SEED)
torch.manual_seed(SEED)
torch.backends.cudnn.deterministic = True


def collect_by_problem(data_dirs: list[Path]) -> dict[str, list[Path]]:
    """Agrupa archivos por problema (course/assignment/subproblem)."""
    problems: dict[str, list[Path]] = defaultdict(list)
    for d in data_dirs:
        d = d.resolve()
        if not d.exists():
            continue
        for ext in ("*.c", "*.cpp"):
            for fp in sorted(d.rglob(ext)):
                rel = fp.relative_to(d.parent if "raw" in str(d) else d)
                parts = rel.parts
                # key = course/assignment/subproblem (primeros 3 segmentos)
                if len(parts) >= 3:
                    key = "/".join(parts[:3])
                elif len(parts) >= 2:
                    key = "/".join(parts[:2])
                else:
                    key = parts[0]
                problems[key].append(fp)
    # Filtrar problemas con menos de 2 archivos (no generan pares positivos)
    return {k: v for k, v in problems.items() if len(v) >= 2}


class ContrastiveDataset(Dataset):
    """Genera pares (ancla, positivo, negativo) sobre la marcha."""

    def __init__(self, problems: dict[str, list[Path]], pairs_per_epoch: int = 10000):
        self.problems = problems
        self.problem_keys = list(problems.keys())
        self.pairs_per_epoch = pairs_per_epoch

    def __len__(self):
        return self.pairs_per_epoch

    def __getitem__(self, idx):
        rng = random.Random(SEED + idx)

        # Par positivo: mismo problema
        pos_key = rng.choice(self.problem_keys)
        a, b = rng.sample(self.problems[pos_key], 2)

        # Par negativo: problema distinto
        neg_key = pos_key
        while neg_key == pos_key:
            neg_key = rng.choice(self.problem_keys)
        neg_path = rng.choice(self.problems[neg_key])

        # Leer contenido
        try:
            a_text = a.read_text(encoding="utf-8", errors="replace")
            b_text = b.read_text(encoding="utf-8", errors="replace")
            neg_text = neg_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return self[(idx + 1) % len(self)]

        return (a_text, b_text, neg_text)


def collate_fn(batch, tokenizer, max_len=512):
    a_texts, b_texts, neg_texts = zip(*batch)
    enc_a = tokenizer(list(a_texts), return_tensors="pt", truncation=True,
                      max_length=max_len, padding="max_length")
    enc_b = tokenizer(list(b_texts), return_tensors="pt", truncation=True,
                      max_length=max_len, padding="max_length")
    enc_neg = tokenizer(list(neg_texts), return_tensors="pt", truncation=True,
                        max_length=max_len, padding="max_length")
    return {
        "a": enc_a, "b": enc_b, "neg": enc_neg,
    }


def contrastive_loss(emb_a, emb_b, emb_neg, margin=0.3):
    """Margin loss: el par positivo debe estar más cerca que el negativo."""
    sim_pos = F.cosine_similarity(emb_a, emb_b)
    sim_neg = F.cosine_similarity(emb_a, emb_neg)
    loss = F.relu(sim_neg - sim_pos + margin).mean()
    return loss, sim_pos.mean(), sim_neg.mean()


def get_embeddings(model, enc, device):
    """Extrae embedding [CLS] de un batch."""
    out = model(
        input_ids=enc["input_ids"].to(device),
        attention_mask=enc["attention_mask"].to(device),
    )
    return out.last_hidden_state[:, 0, :]


def main():
    parser = argparse.ArgumentParser(description="Contrastive fine-tuning de GraphCodeBERT")
    parser.add_argument("--data-dirs", nargs="+", type=Path, default=[
        Path("data/raw/src"), Path("data/output"),
    ])
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--lr", type=float, default=2e-4)
    parser.add_argument("--margin", type=float, default=0.3)
    parser.add_argument("--pairs-per-epoch", type=int, default=20000)
    parser.add_argument("--max-length", type=int, default=512)
    parser.add_argument("--lora-r", type=int, default=16)
    parser.add_argument("--lora-alpha", type=int, default=32)
    parser.add_argument("--save-to", type=Path, default=Path("modelos/weights/graphcodebert-contrastivo"))
    parser.add_argument("--val-problems", type=int, default=5,
                        help="Problemas separados para validación")
    args = parser.parse_args()

    print("=" * 60)
    print("CONTRASTIVE LEARNING — GraphCodeBERT")
    print("=" * 60)
    print(f"GPU: {torch.cuda.get_device_name(0)} ({torch.cuda.get_device_properties(0).total_memory/1e9:.1f} GB)")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # ─── DATOS ───
    print("\n[1/4] Escaneando archivos por problema...")
    all_problems = collect_by_problem(args.data_dirs)
    print(f"  Problemas encontrados: {len(all_problems)}")
    print(f"  Archivos totales: {sum(len(v) for v in all_problems.values())}")

    if len(all_problems) < args.val_problems + 2:
        print(f"  ERROR: necesitamos al menos {args.val_problems + 2} problemas")
        return

    # Separar validación
    keys = sorted(all_problems.keys())
    val_keys = set(keys[-args.val_problems:])
    train_problems = {k: v for k, v in all_problems.items() if k not in val_keys}
    val_problems = {k: v for k, v in all_problems.items() if k in val_keys}
    print(f"  Train: {len(train_problems)} problemas | Val: {len(val_problems)} problemas")

    # ─── MODELO ───
    print("\n[2/4] Cargando GraphCodeBERT + LoRA...")
    model_name = "microsoft/graphcodebert-base"
    tokenizer = RobertaTokenizer.from_pretrained(model_name)

    bnb_config = bnb.BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=torch.float16,
    )
    model = RobertaModel.from_pretrained(
        model_name,
        quantization_config=bnb_config,
        device_map="auto",
    )
    model = prepare_model_for_kbit_training(model)

    lora_config = LoraConfig(
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=0.05,
        bias="none",
        task_type=TaskType.FEATURE_EXTRACTION,
        target_modules=["query", "key", "value", "dense"],
    )
    model = get_peft_model(model, lora_config)

    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    print(f"  Params entrenables: {trainable:,} / {total:,} ({100*trainable/total:.2f}%)")

    model.train()

    # ─── DATALOADER ───
    print("\n[3/4] Preparando dataloader...")
    train_ds = ContrastiveDataset(train_problems, args.pairs_per_epoch)
    val_ds = ContrastiveDataset(val_problems, max(args.pairs_per_epoch // 5, 1000))

    def make_collate():
        return lambda b: collate_fn(b, tokenizer, args.max_length)

    train_loader = DataLoader(train_ds, batch_size=args.batch_size,
                              shuffle=False, collate_fn=make_collate(),
                              num_workers=0)
    val_loader = DataLoader(val_ds, batch_size=args.batch_size,
                            shuffle=False, collate_fn=make_collate(),
                            num_workers=0)

    # ─── ENTRENAMIENTO ───
    print("\n[4/4] Entrenando...")
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.01)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, args.epochs)
    scaler = torch.cuda.amp.GradScaler()

    args.save_to.mkdir(parents=True, exist_ok=True)
    best_val_loss = float("inf")

    for epoch in range(args.epochs):
        # ── Train ──
        model.train()
        train_loss = 0.0
        train_pos = 0.0
        train_neg = 0.0
        n_batches = 0

        for batch in train_loader:
            with torch.cuda.amp.autocast():
                emb_a = get_embeddings(model, batch["a"], device)
                emb_b = get_embeddings(model, batch["b"], device)
                emb_neg = get_embeddings(model, batch["neg"], device)
                loss, sim_pos, sim_neg = contrastive_loss(
                    emb_a, emb_b, emb_neg, args.margin
                )

            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
            optimizer.zero_grad()

            train_loss += loss.item()
            train_pos += sim_pos.item()
            train_neg += sim_neg.item()
            n_batches += 1

        scheduler.step()

        # ── Val ──
        model.eval()
        val_loss = 0.0
        val_pos = 0.0
        val_neg = 0.0
        n_val = 0

        with torch.no_grad():
            for batch in val_loader:
                emb_a = get_embeddings(model, batch["a"], device)
                emb_b = get_embeddings(model, batch["b"], device)
                emb_neg = get_embeddings(model, batch["neg"], device)
                loss, sim_pos, sim_neg = contrastive_loss(
                    emb_a, emb_b, emb_neg, args.margin
                )
                val_loss += loss.item()
                val_pos += sim_pos.item()
                val_neg += sim_neg.item()
                n_val += 1

        avg_train_l = train_loss / n_batches
        avg_val_l = val_loss / n_val
        avg_train_pos = train_pos / n_batches
        avg_train_neg = train_neg / n_batches
        avg_val_pos = val_pos / n_val
        avg_val_neg = val_neg / n_val

        gap_train = avg_train_pos - avg_train_neg
        gap_val = avg_val_pos - avg_val_neg

        print(f"  Epoch {epoch+1}/{args.epochs}: "
              f"train_loss={avg_train_l:.4f} "
              f"pos={avg_train_pos:.4f} neg={avg_train_neg:.4f} gap={gap_train:.4f} | "
              f"val_loss={avg_val_l:.4f} "
              f"pos={avg_val_pos:.4f} neg={avg_val_neg:.4f} gap={gap_val:.4f}")

        # Guardar mejor modelo
        if avg_val_l < best_val_loss:
            best_val_loss = avg_val_loss
            model.save_pretrained(str(args.save_to / "best"))
            tokenizer.save_pretrained(str(args.save_to / "best"))
            print(f"    → Mejor modelo guardado (val_loss={avg_val_l:.4f})")

    # ─── GUARDAR FINAL ───
    model.save_pretrained(str(args.save_to / "final"))
    tokenizer.save_pretrained(str(args.save_to / "final"))

    # Mergear para usar como RobertaModel standalone
    print("\nMergeando adaptador...")
    model = model.merge_and_unload()
    encoder = RobertaModel.from_pretrained(model_name)
    encoder.load_state_dict(model.roberta.state_dict(), strict=False)
    encoder.save_pretrained(str(args.save_to / "merged"))
    tokenizer.save_pretrained(str(args.save_to / "merged"))

    print(f"\n✓ Contraste completo!")
    print(f"  Gap final train: {gap_train:.4f}")
    print(f"  Gap final val:   {gap_val:.4f}")
    print(f"  Modelo: {args.save_to}/merged/")

    metrics = {
        "train_pos": avg_train_pos,
        "train_neg": avg_train_neg,
        "train_gap": gap_train,
        "val_pos": avg_val_pos,
        "val_neg": avg_val_neg,
        "val_gap": gap_val,
        "val_loss": avg_val_l,
        "margin": args.margin,
    }
    with open(args.save_to / "metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)


if __name__ == "__main__":
    # Needed for PEFT
    from peft import TaskType
    main()
