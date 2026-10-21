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

## Tasks
- [x] T1 Make training resumable, add periodic CodeNet-val selection and `--skip-escom` (smoke: killed after the first
  checkpoint, resumed from step 10 and finished with the expected `result.json`)
- [x] T2 `scripts/run_f3.ps1` runner for the four runs
- [ ] T3 Four runs finished; compare A vs B on val per seed and pick the configuration for F4
- [ ] T4 Record results below

## Evidence
Started 2026-10-21 01:47. First ETA for B_s0: about 8.2 h (29 400 s); estimate for the four runs about 30 h
(B about 9 h, A about 6 h each, from the 14 seq/s measured in the pilot).
