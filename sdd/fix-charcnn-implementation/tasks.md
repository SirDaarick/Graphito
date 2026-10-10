# Tasks: Fix CharCNN Implementation (fix-charcnn-implementation)

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated authored changed lines | ~3,700 (code ~1,700 + tests ~1,700 + docs ~300); run artifacts, golden JSON and deleted PoC not counted |
| 400-line budget risk | High in total; per work unit WU6 ~700, WU5/WU7 ~550, others 350-450 (advisory only) |
| Chained PRs recommended | Yes |
| Suggested split | PR1 = WU1-2 -> PR2 = WU3-4 -> PR3 = WU5-6 -> PR4 = WU7-8 -> PR5 = WU9 (real run + artifacts + README results) |
| Delivery strategy | ask-on-risk (default; not supplied) |
| Chain strategy | feature-branch-chain (PR1 base = `feat/fix-charcnn-implementation`; PR N base = PR N-1 branch) |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: feature-branch-chain
400-line budget risk: High

Push, PR creation and merge stay user decisions. Each WU = one Conventional Commit (English) with tests and docs; ~400 lines is advisory. Behavior tasks are RED (test) first, then GREEN. Runner: `python -m pytest tests/ backend/tests/ -q -p no:cacheprovider` (pytest.ini pythonpath `. backend`); focused: `python -m pytest tests/test_char_cnn_v2_<x>.py -q -p no:cacheprovider`. Fixtures are synthetic (`tmp_path`, `tests/eval_factory.py` reused: `make_tree`, `build_split`, `write_manifest`); tiny CPU models only, except WU9. Known pre-existing failure: `tests/test_calibration_experiment.py::test_graphcodebert_calibration`.

Hard constraints for every task: `models/char_cnn/best_model.pth` stays byte-identical (never write it, never run promote; NF3). No diff under `models/evaluation/` (NF1). Frozen legacy files get zero edits: `models/char_cnn/{preprocess,model,dataset,config}.py` (D1).

### Work Units and Dependencies

| WU | Commit | Depends on | Parallel with |
|----|--------|-----------|---------------|
| 1 | `feat(charcnn): add preprocess v2` | none | WU2 |
| 2 | `feat(charcnn): add arch v2 model and windowed scoring` | 1.1 only (`v2/config.py`) | WU1.2-1.3 |
| 3 | `test(charcnn): capture legacy golden snapshot` then `feat(charcnn): version-dispatching inference facade` (2 commits) | 1, 2 (3.1 only needs the untouched tree) | WU4 (after 3.1) |
| 4 | `feat(charcnn): manifest-driven encoded data and epoch sampler` | 1, 2 | WU3.2-3.4 |
| 5 | `feat(charcnn): seeded v2 trainer with AUC selection and leak guard` | 1, 2, 4 | none |
| 6 | `feat(charcnn): val-only calibration, test report and shortcut audit` | 5 | none |
| 7 | `feat(charcnn): add legacy baseline and promote CLIs` | 3, 6 | WU8 |
| 8 | `chore(charcnn): deprecations, train.py delegation and README` | 5 (7 for README CLI list) | WU7 |
| 9 | `data(charcnn): v2 run and legacy baseline artifacts` + `docs(charcnn): results` | all | none |

Ordering note: 3.1 MUST land (committed) before any edit to `inference.py` (design commit order step 3); schedule it first of all if WU3 is picked up before WU1/2.

Reconciliations (spec wins over design/proposal where they differ):
- CP5.2: whole print line removal (design `_HEADER_PRINT_RE`), then leftover marker tokens. CP6.1: line-preserving whitespace (D4); the design open question is closed. CI3.1: `linspace` window starts beyond cap 8.
- CP9.1 lists `autotest` among the guard's course markers, but the design `_MARKER` omits it. Guard pattern `course_marker` includes `autotest` (match only, not stripped); see DECISION D-B.
- CP10.1/CT10.1: `DeprecationWarning` is emitted on import of `prepare_dataset` (design said in `main`). No test or script imports it (checked), so this is safe.
- D2: the trainer uses `load_manifest(...).samples(split, representatives_only=True)`; `load_split` has no such parameter.
- Guard wiring lands in WU5 (trainer step 4, before the first epoch) rather than design commit 6, because CP9.2 requires abort before any checkpoint.

## WU1: Preprocess v2

- [x] 1.1 Create package `models/char_cnn/v2/__init__.py` and `models/char_cnn/v2/config.py` (side-effect-free frozen `CharCNNV2Config`: vocab, dims, kernels, filters, fc_units, dropout, window 4096, stride 2048, max_windows 8, min_non_ws_chars 60, `to_dict`/`from_dict`; constants `PREPROC_VERSION=2`, `ARCH_VERSION=2`). RED `tests/test_char_cnn_v2_preprocess.py::config` (round-trip, no `weights/`/`logs/` dirs created). [CP1.2, CI6.1, D1]
- [x] 1.2 RED `::steps`: CRLF/CR/C0/DEL/zero-width/BOM, folding (`Zadaća šđ “x” – y z`), non-ASCII dropped (not UNK), comment cases (`1'000`, `'"'`, `"http://a"`), headers (3 forms equal body; `printf("Zadaća 5, Zadatak 3");` line removed; `zadatak_count` preserved), whitespace (tabs, indentation, blank lines, literal spacing), idempotence. GREEN `models/char_cnn/v2/preprocess.py` (`preprocess_v2`, delegating to `models.evaluation.normalize.strip_comments`, no copy). [CP1-CP6]
- [x] 1.3 RED `::alphabet_symmetry_guard`: PAD=0, UNK=1 distinct, vocab 98, uint8 `encode`, empty -> `[UNK]`, human-styled vs AI-styled twin encode identically, `leak_hits`, `leak_guard` (0/1000 pass, 1/1000 pass, 2/1000 raises `LeakGuardError` naming the pattern; strict `>`). GREEN: `encode`, `effective_length_v2`, `LEAK_PATTERNS`, `leak_guard`, `LeakGuardError`. [CP7, CP8, CP9.1-9.2]
- Check: `python -m pytest tests/test_char_cnn_v2_preprocess.py -q -p no:cacheprovider`. Docs: module docstrings only.
- Evidence: RED 1.1 `ModuleNotFoundError: models.char_cnn.v2`, 1.2 `ImportError: cannot import name 'preprocess'`, 1.3 21 failed `AttributeError: ... no attribute 'encode'` -> GREEN 70 passed. Spec-driven additions beyond the design regexes: leading course-header lines (marker + number) are dropped (CP5.1 forms are not comments), and C++14 digit separators are shielded around `strip_comments` (CP4 `1'000; // c`); `strip_comments` itself is unchanged.

## WU2: Arch v2 and windowed scoring (parallel with WU1)

- [x] 2.1 RED `tests/test_char_cnn_v2_model.py`: no `_BatchNorm` module; padding invariance (0/100/3000 extra PAD, atol 1e-5, eval, seeded tiny model); batch-1 vs mixed-length batch; masked pooling ignores pad values; v1 `CharCNN` still loads a v1 state_dict `strict=True`. GREEN `models/char_cnn/v2/model.py` (`CharCNNV2`: masked embed, per-kernel Conv1d + channel LayerNorm + ReLU + mask, masked max/mean, one dropout, `fc1` embedding 1024-d, `fc2`; `forward(x, return_embedding=False)`). Imports `v2/config.py` from 1.1 (hence WU2 starts after 1.1). [CI1, CI2, D6, D7]
- [x] 2.2 RED `::windows`: `window_starts` (n<=4096 -> 1; 6144 -> 2; 6145 -> 3; 100000 -> 8 `linspace`, first start 0, last window ends at input end; deterministic); stub forward with a constant per window gives the mean of logits; random-crop helper deterministic per key and length 4096. GREEN `models/char_cnn/v2/scoring.py` (`window_starts`, `score_arrays`, `predict_one`). [CI3, CT2.3 crop part, D8]
- Check: `python -m pytest tests/test_char_cnn_v2_model.py -q -p no:cacheprovider`.
- Evidence: RED 2.1 `ModuleNotFoundError: models.char_cnn.v2.model`, 2.2 `ModuleNotFoundError: models.char_cnn.v2.scoring` -> GREEN 26 passed; full suite 492 passed, 1 skipped, only the known `test_graphcodebert_calibration` failure. Under the cap, the last window start is aligned to `n - window` (every window is full length; 6145 -> starts 0, 2048, 2049).

## WU3: Inference facade (3.1 first, before any other edit to inference.py)

- [x] 3.1 Capture the golden snapshot with the PRE-change code: add `tests/fixtures/charcnn_legacy_golden.json` (all outputs of `predict_text` on 3 snippets with the real `best_model.pth` on CPU, plus a v1 fixture-checkpoint output from seeded random v1 weights built via `CharCNN`) and a legacy golden table of v1 preprocess/encode outputs (CRLF, tabs, diacritics); test in `tests/test_char_cnn_v2_inference.py::legacy_golden` (real-weight cases under the existing `requires_charcnn_weights` marker, tol 1e-6). Must pass on the untouched facade; commit as `test(charcnn): capture legacy golden snapshot`. [CP10.1, CI7.1, CI8.1]
  - Evidence 3.1: captured with the untouched facade (CPU, torch 2.13); `tests/test_char_cnn_v2_inference.py` 9 passed before any `inference.py` edit. Fixture v1 weights come from numpy `RandomState` (torch-init independent, always runs); real-weight cases are pinned to `best_model.pth` sha256 `58f7007479de3b654461c77ad312462465c0d1d8307cd38890b4791bc3b9ca69` (the committed file) and skip on any other hash.
- [ ] 3.2 RED `::contract`: fake legacy checkpoint gives all legacy keys + `arch_version=1`, `preproc_version=1`, `n_windows=1`, `abstained == insufficient_length`; fake tiny v2 checkpoint (non-default conv sizes) rebuilt from its config reproduces logits within 1e-6, all legacy + new keys, floats in [0,1], `score == ai_probability`; `"int x;"` abstains with `score is None` and float legacy keys; unknown `arch_version` raises `ValueError`; absent `preproc_version` selects v1; v2 `config` argument ignored with warning. [CI4-CI7, CP10.2, NF2, D14, D15]
- [ ] 3.3 GREEN `models/char_cnn/inference.py`: version dispatch; legacy bodies moved verbatim into private methods plus new keys; v2 branch via `v2/scoring.py`; constructor and `predict`/`predict_text`/`main` signatures unchanged. Add checkpoint loader helper (`weights_only=True`) in `models/char_cnn/v2/checkpoint.py` if needed by 5.x.
- [ ] 3.4 Regression: `tests/test_char_cnn_{guard,canonical,robustness}.py`, `backend/tests/` and `tests/test_calibration_experiment.py` pass unmodified (legacy assertions). [CI8.1]
- Check: `python -m pytest tests/test_char_cnn_v2_inference.py tests/test_char_cnn_guard.py tests/test_char_cnn_canonical.py tests/test_char_cnn_robustness.py backend/tests -q -p no:cacheprovider`.

## WU4: Encoded data and epoch sampler

- [ ] 4.1 RED `tests/test_char_cnn_v2_data.py`: fixture manifest (`eval_factory`) -> `load_encoded` returns train representatives only, labels `source == "ai"`, broken excluded, `on_text` called once per file with raw+normalized, missing file raises `FileNotFoundError` with a count, no id in two splits. GREEN `models/char_cnn/v2/data.py` (`EncodedSet`, `load_encoded` over `load_manifest(...).samples(split, representatives_only=True)` plus all-test view). [CT1, D2]
- [ ] 4.2 RED `::epochs`: per epoch all AI + equal humans (1:1) via `stable_rng(seed, f"epoch{n}")`; reproducible per (seed, epoch), differs between epochs when humans > AI; humans < AI uses all and records the shortfall; crops <= 4096 and equal for the same (seed, epoch, id); collate right-pads 0. GREEN `epoch_batches`, `collate` (sortish bucketing, `num_workers=0`). [CT2.2-2.3, D9]
- Check: `python -m pytest tests/test_char_cnn_v2_data.py -q -p no:cacheprovider`.

## WU5: Seeded trainer, selection, leak guard

- [ ] 5.1 RED `tests/test_char_cnn_v2_train.py::selection`: stubbed val metrics (0.80, 0.90, 0.90 with PR 0.7/0.6/0.8) select epoch 2; null AUC epochs are never selected; tie goes to the earlier epoch. GREEN selection tuple + `ReduceLROnPlateau(mode="max")` + early stop in `models/char_cnn/v2/train.py`. [CT3.1, D10]
- [ ] 5.2 RED `::run`: tiny config (window 256, stride 128, dims 8/4/16, 2 epochs, CPU) on the factory tree: `seed_everything(deterministic)` called before model/data; no train-mode call before the first real batch (hook); only `runs/<root>/char_cnn/<ts>/` written; `config.json` has CT5.2 keys incl. `manifest_sha256` equal to the loader hash; `best.pth` loads with `weights_only=True` and embeds the full config; `history.csv` rows; no promote call (spy). GREEN `train.py` CLI (`python -m models.char_cnn.v2.train`, flags per design), `RunContext.create("char_cnn", ...)`. [CT1-CT2, CT5.1/5.2/5.4, CT9.3, CI6.1, D12]
- [ ] 5.3 RED `::guard`: fixture whose preprocessing is monkeypatched to leak -> exit code 2, `leak_guard.json` written, `runs/` has no checkpoint; clean fixture passes with shares 0. GREEN guard wiring in step 4 of the trainer (human representatives, all splits). [CP9.2]
- [ ] 5.4 RED `::determinism`: two CPU runs (`--epochs 2 --seed 1`) give identical `history.csv`, selected epoch and `best.pth` tensors. Real `best_model.pth` sha256 before/after unchanged. [CT4.1, CT5.1, NF3]
- Check: `python -m pytest tests/test_char_cnn_v2_train.py -q -p no:cacheprovider`.

## WU6: Calibration, test report, shortcut audit

- [ ] 6.1 RED `tests/test_char_cnn_v2_train.py::evaluate`: calibration fit inputs (spy) contain only val ids; test scored exactly once, after `calibration.json` exists; headline `n` = representatives, secondary (`test_all/`) `n` = all non-broken, both labelled; CI grouped by `dup_group`; a 2-sample group is `low_support`, an empty group gives `n=0`/null metrics without raising; `per_generator` for model/profile with `low_support` at n_pos < 30; `n_abstained` reported. GREEN `models/char_cnn/v2/evaluate.py` (`evaluate_run`), config rewrite with calibration ref (D12). [CT3.2-3.3, CT6, D11, D13, D16]
- [ ] 6.2 RED `tests/test_char_cnn_v2_shortcuts.py`: only human files have `using namespace std;` -> human 1.0, AI 0.0; all CT7 keys present for both classes, raw and normalized; length buckets; report-only (training inputs unchanged). GREEN `models/char_cnn/v2/shortcuts.py` (`on_text` accumulators fed in the data pass), `shortcuts.json`, "Shortcut audit" section in `report.md`, `scores_val.csv`/`scores_test.csv`. [CT7, CT5.3]
- [ ] 6.3 Integration: the 5.2 fixture run contains every CT5.3 artifact; `evaluate_run` is invoked by `train.main`. Check: `python -m pytest tests/test_char_cnn_v2_train.py tests/test_char_cnn_v2_shortcuts.py -q -p no:cacheprovider`.

## WU7: Legacy baseline and promote (parallel with WU8)

- [ ] 7.1 RED `tests/test_char_cnn_v2_promote.py` (fake git runner, tmp target only): dirty target refuses (non-zero, bytes unchanged); `--force` copies + writes `best_model.provenance.json`; clean target copies; `--dry-run` writes nothing; source without version fields refused. GREEN `models/char_cnn/v2/promote.py`. Never executed against the real repo. [CT9.1-9.2, D14]
- [ ] 7.2 RED `tests/test_char_cnn_v2_inference.py::baseline` (or `test_char_cnn_v2_baseline.py`): legacy-format fixture checkpoint + fixture manifest -> output has `contaminated: true`, note about overlap and differing preprocessing, legacy-path metrics, `argmax_0.5` point `source: "manual"`, `file_sha256` before == after, headline/`test_all` views. GREEN `models/char_cnn/v2/baseline.py` -> `runs/char_cnn_legacy/<ts>/`. [CT8.1]
- Check: `python -m pytest tests/test_char_cnn_v2_promote.py tests/test_char_cnn_v2_baseline.py -q -p no:cacheprovider`.

## WU8: Deprecations, train.py delegation, README

- [ ] 8.1 RED `tests/test_char_cnn_v2_promote.py::deprecation` (or `tests/test_char_cnn_v2_cleanup.py`): `data/train_charcnn.py` absent; `prepare_dataset.py` and `dataset_manifest.json` present; `pytest.warns(DeprecationWarning)` on importing `models.char_cnn.prepare_dataset`. GREEN: delete `data/train_charcnn.py`; deprecation docstring + import-time warning in `models/char_cnn/prepare_dataset.py`. [CT10.1]
- [ ] 8.2 Edit `models/char_cnn/train.py`: remove `save_checkpoint`/`setup_model`/`run_training`; keep `evaluate`, `compute_metrics`, `train_epoch`; `main` delegates to `v2.train.main`. Regression: `scripts/generate_tt_figures.py` import path still resolves; existing char_cnn tests pass. [D1]
- [ ] 8.3 Rewrite `models/char_cnn/README.md`: arch v1/v2, preprocess v2, CLIs (train, baseline, promote), run layout, deprecations, limitations (domain shift Bosnian vs Spanish, single dominant generator, small AI counts). Results section stays "pending" until WU9. [docs]
- Check: full suite (see 9.6) is green apart from the known failure.

## WU9: Real-data runs and honest reporting (user-visible; CUDA)

- [ ] 9.1 Preflight: record sha256 of `models/char_cnn/best_model.pth` (BEFORE); confirm `torch.cuda.is_available()`; confirm `data/splits/split_v1.json.gz` sha256 and `git status` shows only the pre-existing `best_model.pth` modification.
- [ ] 9.2 Leak guard + training on `split_v1`: `python -m models.char_cnn.v2.train --device cuda --seed 42` (defaults per design). Record seed, device, torch version, per-stage timings (load/encode, per epoch, evaluate), selected epoch, `leak_guard.json` shares. DECISION D-A: if the guard exits 2, stop and report offending patterns/ids; do not weaken the threshold or patch silently. [CP9.2, CT2-CT3]
- [ ] 9.3 Confirm the run dir `runs/char_cnn/<ts>/` holds `metrics.json` (observed/balanced, CI95 by `dup_group`), per-group + `per_generator`, `calibration.json` (val only), `shortcuts.json`, `report.md`, `test_all/`. Test was evaluated once. [CT5.3, CT6, CT7]
- [ ] 9.4 Legacy baseline: `python -m models.char_cnn.v2.baseline --checkpoint models/char_cnn/best_model.pth` -> `runs/char_cnn_legacy/<ts>/`, labelled `contaminated: true`. Re-hash `best_model.pth` (AFTER) and assert equal to BEFORE (NF3); note the file is the user's uncommitted version. [CT8.1, NF3]
- [ ] 9.5 Commit selected artifacts with `git add -f` (eval-foundation D9): `config.json`, `metrics.json`, `report.md`, `calibration.json`, `shortcuts.json`, `leak_guard.json` from both runs as applicable (NOT `best.pth`, scores CSVs or any weights; never stage `models/char_cnn/best_model.pth`). Commit `data(charcnn): add v2 run and legacy baseline reports`. DECISION D-C: which run dirs to commit if several attempts exist.
- [ ] 9.6 Update `models/char_cnn/README.md` results with honest numbers (headline on representatives, secondary all-files view, CIs, low-support flags, shortcut residuals, legacy baseline marked contaminated and not comparable to the old 96% claim, limitations); commit `docs(charcnn): report v2 results and limitations`. Promotion is out of scope: report that the user decides on promote (SDD-4); do not run it.
- [ ] 9.7 Full verification: `python -m pytest tests/ backend/tests/ -q -p no:cacheprovider` (expect only the known `test_graphcodebert_calibration` failure); `git diff --stat -- models/evaluation` is empty; `git status` shows `best_model.pth` still modified-by-user and nothing else unexpected. Parent spot-checks one reported command.

## Decisions Needed

- D-A (9.2): leak guard aborts on real data -> user decides how to proceed (extend stripping, adjust patterns, or accept); apply must not change the threshold.
- D-B (before WU1): `autotest` in `course_marker` guard pattern (spec CP9.1) while not stripped (design). Default adopted: guard-only; if it aborts on real data this becomes D-A.
- D-C (9.5): which artifacts and run dirs to commit if multiple attempts exist.
- Promotion of the v2 checkpoint, push, PR and merge remain user decisions (out of scope here).
