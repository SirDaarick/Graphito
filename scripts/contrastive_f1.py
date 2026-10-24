"""F1 of the contrastive CodeNet experiment: `v2_norm` zero-shot baseline on CodeNet val and a
training-speed benchmark of the LoRA + InfoNCE step (guide section 3, F1).

Reads the F0 cache (`cache_<split>.pkl`, features of canonicalized code) and builds the attention mask
from it, so the baseline sees exactly the inputs the training will see.

    python scripts/contrastive_f1.py baseline            # CodeNet val: MAP@R and Accepted-vs-WA AUC
    python scripts/contrastive_f1.py speed               # LoRA r=16 + InfoNCE sequences/s and peak memory
"""

import argparse
import json
import pickle
import random
import sys
import time
from pathlib import Path
from typing import Sequence

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

CLS_ID, PAD_ID, SEP_ID = 0, 1, 2  # RoBERTa special ids (upstream hard-codes [0, 2] for the mask)
TEMPERATURE = 0.05


# --- pure helpers (tested) ----------------------------------------------------------------------


def mean_pool_positions(hidden, n_code_kept: Sequence[int]):
    """`[B, L, H]` -> `[B, H]`: mean over the code subtoken positions `1..n` (no CLS, SEP, DFG nodes
    or padding), the `mean` pooling of `models.graphcodebert.v2.embed.pool_hidden`."""
    import torch

    length = hidden.shape[1]
    pos = torch.arange(length, device=hidden.device)[None, :]
    n = torch.as_tensor(list(n_code_kept), device=hidden.device)[:, None]
    mask = ((pos >= 1) & (pos <= n)).to(hidden.dtype)
    return (hidden * mask[:, :, None]).sum(1) / mask.sum(1, keepdim=True).clamp(min=1)


def accepted_vs_wa_auc(sim: np.ndarray, problems: Sequence[str], roles: Sequence[str]) -> dict:
    """For every Accepted anchor, similarity to the other Accepted of its problem (label 1) against
    the Wrong Answer of the same problem (label 0). Pooled ROC-AUC and the mean per-problem AUC."""
    from sklearn.metrics import roc_auc_score

    problems, roles = np.asarray(problems), np.asarray(roles)
    scores, labels, per_problem = [], [], []
    for p in sorted(set(problems.tolist())):
        acc = np.flatnonzero((problems == p) & (roles == "accepted"))
        wa = np.flatnonzero((problems == p) & (roles == "wrong_answer"))
        if len(acc) < 2 or len(wa) < 1:
            continue
        s, y = [], []
        for a in acc:
            others = acc[acc != a]
            s += sim[a, others].tolist() + sim[a, wa].tolist()
            y += [1] * len(others) + [0] * len(wa)
        scores += s
        labels += y
        per_problem.append(roc_auc_score(y, s))
    if not per_problem:
        return {"pooled_auc": None, "mean_problem_auc": None, "n_problems": 0}
    return {
        "pooled_auc": float(roc_auc_score(labels, scores)),
        "mean_problem_auc": float(np.mean(per_problem)),
        "n_problems": len(per_problem),
    }


def info_nce(anchors, positives, temperature: float = TEMPERATURE):
    """Symmetric InfoNCE over L2-normalized `[B, H]` embeddings; the other items of the batch are negatives."""
    import torch
    import torch.nn.functional as F

    a, p = F.normalize(anchors, dim=-1), F.normalize(positives, dim=-1)
    logits = a @ p.T / temperature
    target = torch.arange(a.shape[0], device=a.device)
    return 0.5 * (F.cross_entropy(logits, target) + F.cross_entropy(logits.T, target))


# --- data ---------------------------------------------------------------------------------------


def load_cache(path: Path) -> list[dict]:
    return pickle.loads(path.read_bytes())


def batch_tensors(features: Sequence[dict], device):
    """Cached features -> `(input_ids, position_idx, attn_mask)` tensors on `device`."""
    import torch

    from models.graphcodebert.v2.encode import build_attention_mask

    masks = [
        build_attention_mask(f["input_ids"].tolist(), f["position_idx"].tolist(), f["dfg_to_code"], f["dfg_to_dfg"], (CLS_ID, SEP_ID))
        for f in features
    ]
    ids = torch.from_numpy(np.stack([f["input_ids"] for f in features])).long()
    pos = torch.from_numpy(np.stack([f["position_idx"] for f in features])).long()
    return ids.to(device), pos.to(device), torch.from_numpy(np.stack(masks)).to(device)


def load_roberta(device):
    import torch
    from transformers import RobertaModel

    from models.graphcodebert.v2.model import DEFAULT_MODEL

    return RobertaModel.from_pretrained(
        DEFAULT_MODEL, attn_implementation="eager", local_files_only=True, add_pooling_layer=False, dtype=torch.float32
    ).to(device)


# --- baseline -----------------------------------------------------------------------------------


def embed_rows(roberta, rows: Sequence[dict], device, batch_size: int = 16) -> np.ndarray:
    """L2-normalized `mean`-pooled embeddings `[N, H]` (float64) of cached rows, eval mode."""
    import torch

    from models.graphcodebert.v2.model import forward_hidden

    embs = []
    with torch.no_grad():
        for i in range(0, len(rows), batch_size):
            chunk = rows[i : i + batch_size]
            ids, pos, mask = batch_tensors([r["features"] for r in chunk], device)
            hidden = forward_hidden(roberta, ids, pos, mask)
            embs.append(mean_pool_positions(hidden, [r["features"]["n_code_kept"] for r in chunk]).cpu())
    return torch.nn.functional.normalize(torch.cat(embs), dim=-1).numpy().astype(np.float64)


def val_metrics(emb: np.ndarray, rows: Sequence[dict]) -> dict:
    """MAP@R among Accepted, Accepted-vs-WA AUC and the cosine statistics of the cached rows."""
    from models.logic_eval.grouping import compute_map_at_r

    sim = emb @ emb.T
    problems = [r["problem"] for r in rows]
    roles = [r["role"] for r in rows]
    acc_idx = [i for i, r in enumerate(roles) if r == "accepted"]
    map_res = compute_map_at_r(sim[np.ix_(acc_idx, acc_idx)], [problems[i] for i in acc_idx])
    eye = np.eye(len(rows), dtype=bool)
    same = np.equal.outer(problems, problems) & ~eye
    iu = np.triu_indices(len(rows), 1)
    return {
        "n_samples": len(rows),
        "n_problems": len(set(problems)),
        "map_at_r_accepted": map_res["value"],
        "map_at_r_n_queries": map_res.get("n_queries"),
        "accepted_vs_wa_auc": accepted_vs_wa_auc(sim, problems, roles),
        "cosine": {
            "mean_same_problem": float(sim[same].mean()),
            "mean_different_problem": float(sim[~same & ~eye].mean()),
            "mean_all_pairs": float(sim[iu].mean()),
        },
    }


def run_baseline(args) -> None:
    import torch

    from models.graphcodebert.v2.model import check_mask_honoured

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    rows = load_cache(args.f0 / f"cache_{args.split}.pkl")
    roberta = load_roberta(device).eval()
    check_mask_honoured(roberta)
    t0 = time.time()
    result = {
        "split": args.split,
        "input": "v2_norm, pooling mean, zero-shot",
        **val_metrics(embed_rows(roberta, rows, device, args.batch_size), rows),
        "elapsed_s": round(time.time() - t0, 1),
    }
    out = args.f0 / f"f1_baseline_{args.split}.json"
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


# --- speed --------------------------------------------------------------------------------------


def run_speed(args) -> None:
    import torch
    from peft import LoraConfig, get_peft_model

    from models.graphcodebert.v2.model import forward_hidden

    device = torch.device("cuda")
    rows = load_cache(args.f0 / "cache_train.pkl")
    by_problem: dict[str, list[dict]] = {}
    for r in rows:
        if r["role"] == "accepted":
            by_problem.setdefault(r["problem"], []).append(r["features"])
    problems = [p for p, v in by_problem.items() if len(v) >= 2]
    rng = random.Random(0)
    pairs, checkpointing = args.pairs, args.checkpointing
    props = torch.cuda.get_device_properties(0)
    free_gb, total_gb = (x / 1e9 for x in torch.cuda.mem_get_info())
    entry = {
        "pairs": pairs, "sequences": 2 * pairs, "gradient_checkpointing": checkpointing,
        "gpu": props.name, "gpu_free_gb_at_start": round(free_gb, 2), "gpu_total_gb": round(total_gb, 2),
        "dtype": "float32", "lora_r": 16,
    }
    try:
        base = load_roberta(device)
        model = get_peft_model(base, LoraConfig(r=16, lora_alpha=32, target_modules=["query", "value"], lora_dropout=0.05))
        inner = model.base_model.model
        if checkpointing:
            inner.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
        inner.train()
        opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=1e-4)
        torch.cuda.reset_peak_memory_stats()
        times = []
        for step in range(args.warmup + args.steps):
            chosen = rng.sample(problems, pairs)
            pairs_f = [rng.sample(by_problem[p], 2) for p in chosen]
            feats = [a for a, _ in pairs_f] + [b for _, b in pairs_f]
            ids, pos, mask = batch_tensors(feats, device)
            torch.cuda.synchronize()
            t0 = time.time()
            hidden = forward_hidden(inner, ids, pos, mask)
            pooled = mean_pool_positions(hidden, [f["n_code_kept"] for f in feats])
            loss = info_nce(pooled[:pairs], pooled[pairs:])
            opt.zero_grad(set_to_none=True)
            loss.backward()
            opt.step()
            torch.cuda.synchronize()
            if step >= args.warmup:
                times.append(time.time() - t0)
        entry.update(
            seq_per_s=round(2 * pairs / float(np.mean(times)), 2),
            step_s=round(float(np.mean(times)), 3),
            peak_mem_gb=round(torch.cuda.max_memory_allocated() / 1e9, 2),
            last_loss=round(float(loss), 4),
        )
    except torch.cuda.OutOfMemoryError:
        entry["oom"] = True
    print(json.dumps(entry), flush=True)
    with open(args.f0 / "f1_speed.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("baseline", "speed"):
        p = sub.add_parser(name)
        p.add_argument("--f0", type=Path, default=Path(r"C:\Users\edani\datasets\codenet\f0"))
    sub.choices["baseline"].add_argument("--split", default="val", choices=["train", "val", "test"])
    sub.choices["baseline"].add_argument("--batch-size", type=int, default=16)
    sub.choices["speed"].add_argument("--pairs", type=int, default=8, help="anchor/positive pairs per batch")
    sub.choices["speed"].add_argument("--checkpointing", action="store_true", help="gradient checkpointing")
    sub.choices["speed"].add_argument("--steps", type=int, default=10)
    sub.choices["speed"].add_argument("--warmup", type=int, default=3)
    args = ap.parse_args()
    run_baseline(args) if args.cmd == "baseline" else run_speed(args)


if __name__ == "__main__":
    main()
