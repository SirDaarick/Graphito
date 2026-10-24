"""F2 of the contrastive CodeNet experiment: LoRA + InfoNCE pilot on the `v2_norm` F0 cache.

Triplets (guide, F2): anchor = an Accepted submission, positive = another Accepted of the same problem,
hard negative = a Wrong Answer of the same problem; the other problems of the batch are in-batch negatives.
The model is `microsoft/graphcodebert-base` with a LoRA adapter on `query`/`value`, fed with the cached
single-window `v2_norm` inputs and `mean` pooling (the deployed Channel A input).

    python scripts/contrastive_train.py eval --out <dir>                   # zero-shot E1 baseline
    python scripts/contrastive_train.py train --out <dir>                  # pilot: train, then evaluate
    python scripts/contrastive_train.py eval --adapter <dir>/adapter --out <dir>

Pilot continuation criterion (fixed before running, guide F2): MAP@R on CodeNet val up by >= 0.05 over the
F1 baseline AND ESCOM E1 MAP@R (same sample and seed as `logic_grouping_eval.py`) not lower than the
zero-shot value. If it is not met the experiment stops and is reported as a negative result.
"""

import argparse
import json
import math
import random
import sys
import time
from pathlib import Path
from typing import Sequence

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import contrastive_f1 as f1  # noqa: E402

TEMPERATURE = 0.05
MIN_VAL_GAIN = 0.05
DEFAULT_REPO = Path(r"C:\Users\edani\OneDrive\Documents\Proyectos\Graphito")  # holds the gitignored ESCOM data


# --- pure helpers (tested) ----------------------------------------------------------------------


def info_nce_hard(anchors, positives, negatives=None, temperature: float = TEMPERATURE):
    """InfoNCE of `[B, H]` anchors against their positives; the other positives of the batch and the
    optional `[B, H]` hard negatives are extra candidates. Target of anchor i is positive i."""
    import torch
    import torch.nn.functional as F

    a, p = F.normalize(anchors, dim=-1), F.normalize(positives, dim=-1)
    cands = p if negatives is None else torch.cat([p, F.normalize(negatives, dim=-1)])
    logits = a @ cands.T / temperature
    return F.cross_entropy(logits, torch.arange(a.shape[0], device=a.device))


def problem_batches(problems: Sequence[str], batch_size: int, n_steps: int, rng: random.Random) -> list[list[str]]:
    """`n_steps` batches of `batch_size` distinct problems, always taking the least used ones first
    (random tie-break), so every problem is used within one time of the others."""
    if batch_size > len(problems):
        raise ValueError(f"batch_size={batch_size} exceeds the {len(problems)} available problems")
    counts = {p: 0 for p in problems}
    batches = []
    for _ in range(n_steps):
        batch = sorted(problems, key=lambda p: (counts[p], rng.random()))[:batch_size]
        for p in batch:
            counts[p] += 1
        batches.append(batch)
    return batches


# --- data ---------------------------------------------------------------------------------------


def group_rows(rows: Sequence[dict]) -> tuple[dict, dict]:
    acc: dict[str, list[dict]] = {}
    wa: dict[str, list[dict]] = {}
    for r in rows:
        (acc if r["role"] == "accepted" else wa).setdefault(r["problem"], []).append(r)
    return acc, wa


def pack_mask(features: dict) -> np.ndarray:
    from models.graphcodebert.v2.encode import build_attention_mask

    mask = build_attention_mask(
        features["input_ids"].tolist(), features["position_idx"].tolist(), features["dfg_to_code"], features["dfg_to_dfg"],
        (f1.CLS_ID, f1.SEP_ID),
    )
    return np.packbits(mask, axis=1)


def make_batch(rows: Sequence[dict], packed: dict, device):
    import torch

    ids = torch.from_numpy(np.stack([r["features"]["input_ids"] for r in rows])).long()
    pos = torch.from_numpy(np.stack([r["features"]["position_idx"] for r in rows])).long()
    length = ids.shape[1]
    masks = np.stack([np.unpackbits(packed[(r["problem"], r["submission_id"])], axis=1, count=length).astype(bool) for r in rows])
    return ids.to(device), pos.to(device), torch.from_numpy(masks).to(device)


# --- E1 on ESCOM --------------------------------------------------------------------------------


def e1_eval(roberta, repo_root: Path, device, per_assignment: int = 60, seed: int = 42, n_boot: int = 1000) -> dict:
    """E1 MAP@R as `scripts/logic_grouping_eval.py` computes it for `v2_norm` (canonical identifiers,
    sliding windows, `mean` pooling), but with the given encoder weights."""
    from transformers import RobertaTokenizer

    from models.graphcodebert.v2.config import GCBV2Config
    from models.graphcodebert.v2.embed import GraphCodeBERTV2Embedder
    from models.graphcodebert.v2.model import DEFAULT_MODEL, GraphCodeBERTV2Encoder
    from models.graphcodebert.v2.pairs import map_at_r_ci
    from models.logic_eval.canonical import canonicalize_code
    from models.logic_eval.data import load_e1_sample
    from models.logic_eval.grouping import compute_map_at_r, compute_per_assignment_map_at_r

    sample = load_e1_sample(repo_root / "data" / "splits" / "split_v1.json.gz", max_per_block=per_assignment, seed=seed)
    tokenizer = RobertaTokenizer.from_pretrained(DEFAULT_MODEL, local_files_only=True)
    embedder = GraphCodeBERTV2Embedder(tokenizer, GraphCodeBERTV2Encoder(roberta, device=device, batch_size=16), GCBV2Config())
    vectors, failed = [], 0
    for item in sample:
        lang = item.get("lang", "c")
        code = (repo_root / item["id"]).read_text(encoding="utf-8", errors="replace")
        res = embedder.embed(canonicalize_code(code, lang=lang), lang)
        if not res.success:
            failed += 1
        vectors.append(res.mean if res.success else np.zeros(roberta.config.hidden_size, dtype=np.float32))
    emb = np.stack(vectors).astype(np.float64)
    norms = np.linalg.norm(emb, axis=1, keepdims=True)
    unit = np.divide(emb, norms, out=np.zeros_like(emb), where=norms > 0)
    labels = [e.get("block") or e.get("assignment") for e in sample]
    sim = unit @ unit.T
    per_assign = compute_per_assignment_map_at_r(sim, labels, labels)
    return {
        "map_at_r": compute_map_at_r(sim, labels)["value"],
        "ci95": map_at_r_ci(per_assign, n_boot=n_boot, seed=seed).get("ci95"),
        "n_items": len(sample),
        "n_embed_failures": failed,
        "per_assignment": per_assign,
    }


# --- commands -----------------------------------------------------------------------------------


def load_eval_model(device, adapter: Path | None):
    base = f1.load_roberta(device)
    if adapter is None:
        return base.eval()
    from peft import PeftModel

    return PeftModel.from_pretrained(base, str(adapter)).merge_and_unload().eval()


def evaluate(roberta, args, device) -> dict:
    from models.graphcodebert.v2.model import check_mask_honoured

    check_mask_honoured(roberta)
    val_rows = f1.load_cache(args.f0 / "cache_val.pkl")
    return {
        "val": f1.val_metrics(f1.embed_rows(roberta, val_rows, device), val_rows),
        "e1": e1_eval(roberta, args.repo_root, device),
    }


def run_eval(args) -> None:
    import torch

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    t0 = time.time()
    result = evaluate(load_eval_model(device, args.adapter), args, device)
    result.update(adapter=str(args.adapter) if args.adapter else None, elapsed_s=round(time.time() - t0, 1))
    args.out.mkdir(parents=True, exist_ok=True)
    name = "eval_adapter.json" if args.adapter else "eval_zero_shot.json"
    (args.out / name).write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({k: (v if k != "e1" else {kk: vv for kk, vv in v.items() if kk != "per_assignment"}) for k, v in result.items()}, indent=2))


def run_train(args) -> None:
    import torch
    from peft import LoraConfig, get_peft_model
    from transformers import get_linear_schedule_with_warmup

    from models.graphcodebert.v2.model import forward_hidden

    device = torch.device("cuda")
    args.out.mkdir(parents=True, exist_ok=True)
    random.seed(args.seed)
    torch.manual_seed(args.seed)
    rng = random.Random(args.seed)

    acc, wa = group_rows(f1.load_cache(args.f0 / "cache_train.pkl"))
    # Same problem set for configurations A and B: the ablation must isolate the Wrong Answer negatives.
    eligible = sorted(p for p, v in acc.items() if len(v) >= 2 and wa.get(p))
    chosen = eligible if args.problems == 0 else rng.sample(eligible, args.problems)
    steps = math.ceil(args.triplets / args.pairs)
    batches = problem_batches(chosen, args.pairs, steps, rng)
    print(f"problems={len(chosen)} of {len(eligible)} eligible, steps={steps}, sequences/step={(2 if args.no_wa else 3) * args.pairs}", flush=True)

    t0 = time.time()
    used = [r for p in chosen for r in acc[p] + ([] if args.no_wa else wa.get(p, []))]
    packed = {(r["problem"], r["submission_id"]): pack_mask(r["features"]) for r in used}
    print(f"masks precomputed for {len(used)} samples ({time.time() - t0:.0f}s)", flush=True)

    base = f1.load_roberta(device)
    model = get_peft_model(base, LoraConfig(r=args.rank, lora_alpha=2 * args.rank, target_modules=["query", "value"], lora_dropout=0.05))
    inner = model.base_model.model
    inner.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    inner.train()
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=args.lr, weight_decay=0.01)
    sched = get_linear_schedule_with_warmup(opt, max(1, int(0.05 * steps)), steps)

    from peft import get_peft_model_state_dict, set_peft_model_state_dict

    state_path = args.out / "state.pt"
    start, best, elapsed_before = 0, {"val_map_at_r": -1.0, "step": 0}, 0.0
    if state_path.exists():  # resume an interrupted run: weights, optimizer, scheduler, RNG and best-so-far
        st = torch.load(state_path, weights_only=False)
        set_peft_model_state_dict(model, st["adapter"])
        opt.load_state_dict(st["opt"])
        sched.load_state_dict(st["sched"])
        rng.setstate(st["rng"])
        start, best, elapsed_before = st["step"], st["best"], st["elapsed_s"]
        print(f"resumed from step {start} (best val MAP@R so far {best['val_map_at_r']:.4f} at step {best['step']})", flush=True)
    log = open(args.out / "train_log.jsonl", "a" if start else "w", encoding="utf-8")
    val_rows = f1.load_cache(args.f0 / "cache_val.pkl")[: args.val_max or None] if args.val_every else None

    def save_state(step: int) -> None:
        tmp = state_path.with_suffix(".tmp")
        torch.save({"adapter": get_peft_model_state_dict(model), "opt": opt.state_dict(), "sched": sched.state_dict(),
                    "rng": rng.getstate(), "step": step, "best": best, "elapsed_s": elapsed_before + time.time() - t0}, tmp)
        tmp.replace(state_path)

    t0 = time.time()
    for step, batch in enumerate(batches, 1):
        if step <= start:
            continue
        triplets = []
        for p in batch:
            a, pos = rng.sample(acc[p], 2)
            triplets.append((a, pos, None if args.no_wa else rng.choice(wa[p])))
        rows = [t[0] for t in triplets] + [t[1] for t in triplets] + ([] if args.no_wa else [t[2] for t in triplets])
        ids, pos, mask = make_batch(rows, packed, device)
        hidden = forward_hidden(inner, ids, pos, mask)
        pooled = f1.mean_pool_positions(hidden, [r["features"]["n_code_kept"] for r in rows])
        b = len(batch)
        loss = info_nce_hard(pooled[:b], pooled[b : 2 * b], None if args.no_wa else pooled[2 * b :])
        opt.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad], 1.0)
        opt.step()
        sched.step()
        if step % 10 == 0 or step == steps:
            elapsed = time.time() - t0
            rec = {"step": step, "loss": round(float(loss), 4), "lr": sched.get_last_lr()[0],
                   "elapsed_s": round(elapsed_before + elapsed), "eta_s": round(elapsed / (step - start) * (steps - step))}
            log.write(json.dumps(rec) + "\n")
            log.flush()
            print(json.dumps(rec), flush=True)
        if args.val_every and (step % args.val_every == 0 or step == steps):
            inner.eval()
            v = f1.val_metrics(f1.embed_rows(inner, val_rows, device), val_rows)  # CodeNet val only: ESCOM stays untouched
            inner.train()
            rec = {"step": step, "val_map_at_r": v["map_at_r_accepted"], "val_auc": v["accepted_vs_wa_auc"]["pooled_auc"],
                   "cos_same": v["cosine"]["mean_same_problem"], "cos_diff": v["cosine"]["mean_different_problem"]}
            with open(args.out / "val_log.jsonl", "a", encoding="utf-8") as vf:
                vf.write(json.dumps(rec) + "\n")
            print(json.dumps(rec), flush=True)
            if rec["val_map_at_r"] > best["val_map_at_r"]:
                best = {"val_map_at_r": rec["val_map_at_r"], "step": step}
                model.save_pretrained(args.out / "adapter_best")
            save_state(step)
        elif step % 200 == 0:
            save_state(step)
    model.save_pretrained(args.out / "adapter")
    train_s = round(elapsed_before + time.time() - t0)
    if args.skip_eval:
        print(f"trained in {train_s}s; adapter saved, evaluation skipped")
        return
    if args.skip_escom:  # F3: selection uses CodeNet val only; the single ESCOM evaluation is F4
        result = {"mode": "f3_val_only", "best": best, "n_problems": len(chosen), "steps": steps,
                  "train": {**{k: (str(v) if isinstance(v, Path) else v) for k, v in vars(args).items()}, "train_s": train_s}}
        (args.out / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result["best"]))
        return

    merged = model.merge_and_unload().eval()
    result = evaluate(merged, args, device)
    base_val = json.loads((args.f0 / "f1_baseline_val.json").read_text(encoding="utf-8"))["map_at_r_accepted"]
    zero = json.loads((args.out / "eval_zero_shot.json").read_text(encoding="utf-8"))
    d_val = result["val"]["map_at_r_accepted"] - base_val
    d_e1 = result["e1"]["map_at_r"] - zero["e1"]["map_at_r"]
    result["decision"] = {
        "val_map_at_r_baseline": base_val,
        "val_map_at_r_adapter": result["val"]["map_at_r_accepted"],
        "val_gain": d_val,
        "e1_baseline": zero["e1"]["map_at_r"],
        "e1_adapter": result["e1"]["map_at_r"],
        "e1_delta": d_e1,
        "continue": bool(d_val >= MIN_VAL_GAIN and d_e1 >= 0),
    }
    result["train"] = {**{k: (str(v) if isinstance(v, Path) else v) for k, v in vars(args).items()}, "train_s": train_s}
    (args.out / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result["decision"], indent=2))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("train", "eval"):
        p = sub.add_parser(name)
        p.add_argument("--f0", type=Path, default=Path(r"C:\Users\edani\datasets\codenet\f0"))
        p.add_argument("--out", type=Path, required=True)
        p.add_argument("--repo-root", type=Path, default=DEFAULT_REPO)
    t = sub.choices["train"]
    t.add_argument("--problems", type=int, default=200)
    t.add_argument("--triplets", type=int, default=15000)
    t.add_argument("--pairs", type=int, default=16, help="problems (triplets) per batch")
    t.add_argument("--lr", type=float, default=1e-4)
    t.add_argument("--rank", type=int, default=16)
    t.add_argument("--seed", type=int, default=0)
    t.add_argument("--no-wa", action="store_true", help="configuration A: no same-problem hard negatives")
    t.add_argument("--skip-eval", action="store_true", help="smoke runs: stop after saving the adapter")
    t.add_argument("--skip-escom", action="store_true", help="F3: no ESCOM evaluation (the single one is F4)")
    t.add_argument("--val-every", type=int, default=0, help="evaluate CodeNet val every N steps and keep adapter_best")
    t.add_argument("--val-max", type=int, default=0, help="smoke runs only: cap the val rows")
    sub.choices["eval"].add_argument("--adapter", type=Path, default=None)
    args = ap.parse_args()
    run_train(args) if args.cmd == "train" else run_eval(args)


if __name__ == "__main__":
    main()
