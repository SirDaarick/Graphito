# Feature: Contrastive CodeNet training, phase F4 (single final evaluation on ESCOM)

## Objective
F4 of `Documentacion/guias_implementacion/entrenamiento_contrastivo_codenet.md`: evaluate the frozen F3 adapters on
ESCOM (E1, E2, robustness T0-T7) once. This document is the pre-registration: it is written before any adapter
number exists on ESCOM data. **Status: pipeline built and smoke-tested; the real evaluation has NOT been run.**

## Frozen inputs (see `contrastivo-codenet-f3.md`)
- Headline adapter `ft_B_s1` = `C:\Users\edani\datasets\codenet\f3\B_s1\adapter`; also evaluated and reported, never
  used to pick the headline: `ft_B_s0`, `ft_A_s0`, `ft_A_s1` (all four `adapter`, i.e. the final step).
- Baselines: zero-shot `v2_norm` (canonical identifiers, v2 DFG, mean pooling) and Jaccard.
- Adapter identity is recorded as sha256 in `f4_frozen.json` before anything is computed; the script refuses a
  second start (`--resume` only continues the same frozen run and checks the hashes).

## Protocol
- E1: MAP@R on the `logic_grouping_eval.py` sample (2 842 files, 60 per block, seed 42), bootstrap over blocks.
- E2: leave-one-out passing references, Macro-AUC over the 14 qualifying assignments (543 submissions),
  bootstrap over assignments. The references are passing student submissions, not teacher-written solutions
  (limitation of the current corpus, already stated in the guide); a teacher reference set would be a separate run.
- Robustness: `robustness_experiment.py` on the `split_v1` test pairs, methods `jaccard`, `v2_norm` and the four
  adapters, conditions T0-T6 and T7@0.25/0.5/1.0, ROC-AUC (view `all`), paired bootstrap stratified by assignment
  (n_boot 1 000). Adapter methods canonicalize identifiers on both sides like `v2_norm`.
- Reproduction gates, run BEFORE any adapter is scored (the script stops otherwise): zero-shot `v2_norm` E1 and E2
  must equal `runs/logic_eval/20261013-152644` (tolerance 1e-6: 0.37900444 and 0.55504899), and zero-shot
  robustness T0/T1 must match `runs/robustness_v2norm/20261019-222018` within 0.002.

## Hypotheses and verdict rules (headline adapter vs zero-shot `v2_norm`)
- H1: E2 Macro-AUC gain; paired bootstrap CI95 of the per-assignment AUC difference above 0 = confirmed, entirely
  below 0 = refuted, otherwise inconclusive. The guide's expectation: 0.56 -> 0.65-0.70 would already be solid.
- H2: E1 MAP@R gain; same rule over per-block MAP@R differences. Reminder (user, 2026-10-21): deployment compares
  within a problem, so H2 is a secondary diagnostic and H1 carries the thesis claim.
- H3 (non-regression): for every condition T1-T7, the difference-in-differences
  `[AUC_ft(c) - AUC_ft(T0)] - [AUC_v2_norm(c) - AUC_v2_norm(T0)]` with its CI95. Refuted if any condition has a CI
  entirely below 0; otherwise confirmed. Ten conditions are tested without multiplicity correction; any single
  refutation will be read together with its CI and the other three adapters.
- Always reported, whatever the outcome: all four adapters, Jaccard, per-assignment values, the A vs B ablation on
  ESCOM. No retraining, recalibration or checkpoint change after seeing the results.

## Tasks
- [x] T1 `models/graphcodebert/v2/adapter.py` (adapter identity, cache key, merged embedder), 8 tests including
  train/eval consistency (cosine > 0.9999 between the windowed pipeline and the cached training inputs)
- [x] T2 `--adapter ft_NAME=PATH` in `scripts/robustness_experiment.py` and adapter canonicalization in
  `models/robustness/scoring.py`; verified with a null adapter (untrained LoRA): AUC identical to `v2_norm`
- [x] T3 `scripts/f4_eval.py` (`plan`, `run`, gates, verdicts) with 11 tests; full smoke run with null adapters on
  subsets: every stage and output produced, null adapters equal the zero-shot, gates correctly fail on subsets
- [ ] T4 Run `python scripts/f4_eval.py run` (user go-ahead needed; the real evaluation is one-shot)
- [ ] T5 Record results here and write them up in the thesis

## Sizes (from `f4_eval.py plan`, no model results)
E1: 2 842 files x 5 neural models. E2: 543 submissions x 5 neural models. Earlier single-model passes took
about 17 min for E1 on this GPU, so E1+E2 for five models is roughly 1.5-2 h (estimate). The robustness run has
not been timed at full scale (10 conditions x 5 neural methods on the test pairs); the shared embedding cache
helps for `v2_norm`. Expect several hours; it is resumable.
