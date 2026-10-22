# Feature: Contrastive CodeNet training, phase F3 (full training with ablation)

## Objective
F3 of `Documentacion/guias_implementacion/entrenamiento_contrastivo_codenet.md`: train configurations A (no
same-problem Wrong Answer negatives) and B (with them), 2 seeds each, and pick the checkpoint by CodeNet val only.

## Scope / constraints
- Pilot setup of F2 (see `contrastivo-codenet-f2.md`) scaled up: all 778 eligible train problems (>= 2 Accepted and
  >= 1 Wrong Answer; the same set for A and B so the ablation isolates the negatives), 150 000 triplets = 9 375 steps
  of 16 problems (3 epochs of 50 000, as the guide), seeds 0 and 1. A uses 32 sequences per step, B 48.
- Selection: CodeNet val MAP@R every 1 000 steps, `adapter_best` keeps the best; ESCOM is not evaluated here
  (`--skip-escom`): E1, E2 and T1-T7 are the single F4 evaluation of the frozen configuration.
- Runs are resumable (`state.pt`: weights, optimizer, scheduler, RNG, best-so-far) and `scripts/run_f3.ps1` skips
  finished runs (`result.json`), so it can simply be started again after an interruption.
- Run order: B_s0, A_s0, B_s1, A_s1. Outputs and logs: `C:\Users\edani\datasets\codenet\f3\<run>\` and `<run>.log`.
- The Windows power plan is not changed by the agent; the machine must not sleep during the runs.

## Selection criterion (changed 2026-10-21, user decision, after B_s0 finished and before A_s0 results)
At deployment a submission is compared only with the reference of its own problem, so what matters is the
within-problem ordering of "similar to the reference" (correct above incorrect), not separation between problems.
MAP@R on CodeNet val (and E1) measure cross-problem retrieval and become secondary diagnostics. The primary metric
to choose between A and B, and to read the checkpoints, is the within-problem Accepted-vs-Wrong-Answer ROC-AUC on
CodeNet val (`val_auc` in `val_log.jsonl`, logged every 1 000 steps). Per-seed comparison, A vs B; no ESCOM data.
Checkpoint note: `adapter_best` is still the best by MAP@R and `adapter` is the final step; read `val_log.jsonl` to
see whether the AUC peaked elsewhere (for B_s0 AUC is flat at the end: 0.634 at step 9 000, 0.633 at 9 375).

Why this matters, measured on CodeNet val (mean cosine of an Accepted anchor to ...):

| | other Accepted, same problem | Wrong Answer, same problem | other problems |
|---|---|---|---|
| zero-shot `v2_norm` | 0.972 | 0.970 | 0.956 |
| B_s0 `adapter_best` | 0.787 | 0.728 | 0.270 |

The Wrong Answer is not pushed away like an unrelated program (0.73 vs 0.27), but only about 0.06 below the
correct solutions, hence the modest AUC (0.54 -> 0.63). CodeNet has no usable partial-credit label: 91% of the
Wrong Answer rows in a sample have `accuracy` 0 and 2% have >= 0.5. Graded correctness exists only in ESCOM
(`last_test_results`), evaluated in F4 (E2). A within-problem-only loss (no cross-problem negatives) is a possible
configuration C after A vs B; it is not run now.

## Tasks
- [x] T1 Make training resumable, add periodic CodeNet-val selection and `--skip-escom` (smoke: killed after the first
  checkpoint, resumed from step 10 and finished with the expected `result.json`)
- [x] T2 `scripts/run_f3.ps1` runner for the four runs
- [x] T3 Four runs finished; compare A vs B on val per seed and pick the configuration for F4
- [x] T4 Record results below

## Evidence
Started 2026-10-21 01:47, finished 2026-10-22 07:20 (about 29.5 h wall clock including two interruptions: the
runner and the training processes disappeared at 14:10 on 10-21 and at 20:58 on 10-21 with no system event or error;
both resumed from `state.pt`, losing under 10 minutes of training each).

CodeNet val (99 held-out problems, 2 766 samples), final step 9 375 of each run; zero-shot reference AUC 0.542,
MAP@R 0.182:

| run | within-problem Accepted-vs-WA AUC | MAP@R | best AUC in the log |
|---|---|---|---|
| B_s0 (with Wrong Answer negatives) | 0.633 | 0.812 | 0.634 (step 9 000) |
| B_s1 | 0.634 | 0.810 | 0.634 (step 9 375) |
| A_s0 (without them) | 0.606 | 0.844 | 0.608 (step 8 000) |
| A_s1 | 0.607 | 0.850 | 0.609 (step 7 000) |

- Seeds agree within 0.001-0.003 AUC inside each configuration; B beats A by about 0.027 AUC, A beats B by about
  0.035 MAP@R. By the selection criterion above B wins.
- A's AUC is flat from step 2 000 (about 0.60); B keeps rising until about step 7 000.

## Frozen for F4 (decided 2026-10-22, before any F4 number exists)
- Configuration B. Headline adapter: B_s1 `adapter` (final step; highest final val AUC, 0.634 vs 0.633, a tie-break
  between statistically indistinguishable seeds). `adapter_best` is NOT used for B: it is selected by MAP@R.
- Per the guide ("all conditions and ablations are reported, no cherry-picking"), F4 also evaluates B_s0 `adapter`,
  A_s0 `adapter` and A_s1 `adapter`, reports all four, and draws H1-H3 only from the headline adapter.
- No retraining or recalibration after seeing ESCOM results.
