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

## Deviation declared on 2026-10-23, before any adapter robustness number was read
The robustness run produced all 60 score files (10 conditions x 6 methods, 12:16-22:04 on 10-22) but its
per-method metrics stage (`compute_metrics`, 1 000 resamples x 2 views per file, plus the PR-AUC and operating
points that H3 does not use) had run 3 h 10 min without finishing one of its 60 tasks, so it was stopped. The
quantities the pre-registration fixes are unchanged: the ROC-AUC (view `all`), the paired bootstrap stratified by
assignment with n_boot = 1 000 and seed 42, and the difference-in-differences CI95 of H3. They are now computed by
`paired_bootstrap(..., fast_grouped=True)` over the saved scores: the same resample draws (same chunks and seeds)
and the same midrank AUC, obtained from one sort per column. Equivalence was tested on synthetic data with ties and
undefined resamples (7 tests) and on real F4 columns, where it was bit-identical (max difference 0.0; 192 s against
9.6 s on 4 columns x 40 resamples). Dropped: the per-method PR-AUC and operating-point metrics of the robustness
report; the score files remain, so they can be computed later.

## Tasks
- [x] T1 `models/graphcodebert/v2/adapter.py` (adapter identity, cache key, merged embedder), 8 tests including
  train/eval consistency (cosine > 0.9999 between the windowed pipeline and the cached training inputs)
- [x] T2 `--adapter ft_NAME=PATH` in `scripts/robustness_experiment.py` and adapter canonicalization in
  `models/robustness/scoring.py`; verified with a null adapter (untrained LoRA): AUC identical to `v2_norm`
- [x] T3 `scripts/f4_eval.py` (`plan`, `run`, gates, verdicts) with 11 tests; full smoke run with null adapters on
  subsets: every stage and output produced, null adapters equal the zero-shot, gates correctly fail on subsets
- [x] T4 Run `python scripts/f4_eval.py run` (started 2026-10-22 12:16, finished 2026-10-23 02:10; resumed once)
- [x] T5 Record results here (below)
- [ ] T6 Write the results up in the thesis

## Results (frozen run; outputs in `C:\Users\edani\datasets\codenet\f4\`)
Gates: zero-shot `v2_norm` reproduced the earlier ESCOM runs exactly (E1 0.37900444, E2 0.55504899, robustness
T0/T1 0.90219/0.90168).

| method | E1 MAP@R | E2 Macro-AUC [CI95] |
|---|---|---|
| Jaccard | 0.4497 | 0.5631 [0.520, 0.611] |
| `v2_norm` zero-shot | 0.3790 | 0.5550 [0.505, 0.609] |
| `ft_B_s1` (headline) | 0.4306 | 0.5860 [0.545, 0.626] |
| `ft_B_s0` | 0.4313 | 0.5976 [0.553, 0.641] |
| `ft_A_s0` | 0.4346 | 0.6002 [0.553, 0.651] |
| `ft_A_s1` | 0.4387 | 0.6133 [0.561, 0.666] |

Verdicts (headline `ft_B_s1` against zero-shot `v2_norm`):
- H1 (E2): **inconclusive**, +0.0310, CI95 [-0.014, 0.086] over 14 assignments. Only `ft_A_s1` has a CI above 0
  (+0.058 [0.002, 0.129]). The guide's solid-result target (0.65-0.70) was not reached.
- H2 (E1): **confirmed**, +0.0506, CI95 [0.028, 0.077] over 48 blocks; all four adapters improve by about 0.05.
  No adapter beats Jaccard on E1 (headline -0.0215, CI [-0.045, 0.004]).
- H3 (robustness): **confirmed**: no condition has a difference-in-differences CI entirely below 0 for the
  headline (nor for any of the other three adapters). Headline DiD CI above 0 in T5 (+0.071 [0.001, 0.203]) and
  T7@1.0 (+0.121 [0.020, 0.264]): dead-code insertion and the combined transformation hurt the adapter less than
  `v2_norm`. Point estimates below 0 but with CIs including 0: T2 (-0.007) and T7@0.25 (-0.026 [-0.044, 0.005]).
- Robustness ROC-AUC, T0 -> T7@1.0: Jaccard 0.945 -> 0.931, `v2_norm` 0.902 -> 0.708, `ft_B_s1` 0.902 -> 0.830.
  Jaccard stays above every neural method in every condition.

Caveats: A configurations score higher than B on E2 (point estimates, inside the noise) although B was better on
the CodeNet within-problem AUC used to freeze the headline; the headline was not changed after seeing ESCOM.
E2 has 14 assignments (low power) and uses passing student submissions as references, not teacher solutions.

## Sizes (from `f4_eval.py plan`, no model results)
E1: 2 842 files x 5 neural models. E2: 543 submissions x 5 neural models. Earlier single-model passes took
about 17 min for E1 on this GPU, so E1+E2 for five models is roughly 1.5-2 h (estimate). The robustness run has
not been timed at full scale (10 conditions x 5 neural methods on the test pairs); the shared embedding cache
helps for `v2_norm`. Expect several hours; it is resumable.
