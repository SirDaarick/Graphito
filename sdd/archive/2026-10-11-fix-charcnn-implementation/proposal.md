# Proposal: Fix CharCNN Implementation (fix-charcnn-implementation)

## Intent

Channel B (CharCNN AI-code detector, `models/char_cnn/`) cannot be measured honestly. The exploration found:
- **Train/infer mismatch.** Training pads to 4096 (`dataset.py:55`), inference does not (`inference.py:90,105`), and pooling ignores padding after BatchNorm (`model.py:62-63`).
- **Label leaks on disk that occur only in human files.** Course headers (`Zadaća/Zadatak N`, 22,714 files), C0 controls (18,964), CR (16,448), tabs, and diacritics or curly quotes. They are hidden because UNK == PAD == 0 (`preprocess.py:35-36`).
- **Training is not reproducible.** There is no seeding, the dummy forward pass pollutes BatchNorm, and the run overwrote the tracked `best_model.pth`. Metrics are argmax only.

This change is SDD-2 of Phase 1. It fixes the implementation and measures the model honestly on `split_v1` with the SDD-1 `models/evaluation` toolkit. It does **not** try to improve the model.

## Scope

### In Scope
- Preprocess v2 as the single source of truth, applied the same way to both classes. It includes a leak guard in the training CLI and an UNK index distinct from PAD.
- Model `arch_version` 2: masked pooling, LayerNorm, a single dropout and sliding-window inference.
- A trainer driven by the `split_v1` manifest. It is seeded, uses balanced per-epoch resampling, selects checkpoints by val AUC, calibrates on val only and evaluates test once.
- Versioned run artifacts under `runs/char_cnn/<ts>/`, plus an explicit promote CLI. This change runs no promotion.
- A backward-compatible `CharCNNInference` that adds keys for abstention and versioning.
- A shortcut report (reporting only) and a legacy baseline of the current checkpoint on `split_v1` test.
- Deprecating `prepare_dataset.py` and `dataset_manifest.json`, and removing the `data/train_charcnn.py` PoC.

### Out of Scope
- Regenerating AI data, new LLMs, leave-one-LLM-out and the TF-IDF probe (Phase 2).
- Backend thresholds, fusion, XAI, UI handling of abstention and promotion to production (SDD-4).
- Any change to `models/char_cnn/best_model.pth`. The user's uncommitted file stays as it is.
- Changes to `models/evaluation` APIs. They are consumed only.

## Capabilities

### New Capabilities
- `charcnn-preprocessing`: the versioned v2 normalization pipeline, alphabet with a distinct UNK and PAD, and the leak-pattern guard.
- `charcnn-training`: manifest-driven, seeded training and evaluation. Covers checkpoint selection, val-only calibration, the test report with CIs, the shortcut report, the legacy baseline, versioned run artifacts and the promote CLI.
- `charcnn-inference`: arch v2 inference with padding invariance and sliding windows, abstention, a backward-compatible result contract and frozen loading of legacy checkpoints.

### Modified Capabilities
- None. The `eval-foundation` capabilities are consumed unchanged.

## Approach

1. **Preprocess v2** (`preprocess.py`) runs these steps in order:
   - Convert CRLF and CR to LF, and delete C0 controls and zero-width characters.
   - Strip diacritics with NFKD, map Unicode quotes, dashes and NBSP to ASCII, then drop any remaining non-ASCII.
   - Remove comments by importing `models.evaluation.normalize.strip_comments`.
   - Strip course header lines and `Zadaća/Zadatak/Tutorijal N` tokens.
   - Keep only canonical whitespace.

   The training CLI aborts if more than 0.1% of human files still match a leak pattern.
2. **Model v2.**
   - Masked average and max pooling with dynamic padding, and channel LayerNorm, so output does not change with padding.
   - One dropout, and no special case for batch size 1.
   - Training takes a random 4096-character crop. Inference averages logits over sliding windows (stride 2048, at most about 8 windows).
3. **Trainer.**
   - Train and val come from `load_split(..., representatives_only=True)`.
   - Each epoch uses all AI files plus a fresh human sample drawn with `stable_rng`, under `seed_everything(deterministic)`.
   - There is no train-mode dummy forward pass, and checkpoints are selected by val ROC/PR-AUC.
   - Platt calibration is fitted on val only. Test is evaluated once at the end.
   - The report goes through `models.evaluation`: observed and balanced views, bootstrap CIs grouped by `dup_group`, and per-group results by language, course, profile, model and length bucket.
4. **Artifacts.**
   - Checkpoints are written only under `runs/char_cnn/<ts>/`. They carry the full config: `arch_version`, `preproc_version`, alphabet, conv sizes, dropout, seed and manifest sha256.
   - The promote CLI refuses to overwrite a modified `best_model.pth` unless `--force` is given.
5. **Inference contract.**
   - Constructor, `predict`/`predict_text` signatures and all existing keys stay the same.
   - New keys: `score` (None when abstained), `abstained`, `n_windows`, `preproc_version` and `arch_version`.
   - Short input abstains, but the legacy numeric keys are still filled.
   - Checkpoints without version fields load through a frozen legacy path that is unchanged byte for byte.
6. **Shortcut report.** For each class, it records the share of files that still contain:
   - non-ASCII characters;
   - course markers (`Zadaća`, `Zadatak`, `Tutorijal`, autotest);
   - control characters, CR or tabs;
   - `std::`, `using namespace` or `#include <bits/`;
   - a non-code first line.

   It also records length buckets. The output goes to `shortcuts.json` and is annotated in the report.
7. **Legacy baseline.** The current `best_model.pth` is run through the same harness on `split_v1` test and labeled contaminated, because the legacy split overlaps test.
8. **Deprecation.** Remove `data/train_charcnn.py`. Mark `prepare_dataset.py` and `dataset_manifest.json` deprecated and keep them until the legacy tests migrate.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `models/char_cnn/preprocess.py` | Modified | v2 pipeline, distinct UNK, leak patterns, version constant |
| `models/char_cnn/model.py` | Modified | arch v2 (masked pooling, LayerNorm); v1 kept for legacy load |
| `models/char_cnn/dataset.py` | Modified | Manifest-driven, dynamic padding, random crop |
| `models/char_cnn/train.py` | Modified | Seeded manifest trainer; writes only to `runs/` |
| `models/char_cnn/inference.py` | Modified | Windows, abstention, version keys, legacy path |
| `models/char_cnn/` (promote, shortcut, baseline CLIs; names in design) | New | Promotion guard, shortcut report, legacy baseline |
| `models/char_cnn/prepare_dataset.py`, `dataset_manifest.json` | Deprecated | Marked; not deleted |
| `data/train_charcnn.py` | Removed | Invalid PoC |
| `tests/test_char_cnn_{guard,canonical,robustness}.py`, `tests/test_calibration_experiment.py` | Modified | Align with the v2 contract; legacy cases stay green |
| `tests/` | New | Padding invariance, leak guard, determinism, contract, promote guard |
| `backend/app/infrastructure/inference/real_engine.py`, `scripts/benchmark_*.py`, `scripts/generate_tt_figures.py` | Unchanged (verify in design) | Expected to rely only on legacy keys and float contract |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Old checkpoint or consumers break | Med | Frozen legacy path; contract tests on legacy keys; `real_engine.py` unchanged |
| New numbers read as a regression against the old 96% claim | High | Report states the split and preprocessing differ; legacy baseline marked contaminated |
| Few AI positives (225 val, 331 test) give wide CIs | High | Bootstrap CI95 grouped by `dup_group`; low-support groups flagged |
| One dominant generator means results hold only in distribution | High | Per-model breakdown; stated as a limitation; leave-one-LLM-out is Phase 2 |
| Bosnian strings in the corpus vs Spanish deployment | Med | ASCII folding plus header stripping; documented as a domain-shift limitation |
| Dedup (`representatives_only`) shrinks the human train set | Med | Per-epoch fresh human draws; report effective sizes |
| CUDA nondeterminism | Med | `seed_everything(deterministic=True)`; reproducibility asserted on CPU |
| CUDA run not bit-identical to CPU | Low | torch CUDA verified available; CPU fixture test proves determinism; CUDA run records seed and versions |
| Stripping leaves residual shortcuts (`std::`, `bits/`) | Med | Shortcut report quantifies them; no silent normalization of legitimate code |

## Rollback Plan

All work is on `feat/fix-charcnn-implementation` as work-unit commits. To roll back, revert those commits. `best_model.pth` is never written and the backend keeps loading it through the frozen legacy path, so there is no runtime impact. `runs/` output is gitignored apart from selected reports.

## Dependencies

- SDD-1 `eval-foundation`: `models/evaluation` (`load_split`, `seed_everything`, `stable_rng`, metrics, calibration, `RunContext`, `strip_comments`) and `data/splits/split_v1.json.gz`.
- torch (present). No new runtime dependencies.

## Success Criteria

- [ ] A padding invariance test passes: the v2 output on the same input is identical (within tolerance) whether or not padding is added, and for batch size 1 vs larger batches.
- [ ] The leak guard test passes, and in the real run fewer than 0.1% of preprocessed human files match leak patterns.
- [ ] Two seeded CPU runs with the same config produce identical metrics and checkpoint selection.
- [ ] `runs/char_cnn/<ts>/` contains the versioned config, val calibration, test metrics with CI95, per-group breakdown and `shortcuts.json`.
- [ ] The legacy baseline report on `split_v1` test exists and is labeled contaminated.
- [ ] `models/char_cnn/best_model.pth` is byte-identical to its state before the change.
- [ ] Existing consumer tests and the new CharCNN tests pass under `pytest`.

## Resolved Questions (orchestrator, 2026-10-10)

- Test metrics: headline on representatives (consistent with training dedup); all test files reported as a secondary view with CI bootstrapped by `dup_group`.
- Per-epoch resampling ratio: 1:1 human:AI. Natural prevalence is reported through the `observed` view, not through training.
- Environment: torch 2.13+cu126 with `torch.cuda.is_available() == True` was verified on this machine (Python 3.14, RTX 2060 SUPER). The reported run uses CUDA with deterministic flags; exact reproducibility is asserted by a CPU test on a fixture tree.
