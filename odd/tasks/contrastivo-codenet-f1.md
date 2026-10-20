# Feature: Contrastive CodeNet training, phase F1 (baselines and speed)

## Objective
F1 of `Documentacion/guias_implementacion/entrenamiento_contrastivo_codenet.md`: record the `v2_norm` zero-shot
baselines (CodeNet val and ESCOM E1/E2) and measure the real training throughput before the F2 pilot.

## Scope / constraints
- Input is `v2_norm` (see `contrastivo-codenet-f0.md`), pooling `mean`, fp32, eager attention (the only dtype
  `v2/config.py` supports).
- Inputs are the F0 cache features, so the baseline sees exactly what training will see.
- ESCOM baselines are reused from `runs/logic_eval/20261013-152644` (same protocol, seed 42, 1000 bootstrap
  iterations); they are not recomputed.
- Outputs live outside the repo in `C:\Users\edani\datasets\codenet\f0\`.

## Tasks
- [x] T1 F0 correction: dedup of the CodeNet samples against the ESCOM evaluation corpus `data/raw/src`
  (`scripts/dedup_codenet_vs_escom.py`, 5 tests; the first F0 only compared against the 124 catalog programs)
- [x] T2 `scripts/contrastive_f1.py` baseline (CodeNet val) and speed benchmark (5 helper tests, written together
  with the code: no RED was observed)
- [x] T3 Run baseline and speed; record below

## Evidence
Dedup vs `data/raw/src` + `Programas_ESCOM` (43 895 files, Jaccard >= 0.8, MinHash 32x4 bands then exact):
27 464 samples checked, 1 flagged (Wrong Answer of p03089, Jaccard 1.0, train), removed -> 27 463 kept, no problem dropped.

CodeNet val, `v2_norm` zero-shot (99 problems, 2 766 samples; `f1_baseline_val.json`):
- MAP@R among Accepted: 0.182 (1 920 queries).
- Accepted vs Wrong Answer of the same problem: pooled ROC-AUC 0.542, mean per-problem 0.541.
- Mean cosine: same problem 0.970, different problem 0.956, all pairs 0.956 (saturated: gap 0.015).

ESCOM (reused, `runs/logic_eval/20261013-152644`): E1 MAP@R `v2_norm` 0.379 [0.336, 0.430] (Jaccard 0.450
[0.406, 0.499]); E2 Macro-AUC `v2_norm` 0.555 [0.505, 0.609] (Jaccard 0.563 [0.520, 0.611]).

Speed, RTX 2060 SUPER, 7.51 GB free at start, fp32, LoRA r=16 (query/value), InfoNCE, 512-token inputs, one
process per configuration (`f1_speed.jsonl`):

| pairs/batch | sequences | grad. checkpointing | seq/s | step s | peak GB |
|---|---|---|---|---|---|
| 4 | 8 | no | 11.4 | 0.70 | 5.19 |
| 8 | 16 | no | 0.05 | 299 | 9.86 (spills past 7.5 GB) |
| 16 | 32 | no | no output (failed) | - | - |
| 4 | 8 | yes | 15.0 | 0.53 | 1.22 |
| 8 | 16 | yes | 7.5 | 2.15 | 1.91 |
| 16 | 32 | yes | 7.6 | 4.20 | 3.31 |
| 32 | 64 | yes | 3.4 | 18.9 | 6.09 |

- The guide estimated 20-40 seq/s; measured 7-15 seq/s. Checkpointing is required for batches >= 8 pairs.
- Throughput is not flat across batch sizes (15 -> 7.5 -> 3.4 with checkpointing) and each point is 10 steps
  after 3 warm-up steps on a GPU shared with the desktop: treat these as order of magnitude.
- Projection at 7.5 seq/s (16 pairs, checkpointing): F2 pilot (about 45k sequences) about 100 min; one F3 run
  (450k sequences) about 17 h, so four runs about 67 h locally. At 15 seq/s the times halve.

## Next step
F2 pilot (200 problems, 1 epoch): port `contrastive_graphcodebert.py` to the `v2_norm` cache and InfoNCE; the
`info_nce` and `batch_tensors` helpers in `scripts/contrastive_f1.py` already do the core of it.
