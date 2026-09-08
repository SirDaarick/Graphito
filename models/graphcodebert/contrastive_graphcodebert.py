#!/usr/bin/env python3
"""
contrastive_graphcodebert.py — Fine-tuning contrastivo de GraphCodeBERT con DFG

Objetivo:
  Entrena un adaptador LoRA para que GraphCodeBERT distinga programas semánticamente
  equivalentes (incluso con punteros y renombrado) de programas con lógica distinta,
  utilizando el Grafo de Flujo de Datos (DFG) durante el entrenamiento.

Uso:
  python models/graphcodebert/contrastive_graphcodebert.py --epochs 2 --pairs-per-epoch 500
"""

import argparse
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

# Insert project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import torch
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
from transformers import RobertaModel, RobertaTokenizer
from peft import LoraConfig, get_peft_model, TaskType

from models.graphcodebert.config import GraphCodeBERTConfig
from models.graphcodebert.inference import GraphCodeBERTInference

SEED = 42
random.seed(SEED)
torch.manual_seed(SEED)
if torch.cuda.is_available():
    torch.cuda.manual_seed_all(SEED)


def collect_by_problem(data_dirs: list[Path]) -> dict[str, list[Path]]:
    """Agrupa archivos por problema (course/assignment/subproblem)."""
    problems: dict[str, list[Path]] = defaultdict(list)
    for d in data_dirs:
        d = d.resolve()
        if not d.exists():
            continue
        for ext in ("*.c", "*.cpp"):
            for fp in sorted(d.rglob(ext)):
                try:
                    rel = fp.relative_to(d.parent if "raw" in str(d) else d)
                    parts = rel.parts
                    if len(parts) >= 3:
                        key = "/".join(parts[:3])
                    elif len(parts) >= 2:
                        key = "/".join(parts[:2])
                    else:
                        key = parts[0]
                    problems[key].append(fp)
                except Exception:
                    continue
    return {k: v for k, v in problems.items() if len(v) >= 2}


class ContrastiveGraphDataset(Dataset):
    """Genera tripletas (ancla, positivo, negativo) a partir de problemas C/C++."""

    def __init__(self, problems: dict[str, list[Path]], pairs_per_epoch: int = 500):
        self.problems = problems
        self.problem_keys = list(problems.keys())
        self.pairs_per_epoch = pairs_per_epoch

    def __len__(self):
        return self.pairs_per_epoch

    def __getitem__(self, idx):
        rng = random.Random(SEED + idx)

        # Positivo: dos envíos de estudiantes del mismo problema
        pos_key = rng.choice(self.problem_keys)
        a_path, b_path = rng.sample(self.problems[pos_key], 2)

        # Negativo: un envío de un problema completamente distinto
        neg_key = pos_key
        while neg_key == pos_key:
            neg_key = rng.choice(self.problem_keys)
        neg_path = rng.choice(self.problems[neg_key])

        try:
            a_text = a_path.read_text(encoding="utf-8", errors="replace")[:2000]
            b_text = b_path.read_text(encoding="utf-8", errors="replace")[:2000]
            neg_text = neg_path.read_text(encoding="utf-8", errors="replace")[:2000]
        except Exception:
            return self[(idx + 1) % len(self)]

        return {"a": a_text, "b": b_text, "neg": neg_text}


def embed_code_tensor(engine: GraphCodeBERTInference, code: str) -> torch.Tensor:
    """Extrae el embedding [CLS] con gradientes activos a través de LoRA y DFG."""
    dfg_result = engine._dfg_extractor.parse_code(code, "c")
    tokens = dfg_result.code_tokens
    edges = dfg_result.dfg_edges
    use_graph = dfg_result.success and len(tokens) > 0 and len(edges) > 0

    input_ids, position_idx, graph_mask_4d = engine._build_graph_aware_input(
        tokens, edges if use_graph else []
    )

    code_len = (input_ids[0] != engine.tokenizer.pad_token_id).sum().item()
    num_dfg = (input_ids[0] == engine.tokenizer.unk_token_id).sum().item()
    real_code_len = code_len - num_dfg

    token_embeds = engine.encoder.embeddings.word_embeddings(input_ids.to(engine.device))
    pos_embeds = engine.encoder.embeddings.position_embeddings(position_idx.to(engine.device))

    if use_graph:
        token_embeds = engine._inject_dfg_embeddings(
            token_embeds, tokens, edges, code_len=real_code_len, num_dfg=num_dfg
        )

    embeds = token_embeds + pos_embeds
    embeds = engine.encoder.embeddings.LayerNorm(embeds)
    embeds = engine.encoder.embeddings.dropout(embeds)

    out = engine.encoder.encoder(
        hidden_states=embeds,
        attention_mask=graph_mask_4d.to(engine.device),
    )
    cls_embedding = out.last_hidden_state[:, 0, :]
    return F.normalize(cls_embedding, p=2, dim=-1)


def main():
    parser = argparse.ArgumentParser(description="Contrastive fine-tuning de GraphCodeBERT con DFG")
    parser.add_argument("--data-dirs", nargs="+", type=Path, default=[Path("data/raw/src")])
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--margin", type=float, default=0.3)
    parser.add_argument("--pairs-per-epoch", type=int, default=300)
    parser.add_argument("--lora-r", type=int, default=8)
    parser.add_argument("--lora-alpha", type=int, default=16)
    parser.add_argument("--save-to", type=Path, default=Path("modelos/weights/graphcodebert-contrastivo"))
    args = parser.parse_args()

    print("=" * 60)
    print("CONTRASTIVE LEARNING (GRAPH-GUIDED) — GraphCodeBERT")
    print("=" * 60)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if device.type == "cuda":
        print(f"GPU: {torch.cuda.get_device_name(0)} ({torch.cuda.get_device_properties(0).total_memory/1e9:.1f} GB)")
    else:
        print("Dispositivo: CPU")

    # 1. Dataset
    print("\n[1/4] Escaneando problemas de código C/C++...")
    all_problems = collect_by_problem(args.data_dirs)
    print(f"  Problemas encontrados: {len(all_problems)}")
    print(f"  Archivos totales: {sum(len(v) for v in all_problems.values())}")

    keys = sorted(all_problems.keys())
    val_keys = set(keys[-3:])
    train_problems = {k: v for k, v in all_problems.items() if k not in val_keys}
    val_problems = {k: v for k, v in all_problems.items() if k in val_keys}

    train_ds = ContrastiveGraphDataset(train_problems, args.pairs_per_epoch)
    val_ds = ContrastiveGraphDataset(val_problems, max(args.pairs_per_epoch // 5, 50))

    # 2. Engine + LoRA
    print("\n[2/4] Inicializando GraphCodeBERTInference con DFG + LoRA...")
    engine = GraphCodeBERTInference(device=device)

    lora_config = LoraConfig(
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=0.05,
        bias="none",
        task_type=TaskType.FEATURE_EXTRACTION,
        target_modules=["query", "key", "value", "dense"],
    )
    engine.encoder = get_peft_model(engine.encoder, lora_config)
    trainable = sum(p.numel() for p in engine.encoder.parameters() if p.requires_grad)
    total = sum(p.numel() for p in engine.encoder.parameters())
    print(f"  Parámetros entrenables LoRA: {trainable:,} / {total:,} ({100*trainable/total:.2f}%)")

    # 3. Optimizador
    optimizer = torch.optim.AdamW(engine.encoder.parameters(), lr=args.lr, weight_decay=0.01)
    args.save_to.mkdir(parents=True, exist_ok=True)

    # 4. Loop de entrenamiento
    print("\n[3/4] Entrenando con Triplet Margin Loss...")
    best_val_gap = -1.0

    for epoch in range(args.epochs):
        engine.encoder.train()
        train_loss = 0.0
        train_pos = 0.0
        train_neg = 0.0

        for i in range(len(train_ds)):
            item = train_ds[i]
            optimizer.zero_grad()

            emb_a = embed_code_tensor(engine, item["a"])
            emb_b = embed_code_tensor(engine, item["b"])
            emb_neg = embed_code_tensor(engine, item["neg"])

            sim_pos = (emb_a * emb_b).sum(dim=-1)
            sim_neg = (emb_a * emb_neg).sum(dim=-1)
            loss = F.relu(sim_neg - sim_pos + args.margin).mean()

            loss.backward()
            optimizer.step()

            train_loss += loss.item()
            train_pos += sim_pos.item()
            train_neg += sim_neg.item()

            if (i + 1) % 50 == 0:
                print(f"  Paso {i+1}/{len(train_ds)}: loss={train_loss/(i+1):.4f} pos={train_pos/(i+1):.4f} neg={train_neg/(i+1):.4f}")

        # Validación
        engine.encoder.eval()
        val_pos = 0.0
        val_neg = 0.0
        with torch.no_grad():
            for j in range(len(val_ds)):
                v_item = val_ds[j]
                v_a = embed_code_tensor(engine, v_item["a"])
                v_b = embed_code_tensor(engine, v_item["b"])
                v_neg = embed_code_tensor(engine, v_item["neg"])
                val_pos += (v_a * v_b).sum(dim=-1).item()
                val_neg += (v_a * v_neg).sum(dim=-1).item()

        avg_val_pos = val_pos / len(val_ds)
        avg_val_neg = val_neg / len(val_ds)
        val_gap = avg_val_pos - avg_val_neg
        print(f"\n→ Epoch {epoch+1} Final: Val Pos={avg_val_pos:.4f} Val Neg={avg_val_neg:.4f} Gap={val_gap:.4f}\n")

        if val_gap > best_val_gap:
            best_val_gap = val_gap
            engine.encoder.save_pretrained(str(args.save_to / "best"))
            engine.tokenizer.save_pretrained(str(args.save_to / "best"))
            print(f"  ★ Guardado mejor checkpoint en {args.save_to / 'best'}")

    # Guardar final
    engine.encoder.save_pretrained(str(args.save_to / "final"))
    engine.tokenizer.save_pretrained(str(args.save_to / "final"))
    print(f"\n[4/4] Adaptador LoRA guardado en {args.save_to / 'final'}")


if __name__ == "__main__":
    main()
