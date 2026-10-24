# Feature: Contrastive CodeNet training, phase F2 (pilot)

## Objective
F2 of `Documentacion/guias_implementacion/entrenamiento_contrastivo_codenet.md`: a LoRA + InfoNCE pilot on the
`v2_norm` F0 cache and the pre-registered continue/stop decision.

## Scope / constraints
- Config: 200 train problems (seed 0), 15 000 triplets, 16 problems per batch (48 sequences), 1 epoch (938 steps),
  LoRA r=16 / alpha 32 on `query`+`value`, AdamW lr 1e-4, 5% warmup then linear decay, temperature 0.05,
  gradient checkpointing, fp32. Triplet = Accepted anchor, other Accepted positive, same-problem Wrong Answer
  hard negative; the other problems of the batch are in-batch negatives.
- Criterion fixed before running (module docstring of `scripts/contrastive_train.py`): continue iff CodeNet val
  MAP@R gains >= 0.05 over 0.182 AND ESCOM E1 MAP@R (same sample and seed as `logic_grouping_eval.py`) is not
  below the zero-shot value. Otherwise stop and report a negative result; no tuning before it passes.
- E2 and the T1-T7 robustness are NOT run here: the guide reserves them for the single F4 evaluation.
- Artifacts: `C:\Users\edani\datasets\codenet\f2\pilot1\` (adapter, `train_log.jsonl`, `eval_zero_shot.json`,
  `result.json`).

## Tasks
- [x] T1 `scripts/contrastive_train.py` (train + eval) and `tests/test_contrastive_train.py` (RED observed, then GREEN)
- [x] T2 Zero-shot reference through the same pipeline: E1 0.37900 = the earlier run exactly; val MAP@R 0.18191
- [x] T3 Pilot run (3 180 s of training) and decision

## Evidence
| metric | zero-shot `v2_norm` | pilot adapter |
|---|---|---|
| CodeNet val MAP@R (Accepted, 99 held-out problems) | 0.182 | 0.706 (gain +0.524) |
| ESCOM E1 MAP@R | 0.379 [0.336, 0.430] | 0.434 [0.388, 0.486] (delta +0.055) |
| CodeNet val Accepted-vs-WA ROC-AUC (pooled) | 0.542 | 0.604 |
| mean cosine, same problem / different problem (val) | 0.970 / 0.956 | 0.761 / 0.373 |

- Decision: continue (both conditions met).
- E1 paired per-assignment delta: mean +0.0554, bootstrap CI95 [0.036, 0.078] (2 000 resamples of the 48
  assignments, seed 42); 42 assignments improve, 6 get worse. The reference Jaccard E1 is 0.450 [0.406, 0.499], so
  the adapter is now comparable to it, not above it.
- Training loss 3.15 -> about 1.0-1.5 (a non-learning batch of 16 would sit near ln 32 = 3.5).
- Throughput: 45k sequences in 3 180 s = about 14 seq/s (F1 projected 7.5; the GPU was less loaded).

## Caveats
- One seed and one run; the 0.524 val gain is in-domain (held-out CodeNet problems) and says nothing yet about
  teacher-reference correctness (E2) or robustness (H3).
- Accepted-vs-WA AUC stays low (0.60): a Wrong Answer is usually structurally close to an Accepted solution.
- The pilot trained on 200 of 778 eligible problems; F3 uses all of them.

## Next step
F3: configurations A (no Wrong Answer negatives, `--no-wa`) and B (this setup), 2 seeds each, all eligible
problems, 3 epochs. At the measured throughput one run of 150k triplets is about 8.8 h locally (about 35 h for
four runs), instead of the 67 h projected in F1.
