# Spec: fix-charcnn-implementation

Keywords follow RFC 2119. Scenarios MUST be testable with pytest on small synthetic fixtures (tiny strings, a handful of fake source files, a fixture manifest, a tiny randomly initialised model on CPU). No real corpus and no real weights are needed, except scenarios explicitly marked `[legacy-compat]`, which load `models/char_cnn/best_model.pth` and MUST be guarded by a skip-if-missing marker. Consumed unchanged from `eval-foundation`: `load_manifest`/`samples(representatives_only)`, `models.evaluation` metrics (ROC-AUC, PR-AUC, bootstrap CI by `dup_group`, per-group breakdown, observed/balanced views), val-only calibration, `RunContext`, `seed_everything`, `stable_rng`, `normalize.strip_comments`. Constants: `PREPROC_VERSION = 2`, `ARCH_VERSION = 2`, window 4096, stride 2048, window cap 8, leak threshold 0.1%.

## Capability: charcnn-preprocessing (new)

### CP1. Pipeline, order and versioning
- CP1.1 `preprocess_v2(text) -> str` MUST apply, in this order: (1) CRLF/CR to LF, delete C0 controls (except LF and TAB handled by CP6) and zero-width characters; (2) NFKD diacritic stripping, Unicode punctuation folding, drop remaining non-ASCII; (3) comment removal via `models.evaluation.normalize.strip_comments`; (4) header/boilerplate stripping; (5) canonical whitespace.
- CP1.2 The module MUST expose `PREPROC_VERSION = 2`. Encoded output and checkpoints MUST be traceable to this value.
- CP1.3 The function MUST be pure and idempotent: `f(f(x)) == f(x)`.
- CP1.4 The function MUST NOT receive or depend on the class label.

Scenarios
- Given text with CRLF, a form feed and a zero-width space, When preprocessed, Then the output contains none of `\r`, `\x0c`, `​`.
- Given any fixture string, When `f` is applied twice, Then the result equals the single application.
- Given a string whose comment contains the text `Zadaca 1, Zadatak 1`, When preprocessed, Then the comment is gone before header stripping and the output has no such text.

### CP2. Control, CR and zero-width removal
- CP2.1 CR and CRLF MUST become a single LF. C0 controls other than LF and TAB, DEL, and zero-width characters (U+200B-U+200D, U+2060, U+FEFF) MUST be removed.

Scenarios
- Given `"a\r\nb\rc\x01d\x7fe﻿"`, Then the output is `"a\nb\ncde"`.

### CP3. Unicode folding
- CP3.1 Diacritics MUST be stripped (`ć`, `č`, `š`, `đ`, `ž`, `á`, `ñ` fold to base letters; `đ` MUST fold to `d`). Curly quotes MUST map to `'`/`"`, en/em dashes to `-`, NBSP to space.
- CP3.2 Any remaining non-ASCII character MUST be dropped. It MUST NOT be encoded as UNK.

Scenarios
- Given `"Zadaća šđ “x” – y z"`, When folded, Then the result is `Zadaca sd "x" - y z` (before later steps).
- Given a string containing `✓` or an emoji, When encoded, Then no index equals the UNK index for those characters and the sequence length excludes them.

### CP4. Comment removal
- CP4.1 Comment removal MUST delegate to `models.evaluation.normalize.strip_comments` (single implementation, no copy). It MUST be string- and char-literal-aware.

Scenarios
- Given `int x = 1'000; // c`, Then `1'000` survives and `// c` is removed.
- Given `char c = '"'; int y; // c`, Then the output keeps `'"'` and `int y;`.
- Given `puts("http://a"); /* b */`, Then `//` inside the string survives and the block comment is removed.

### CP5. Header and boilerplate stripping
- CP5.1 Leading course-header lines MUST be removed, including these forms (all MUST yield the same result as the body alone): `/\x01B\x0216/17 (Zadaća 6, Zadatak 4)`, `/B2017/2018: Zadaća 4, Zadatak 2`, `   B16/17 (Tutorijal 13, Zadatak 1)`.
- CP5.2 An output statement line (`printf`, `puts`, `cout`, optionally `std::`) that contains a course marker (`Zadaća|Zadatak|Tutorijal`, any diacritic form, any case) MUST be removed entirely, because a token-only removal would leave a human-only residue such as `printf("  ,  ");`. Any remaining marker token (with an optional number) MUST then be removed in all positions, including inside string literals.
- CP5.3 Stripping MUST NOT remove ordinary identifiers or code lines that do not match these patterns.

Scenarios
- Given each of the three header examples followed by `int main(){}`, Then the output equals `preprocess_v2("int main(){}")`.
- Given a body containing the line `printf("Zadaća 5, Zadatak 3");`, Then that whole line is removed, no `zadac`/`zadat` substring (case-insensitive) remains, and the output equals the body without that line.
- Given `x = 1; /* Zadatak 2 */ int zadatak_count = 0;` after comment removal, Then `zadatak_count` is preserved (no number follows, CP5.3).
- Given `int zadatak_count = 0;` (no number token pattern), Then the identifier is preserved.

### CP6. Canonical whitespace
- CP6.1 Output MUST keep line breaks (LF only) while removing layout: tabs become spaces; outside single-line string/char literals runs of 2+ spaces collapse to one; each line is stripped (no leading indentation, no trailing spaces); empty lines are dropped; lines are joined with `\n` and no trailing newline.

Scenarios
- Given the same program with 2-space, 4-space, tab and brace-on-next-line styling, When preprocessed and encoded, Then all encodings are identical except where token boundaries differ (see CP8).

### CP7. Alphabet
- CP7.1 PAD MUST be index 0 and UNK a distinct non-zero index. Every printable ASCII character, LF and space MUST have its own index. `encode` MUST map characters outside the alphabet to UNK only for ASCII characters not in the alphabet (none expected after CP3); PAD MUST appear only as padding.

Scenarios
- Given the alphabet, Then `PAD != UNK`, and `encode("abc")` contains no 0.
- Given padding applied to a batch, Then padded positions equal PAD and no encoded real character equals PAD.

### CP8. Class symmetry
- CP8.1 Two renderings of the same program that differ only in formatting artifacts removed by CP1-CP6 (CRLF vs LF, tabs vs spaces, trailing whitespace, header presence, comments, diacritics) MUST encode identically, regardless of which class the file came from.

Scenarios
- Given a "human-styled" variant (CRLF, tabs, header line, diacritic comment) and an "AI-styled" variant (LF, 4 spaces, no header, no comments) of the same program, Then `encode(preprocess_v2(a)) == encode(preprocess_v2(b))`.

### CP9. Leak guard
- CP9.1 A `leak_patterns` list MUST cover: non-ASCII, `\r`, C0 controls, tabs, course markers (`Zadaca|Zadatak|Tutorijal|autotest`, case-insensitive) in preprocessed text.
- CP9.2 `leak_guard(texts, threshold=0.001)` MUST return per-pattern match shares over the supplied human texts and MUST raise `LeakGuardError` when any share exceeds the threshold. The training CLI MUST call it on preprocessed human train files before the first epoch and abort without writing a checkpoint.

Scenarios
- Given 1000 clean human fixtures, Then the guard passes with shares 0.
- Given 1000 fixtures where 2 (0.2%) contain a surviving marker (guard fed a pre-stripped text with marker injected), Then `LeakGuardError` is raised naming the pattern; given 1 of 1000 (0.1%), Then it passes (threshold is strict `>`).
- Given the trainer CLI on a fixture whose preprocessing is monkeypatched to leak, Then it exits non-zero and `runs/` contains no checkpoint.

### CP10. Legacy path frozen
- CP10.1 The v1 preprocessing and encoding (current behavior, including UNK == PAD == 0) MUST be retained as a distinct frozen function and MUST produce byte-identical output to the pre-change implementation for the same input.
- CP10.2 A checkpoint without `preproc_version` MUST use the v1 path; a checkpoint with `preproc_version: 2` MUST use v2.

Scenarios
- Given a golden table of inputs and their pre-change v1 encodings captured in the test file (including CRLF, tabs, diacritics), Then the v1 function reproduces them exactly.
- Given a checkpoint dict lacking `preproc_version`, Then the selected preprocessor is v1.

## Capability: charcnn-training (new)

### CT1. Data source and labels
- CT1.1 Train and val samples MUST come from the `split_v1` manifest via `load_manifest`/`samples(split, representatives_only=True)`; the trainer MUST NOT read `dataset_manifest.json` or `prepare_dataset.py` outputs.
- CT1.2 Label MUST be `1` iff `source == "ai"`, else `0`. Broken entries MUST be excluded (loader default).
- CT1.3 Split membership MUST NOT overlap: no id appears in more than one of train/val/test.

Scenarios
- Given a fixture manifest with train/val/test entries and non-representative duplicates, Then the trainer's train set contains only train representatives and labels match `source`.

### CT2. Seeding, resampling, no dummy pass
- CT2.1 The trainer MUST call `seed_everything(seed, deterministic=True)` before building model and data.
- CT2.2 Each epoch MUST use all train AI files plus a human sample of equal size (1:1) drawn with `stable_rng` keyed on (seed, epoch); the draw MUST be deterministic per (seed, epoch) and MUST differ across epochs when human count exceeds AI count. If humans < AI, all humans MUST be used and the shortfall recorded in `config.json`.
- CT2.3 Training MUST take a random crop of at most 4096 characters, seeded; the trainer MUST NOT run a train-mode dummy forward pass.

Scenarios
- Given 3 AI and 10 human train fixtures, Then each epoch yields 3 AI + 3 human; epoch 0 and epoch 1 human sets are each reproducible when recomputed and differ from each other.
- Given a model with a forward hook counting train-mode calls, Then no call occurs before the first real batch.
- Given a 9000-char sample and a fixed seed, Then two crops under the same (seed, epoch, index) are equal and have length 4096.

### CT3. Selection, calibration, test
- CT3.1 The checkpoint MUST be selected by highest val ROC-AUC, ties broken by higher val PR-AUC, then earlier epoch. Epochs with null AUC (single class) MUST NOT be selected.
- CT3.2 Platt calibration MUST be fitted on val scores only, using the selected checkpoint, and saved in the run directory.
- CT3.3 Test MUST be evaluated exactly once, after selection and calibration, with the selected checkpoint.

Scenarios
- Given stubbed per-epoch val metrics (0.80, 0.90, 0.90 with PR-AUC 0.7/0.6/0.8), Then epoch 2 is selected.
- Given a spy on the test-evaluation function, Then it is called once, after the calibration file exists.
- Given calibration fit with a spy on its inputs, Then no test or train id is present.

### CT4. Reproducibility
- CT4.1 Two runs on CPU with the same fixture manifest, seed and config MUST produce identical per-epoch val metrics, identical selected epoch, identical test metrics and identical selected-checkpoint tensors.

Scenarios
- Given a fixture tree (about 12 files) and `--epochs 2 --seed 1 --device cpu` run twice, Then `metrics.json` content (excluding timestamps and run directory) and checkpoint state_dict tensors are equal.

### CT5. Output location and artifacts
- CT5.1 The trainer MUST write only under `runs/char_cnn/<ts>/` (default root overridable for tests). It MUST NOT write `models/char_cnn/best_model.pth` or any other path under `models/`.
- CT5.2 `config.json` MUST record `arch_version`, `preproc_version`, alphabet, conv sizes, dropout, seed, epochs, learning rate, manifest sha256 (as reported by the loader) and git commit if available.
- CT5.3 The run directory MUST contain: `config.json`, selected checkpoint, per-epoch val metrics, calibration file, test metrics, per-group breakdown and `shortcuts.json`.
- CT5.4 The checkpoint MUST embed the full model config (CI6).

Scenarios
- Given a fixture run with the repo's `models/char_cnn/best_model.pth` hashed before and after (or absent), Then its hash is unchanged and no file under `models/` has a newer mtime.
- Given the run directory, Then every CT5.3 artifact exists and `config.json.manifest_sha256` equals the fixture manifest's loader hash.

### CT6. Metrics report
- CT6.1 Metrics MUST be computed with `models.evaluation`, reporting `observed` and `balanced` views, ROC-AUC, PR-AUC and threshold metrics, with CI95 bootstrapped by `dup_group`.
- CT6.2 The report MUST include per-group breakdowns by lang, course, profile, model and length bucket; groups with low support MUST be flagged and groups with `n=0` MUST NOT raise.
- CT6.3 The test headline MUST be computed on representatives only; a secondary view over all test files (non-broken) MUST also be reported, with CI bootstrapped by `dup_group`. Both MUST be labelled.

Scenarios
- Given a fixture test split with duplicates, Then the headline `n` equals the representative count and the secondary `n` equals the all-files count.
- Given a group with 2 samples, Then it is present with a `low_support` flag; a group with none yields `n=0`, null metrics.

### CT7. Shortcut report
- CT7.1 `shortcuts.json` MUST contain, per class (human, ai), the share of files that still contain: non-ASCII, course markers, control/CR/tab characters, `std::`, `using namespace`, `#include <bits/`, and a non-code first line; plus length bucket shares. It MUST be reporting only and MUST NOT alter training or scores.

Scenarios
- Given fixtures where only human files contain `using namespace std;`, Then `shortcuts.json` has human share 1.0 and ai share 0.0 for that key, and training inputs are unchanged by the report.

### CT8. Legacy baseline
- CT8.1 A baseline entry point MUST evaluate a legacy checkpoint through the same harness on `split_v1` test (CT6 views) and the report MUST carry `contaminated: true` with a note that the legacy split overlaps test and preprocessing differs.

Scenarios
- Given a legacy-format fixture checkpoint (random weights, no version fields) and a fixture manifest, When the baseline runs, Then output includes `contaminated: true` and metrics from the legacy path.

### CT9. Promote CLI
- CT9.1 A promote CLI MUST copy a chosen run checkpoint to `models/char_cnn/best_model.pth` (target overridable) and record provenance (run dir, checkpoint sha256, config sha256, timestamp) in a sidecar file.
- CT9.2 It MUST refuse (non-zero exit, no write) when the target is git-modified or untracked-modified, unless `--force` is given. It MUST refuse when the source checkpoint lacks version fields.
- CT9.3 SDD-2 execution (trainer, baseline, tests) MUST NOT invoke the promote CLI.

Scenarios
- Given a temp git repo whose target file has uncommitted changes, When promote runs without `--force`, Then exit is non-zero and the target bytes are unchanged; with `--force`, Then bytes equal the source and provenance exists.
- Given a clean tracked target, When promote runs, Then the copy succeeds with provenance.
- Given the trainer end-to-end on a fixture, Then a spy on the promote entry point is never called.

### CT10. Deprecation and cleanup
- CT10.1 `data/train_charcnn.py` MUST be removed. `models/char_cnn/prepare_dataset.py` and `models/char_cnn/dataset_manifest.json` MUST remain and MUST be marked deprecated (module docstring/top-level note stating replacement by `split_v1`). Importing `prepare_dataset` MUST emit a `DeprecationWarning`.

Scenarios
- Given the repo, Then `data/train_charcnn.py` does not exist, both deprecated files exist, and importing `prepare_dataset` raises a `DeprecationWarning` under `pytest.warns`.

## Capability: charcnn-inference (new)

### CI1. Architecture v2
- CI1.1 Arch v2 MUST use masked average and max pooling over real (non-PAD) positions, channel LayerNorm, and a single dropout. It MUST NOT contain any `BatchNorm` module. Batch size 1 MUST NOT be special-cased.
- CI1.2 Arch v1 MUST remain available for legacy loading.

Scenarios
- Given a v2 model, Then `any(isinstance(m, nn.modules.batchnorm._BatchNorm) for m in model.modules())` is False.
- Given a v1 state_dict fixture, Then the v1 class loads it with `strict=True`.

### CI2. Padding invariance
- CI2.1 In eval mode, v2 logits for a sequence MUST be equal within 1e-5 with and without extra trailing PAD, and for batch size 1 versus the same sequence inside a batch of N with mixed lengths.

Scenarios
- Given a random-weight v2 model (seeded) and a sequence of 300 chars, Then logits with 0, 100 and 3000 extra PAD are within 1e-5.
- Given 4 sequences of different lengths, Then batched logits match one-at-a-time logits within 1e-5.

### CI3. Sliding windows
- CI3.1 Inputs up to 4096 encoded chars MUST use one window. Longer inputs MUST be scored with windows of 4096 and stride 2048, up to a cap of 8 windows, averaging logits; `n_windows` MUST report the count used. Inputs beyond the cap MUST use 8 evenly spaced window starts (`linspace`) whose first window starts at 0 and whose last window ends at the end of the input.
- CI3.2 Window selection MUST be deterministic.

Scenarios
- Given encoded length 4096, Then `n_windows == 1`; length 6144, Then 2; length 6145, Then 3.
- Given length 100000, Then `n_windows == 8`.
- Given a stub forward returning a different constant per window, Then the output equals the mean of per-window logits.

### CI4. Result contract
- CI4.1 `CharCNNInference` constructor and `predict`/`predict_text` signatures MUST be unchanged. Returned dict MUST keep keys `prediction, class_id, confidence, prob_humano, prob_sintetico, ai_probability, embedding, insufficient_length` with the same value types (Python floats, `embedding` list or array as before) and add `score`, `abstained`, `n_windows`, `preproc_version`, `arch_version`.
- CI4.2 `score` MUST equal the AI probability as a float when not abstained.

Scenarios
- Given a v2 fixture checkpoint and a normal input, Then all legacy keys and all new keys are present, probabilities are `float`, `0 <= ai_probability <= 1`, `score == ai_probability`, `abstained is False`.

### CI5. Abstention
- CI5.1 When the preprocessed input is below the minimum length (existing `insufficient_length` threshold), the result MUST have `score is None`, `abstained is True`, `insufficient_length is True`, and the legacy numeric keys MUST still be present as floats so existing consumers do not break.

Scenarios
- Given input `"int x;"`, Then `abstained is True`, `score is None`, and `prob_humano`, `prob_sintetico`, `ai_probability`, `confidence` are floats.

### CI6. Checkpoint config
- CI6.1 A v2 checkpoint MUST store `arch_version`, `preproc_version`, alphabet, conv sizes, dropout, window parameters and calibration reference (if any); loading MUST rebuild the model from these fields only, without caller-supplied architecture arguments.

Scenarios
- Given a model saved with non-default conv sizes, Then `CharCNNInference(path)` reconstructs it and reproduces the saved model's logits within 1e-6.

### CI7. Legacy checkpoint loading
- CI7.1 A checkpoint lacking `arch_version`/`preproc_version` MUST load through a frozen legacy path using v1 architecture and v1 preprocessing, with unchanged numeric behavior. Result keys MUST report `preproc_version: 1`, `arch_version: 1` and `n_windows: 1`.

Scenarios
- Given a fixture legacy checkpoint (random v1 weights, no version fields) and a golden output captured from the pre-change code path, Then probabilities match within 1e-6.
- `[legacy-compat]` Given the real `models/char_cnn/best_model.pth`, Then it loads and returns legacy keys plus `arch_version == 1` (skip if the file is missing).

### CI8. Consumers
- CI8.1 `backend/app/infrastructure/inference/real_engine.py` and existing scripts MUST work unchanged using only legacy keys.

Scenarios
- Given the existing `tests/test_char_cnn_*` legacy cases and consumer tests, Then they pass unmodified in their legacy assertions.

## Cross-cutting non-functional requirements

- NF1. `models.evaluation` MUST be unchanged (no diff under `models/evaluation/`); the change only imports it.
- NF2. The backend API float contract MUST be preserved: all probability fields are JSON-serializable Python floats in [0, 1]; `score=None` is only an added field.
- NF3. `best_model.pth` MUST be byte-identical before and after the change (verified by sha256 in the verification step).
- NF4. No new runtime dependencies beyond torch and the existing stack.
