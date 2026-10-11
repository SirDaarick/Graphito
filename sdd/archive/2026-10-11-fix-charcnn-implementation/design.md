# Design: Fix CharCNN Implementation (fix-charcnn-implementation)

## Technical Approach

The legacy CharCNN code stays frozen and keeps serving `models/char_cnn/best_model.pth`. All new behavior lives in a subpackage, `models/char_cnn/v2/`: preprocess v2, arch v2, manifest data, trainer, evaluation, shortcut report, legacy baseline and promote. `models/char_cnn/inference.py` is the single facade. It reads the checkpoint's version fields and picks the frozen legacy path or the v2 path, so the backend (`real_engine.py:47-79`), `models/fusion.py:53-58` and the `scripts/` consumers keep their constructor, `predict`/`predict_text` and key contract. Training reads `data/splits/split_v1.json.gz` through `models.evaluation` and writes only under `runs/`. It reports through the SDD-1 toolkit (`calibration.build_calibration`, `report.compute_metrics`, `RunContext`), and no `models/evaluation` API changes.

## Architecture Decisions

| # | Decision | Rejected alternative | Rationale |
|---|----------|----------------------|-----------|
| D1 | New code goes in `models/char_cnn/v2/`. `preprocess.py`, `model.py`, `dataset.py` and `config.py` get **zero edits**. `inference.py` gains a version dispatch. `train.py` keeps `evaluate`/`compute_metrics`/`train_epoch`, and its `main` delegates to the v2 CLI. | Versioned functions inside the existing files | `tests/test_char_cnn_{guard,canonical,robustness}.py` import `CharPreprocessor`, `CharCNNDataset`, `rebase_path`, `CharCNN`, `evaluate` and `compute_metrics`. `scripts/generate_tt_figures.py:21` imports `train.compute_metrics`. Untouched files are byte-identical by construction, so no diff review is needed to prove the legacy path is frozen. `CharCNNConfig.__post_init__` creates `weights/` and `logs/` on construction, so v2 uses its own side-effect-free dataclass. |
| D2 | Representatives come from `load_manifest(path, expected_sha256).samples(split, representatives_only=True)`. | `load_split(..., representatives_only=True)` as written in the proposal | `load_split` has no such parameter (`manifest.py:309-323`). This uses the same API without modifying it. |
| D3 | Pipeline order follows the proposal: newlines/controls → Unicode fold → `strip_comments` → course markers → whitespace (see Preprocessing v2). | Stripping comments before folding | Folding first can turn a curly quote inside a literal into a delimiter. That only matters when a `//` follows inside the same literal, which is very rare. Keeping the proposal order keeps design and spec aligned. Newline normalization **must** come before `strip_comments`, because a CR-only file would otherwise become one giant `//` comment. |
| D4 | Whitespace v2 keeps the lines. Tabs become spaces, each line is stripped (indentation removed), runs of spaces outside literals collapse to one, and empty lines are dropped. | Legacy `canonical` (removes all layout whitespace, newlines included); expanding tabs to 4 spaces | Tabs and indentation come from the editor (only human files have tabs). `strip_comments` keeps the line count, so header comments leave blank-line blocks only in human files. Dropping indentation and blank lines removes both leaks. Line structure and operator spacing are real style, so they stay. Tab expansion would keep the editor artifact. |
| D5 | Alphabet = `\n` + ASCII 0x20-0x7E (96 symbols). PAD=0, UNK=1, alphabet[i] → i+2, vocab 98. Encoded arrays are `np.uint8`. | Keeping the 122-symbol legacy alphabet with UNK=PAD=0 | Non-ASCII is dropped before encoding, so UNK cannot appear. It stays distinct only for robustness. uint8 cuts the cache 8x compared with int64. |
| D6 | Normalization is a per-position LayerNorm over channels (`LayerNorm(C)` on the transposed tensor). | BatchNorm (couples the batch and pollutes running stats); `GroupNorm(1, C)` (its statistics include padded positions) | It is the only option of the three that neither depends on the batch nor sees padding. It also removes the batch-size-1 special case (`model.py:69-72`). |
| D7 | Masking: the embedding output is multiplied by the mask, each branch is a single conv layer, and pooling is masked (max uses `-inf` fill, average is `sum/len`). | Masking after every layer of a stacked CNN | With right padding, a zero PAD embedding equals the conv's implicit zero padding, so valid positions see identical inputs. LayerNorm and ReLU act per position, and pooling ignores pad positions. Output is therefore padding-invariant up to float summation order, and the test uses tolerance 1e-5. |
| D8 | Windows: training takes a random 4096 crop. Inference, val and test all use the same `score_arrays`: window 4096, stride 2048, at most 8 windows (evenly spaced starts via `linspace` when there would be more). Logits and embeddings are averaged over windows. | Head+tail truncation (legacy `preprocess.py:105-109`) | One code path for val, test and deployment. Every window has the training length distribution. |
| D9 | Each epoch uses all AI train representatives plus `stable_rng(seed, f"epoch{n}").sample(sorted human ids, n_ai)`. The rng shuffles the list, then sortish bucketing runs (chunks of 50 batches, sorted by cropped length, batch order shuffled) with dynamic padding. Crop offset = `stable_rng(seed, f"epoch{n}:crop:{id}")`. `num_workers=0`, with no `DataLoader` shuffle. | DataLoader workers; a WeightedRandomSampler | Order-independent keyed RNG makes epochs reproducible. Data is in RAM and collation is cheap, so worker processes buy nothing and Windows spawn costs pickling the cache. |
| D10 | Selection uses val ROC-AUC (raw scores, val representatives), with the lexicographic tuple `(roc_auc, pr_auc)` and the earlier epoch winning ties. Scheduler: `ReduceLROnPlateau(mode="max")` on val ROC-AUC. Early stop on the same tuple. No AMP. | Val loss (legacy); AMP fp16 | AUC is threshold- and prevalence-free, which matches the reported headline. Skipping AMP avoids fp16 rounding flipping selection, and the model is small enough. |
| D11 | Stages are separated structurally. `fit()` receives only train and val. `evaluate_run()` runs after selection: val scores → Platt → `calibration.json` → test scored **once** (representatives headline, all test files secondary). | Scoring test inside the epoch loop | Test cannot influence selection or calibration. `ScoredSet`/`build_calibration` already refuse non-val fit data. |
| D12 | `RunContext.create("char_cnn", …)` runs at start. After calibration, the run dir's `config.json` is rewritten (`dataclasses.replace` + `provenance.atomic_write_bytes`) with `calibration_path/sha256` and `threshold_source`. The secondary view uses `RunContext(path=run/"test_all", …)` (public dataclass constructor). | Extending `RunContext` | `models/evaluation` APIs are consumed only. The run owns its directory, so the update is a provenance completion, not a rewrite of history. |
| D13 | Per-group: `compute_metrics(groups=…)` gets only mixed-class keys (`lang`, `course`, `length_bucket`). Per `model` and `profile`, the code computes AUC/AP of (AI files of that group ∪ all humans) and recall at each operating point, stored as `metrics["per_generator"]` with `low_support` when n_pos < 30. | Passing `model`/`profile` to `per_group` | Humans have `model=None`, so every generator group is positives-only and its AUC is undefined. Comparing each group against all humans is the meaningful breakdown. |
| D14 | Checkpoints hold primitives only: `model_state_dict` + `config` dict. No optimizer and no numpy, so they load with `weights_only=True`. The facade treats absent `arch_version` as legacy, `arch_version == preproc_version == 2` as v2, and anything else as `ValueError`. | Duck-typing on state-dict keys (current `inference.py:54`) | Explicit versions fail closed on an unknown future format. |
| D15 | Abstention (v2): `effective_length_v2(normalized) < MIN_NON_WS_CHARS` (60, imported from the legacy module). Legacy numeric keys keep their current placeholder values. | Returning `None` in the legacy keys | `real_engine.py:76-77` does `float(res["prob_sintetico"])`, so `None` would turn the backend into stub fallbacks. The new keys `abstained`/`score=None` let SDD-4 handle abstention properly. |
| D16 | Metrics score every file with the model. Abstention is a deployment policy and is reported as `n_abstained` per class and split. | Dropping abstained files from metrics | The goal is to measure the model. Hygiene already excludes `too_short` (< 50 effective bytes). |

## Preprocessing v2 (`v2/preprocess.py`, `PREPROC_VERSION = 2`)

Header patterns were validated against real file heads. `B2017/Z2/Z1/student{1013,2080}.cpp` open with a block comment `/*B 2017/2018, Zadaća 2, Zadatak 1 … NAPOMENA … autotestovima …`, which `strip_comments` removes (leaving blank lines that D4 drops). In A2016, the course header appears as code: `printf("Zadaća 4, Zadatak 4");` (`A2016/Z4/Z4/student8854.c:199`, `student8195.c:12`). The A2016 Z1 heads and both AI heads (`ref_descuidado_or-deepseek-chat…0001.c`, `ref_kompaktan_or-llama4…0002.c`) start with `#include` and contain no markers. Both classes print Bosnian prompts ("Unesite bodove za Tarika"), so prompt text is not a leak.

```python
_MARKER = r"(?:zada(?:ca|tak|a{1,2})|tutorijal)"   # after folding: Zadaća->Zadaca; zadaa(a) = U+FFFD/mojibake residue
_HEADER_PRINT_RE = re.compile(rf"^[ \t]*(?:std::)?(?:printf|puts|cout)\b[^\n]*\b{_MARKER}\b[^\n]*(?:\n|$)", re.I | re.M)
_MARKER_TOKEN_RE = re.compile(rf"\b{_MARKER}\b(?:[ \t]*(?:br\.?[ \t]*)?\d+)?", re.I)
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")    # \t and \n survive step 2
LEAK_PATTERNS = {"non_alphabet": r"[^\n\x20-\x7e]", "course_marker": rf"(?i)\b{_MARKER}\b"}
```

1. **Newlines**: `\r\n` → `\n`, then `\r` → `\n`.
2. **Controls**: delete `_CONTROL_RE` matches and U+200B-U+200D, U+2060, U+FEFF (BOM) and U+FFFD.
3. **Fold**: `str.translate` maps curly quotes (U+2018-U+201B → `'`, U+201C-U+201F → `"`), dashes (U+2010-U+2015, U+2212 → `-`), Unicode spaces (U+00A0, U+2000-U+200A, U+202F, U+205F, U+3000 → space) and `đ/Đ` → `d/D` (NFKD does not decompose them). Then NFKD runs, combining marks are dropped and every char outside `ALPHABET ∪ {\t}` is dropped. This is the only place non-ASCII disappears.
4. **Comments**: `models.evaluation.normalize.strip_comments` (string-aware, keeps line count).
5. **Course markers**: `_HEADER_PRINT_RE` deletes whole print lines that carry a marker. Then `_MARKER_TOKEN_RE` deletes the marker tokens left over (a marker plus an optional number).
6. **Whitespace** (D4): `\t` → space. Outside single-line literals (the legacy `_LITERAL` regex, copied, not imported), ` {2,}` → one space. Each line is stripped, empty lines are dropped, and lines are joined with `\n` with no trailing newline.

`encode(text) -> np.ndarray[uint8]` uses a 256-entry LUT that defaults to UNK. An empty result becomes `[UNK]` so the model always gets length ≥ 1. It is counted as `n_empty_after_normalize`. `effective_length_v2(t) = len(t) - t.count(" ") - t.count("\n")`. `leak_hits(t) -> set[str]` applies `LEAK_PATTERNS`. **Leak guard** (training CLI): over the normalized human representatives of all splits, if the share matching any pattern exceeds 0.001, it writes `leak_guard.json` (rates per pattern and per class, first 20 offending ids) and exits with code 2 before training. `non_alphabet` holds by construction, so the guard's real job is `course_marker` plus a regression check.

## Model v2 (`v2/model.py`, `ARCH_VERSION = 2`)

```text
x (B,L) uint8->long; mask = x != PAD
Embedding(98,128,padding_idx=0) * mask -> (B,128,L)
per k in (3,5,7,9): Conv1d(128,64,k,pad=k//2) -> LayerNorm(64) per position -> ReLU -> *mask
    -> masked max (fill -inf) ‖ masked mean (sum/len)            # 4 x 128 = 512
Dropout(0.4) -> fc1 Linear(512,1024) -> ReLU = embedding (1024-d, fusion-compatible) -> fc2 Linear(1024,2)
```

`forward(x, return_embedding=False)` keeps the legacy signature, and the mask is derived from `x != 0` (PAD never occurs inside text). There is one dropout, no BatchNorm and no batch-size branch. `CharCNNV2Config` (frozen, `to_dict`/`from_dict`) holds vocab, dims, kernels, filters, fc_units, dropout, `window=4096`, `stride=2048`, `max_windows=8` and `min_non_ws_chars=60`. `v2/scoring.py` provides `window_starts(n, cfg)`, `score_arrays(model, arrays, device, batch_size) -> (p_synth, embeddings|None, n_windows)` and `predict_one(text)`. The scored value is `softmax(mean window logits)[1]`, and the embedding is the mean of the window embeddings.

## Data Pipeline (`v2/data.py`)

`load_encoded(manifest, samples, root=ROOT, on_text=None) -> EncodedSet(samples, arrays, y)` reads `root / sample.id` as bytes and decodes UTF-8 with `errors="replace"` (same as inference). It normalizes and encodes each file, and calls `on_text(sample, raw, normalized)` so the leak guard and shortcut accumulators run in the **same pass**. A missing file raises `FileNotFoundError` with a count. Sets loaded: train/val/test representatives and all test files (non-representative train files are never read). Memory: about 44k manifest entries at an assumed 2-5 KB normalized each is about 90-220 MB of uint8. Raw text is not kept. Preprocessing is single-process (estimated 1-3 min). `epoch_batches(train, epoch, seed, batch_size)` implements D9. `collate` right-pads with 0 to the batch maximum and returns `LongTensor (B, Lmax)` and labels. If humans < AI, all humans are used and the ratio is recorded.

## Training (`v2/train.py`, `python -m models.char_cnn.v2.train`)

- **Flags**: `--manifest` (default `split_v1.json.gz`), `--expected-sha256`, `--root`, `--runs-root runs`, `--seed 42`, `--device` (default `cuda` if available), `--epochs 50`, `--batch-size 128`, `--lr 1e-3`, `--weight-decay 1e-4`, `--early-stop 7`, `--lr-patience 3`, `--lr-factor 0.5`, plus `--limit-per-class N` (debug only, recorded). These hyperparameters are the current `train.py` CLI defaults (`train.py:268-271`) plus `CharCNNConfig`'s optimizer and scheduler values.
- **Order**:
  1. `seed_everything(seed, deterministic_torch=True)`.
  2. Load the manifest.
  3. `RunContext.create("char_cnn", seed, split="test", mode="representatives", manifest_sha256, config=full_cfg, root=runs_root)`.
  4. Load and encode the data, with the guard and shortcuts.
  5. `torch.manual_seed(seed)`, then build the model. There is no dummy forward pass.
  6. Run the epochs.
  7. Save `best.pth` whenever the selection tuple improves.
  8. `evaluate_run`.
- **Epoch**: `model.train()` over `epoch_batches` with CE loss and Adam. Then `model.eval()` and `score_arrays(val)`, followed by `metrics.roc_auc` and `metrics.average_precision`, `scheduler.step(roc)`, the D10 update and the early-stop counter. `history.csv` gets one row per epoch: epoch, train_loss, val_roc_auc, val_pr_auc, lr, n_epoch_samples, seconds.
- **Checkpoint `best.pth`**: `{"format": "graphito.charcnn_checkpoint/v2", "model_state_dict", "config": {arch_version: 2, preproc_version: 2, alphabet, pad_idx, unk_idx, vocab_size, embedding_dim, conv_kernel_sizes, conv_filters, fc_units, num_classes, dropout, norm: "layernorm_channels", window, stride, max_windows, min_non_ws_chars, seed, manifest_path, manifest_sha256, git_sha, dirty, run_id, epoch, val_roc_auc, val_pr_auc, hyperparams{…}, device, torch_version}}`.
- **`evaluate_run` (`v2/evaluate.py`)**:
  1. Load `best.pth`.
  2. Score val. Build `ScoredSet.from_samples(val, p, y, manifest_sha256)` and call `build_calibration(..., channel="char_cnn", score_name="p_synthetic_raw", method="platt", manifest=m)`. Save with `save_calibration` → `calibration.json`, reload it with `load_calibration`, and get the points from `operating_points_from_calibration`.
  3. Score test **once** and apply the calibrator. Call `compute_metrics(y, s_cal, channel="char_cnn", split="test", mode=…, seed, operating_points, groups={lang, course, length_bucket}, bootstrap_groups=[s.dup_group or s.id], bootstrap_unit="dup_group")`.
  4. Add `per_generator` (D13), `n_abstained` and `data_summary`, then `RunContext.write`. The headline is representatives in the run root, and the secondary view (all files) goes to `test_all/`.
  5. Write `scores_val.csv` and `scores_test.csv` (id, y, raw, calibrated) and `shortcuts.json`. Append a "Shortcut audit" section to `report.md`.
- **Length buckets** (normalized chars): `<512`, `512-1023`, `1024-2047`, `2048-4095`, `>=4096` (multi-window).

## Inference Contract (`models/char_cnn/inference.py`)

The constructor `(checkpoint_path=None, config=None, device=None, model_path=None)` is unchanged, and so are `predict(file_path)`, `predict_text(text, pad=False)` (`pad` is ignored on v2, which is padding-invariant) and `main()`. Device: the given one, otherwise CUDA if available, otherwise CPU. The legacy branch is the current constructor and `predict_text` bodies moved verbatim into private methods, plus the new keys. A v2 `config` argument is ignored with a warning, because the checkpoint config wins.

| Key | Legacy ckpt | v2 normal | v2 abstained |
|-----|-------------|-----------|--------------|
| prediction / class_id / confidence | as today | argmax of averaged logits | `"humano"` / 0 / 0.95 |
| prob_humano / prob_sintetico / ai_probability | as today | softmax, rounded to 6 | 0.95 / 0.05 / 0.05 (placeholder) |
| embedding (1024 floats) | as today | mean over windows | model on the short input; zeros if the normalized text is empty |
| insufficient_length | as today | False | True |
| score | prob_sintetico, or None if insufficient | raw p_synth (uncalibrated) | None |
| abstained / n_windows | = insufficient_length / 1 | False / 1..8 | True / 0 or 1 |
| preproc_version / arch_version | 1 / 1 | 2 / 2 | 2 / 2 |

Calibrated probabilities live in the run's `calibration.json`. Applying them at inference time is SDD-4.

## Legacy Baseline, Shortcuts, Promote

- **`v2/baseline.py`**: `--checkpoint models/char_cnn/best_model.pth`.
  - It records `file_sha256` before and after the run and fails if they differ. It loads through the facade (legacy branch) and runs `predict_text(raw)` on split_v1 test (representatives headline, all files in `test_all/`).
  - Output goes to `RunContext.create("char_cnn_legacy", mode="legacy_contaminated", config={"contaminated": true, …})` → `runs/char_cnn_legacy/<ts>/`.
  - Metrics are threshold-free plus one `argmax_0.5` point with `source: "manual"`. Warning: `contaminated: legacy checkpoint was trained on a split that overlaps split_v1 test`. It is never calibrated.
- **`v2/shortcuts.py`**: accumulators fed by `on_text` record, per class and set (train representatives, test representatives), the share of files matching each pattern in the **raw** and **normalized** text.
  - Patterns: `non_ascii [^\x00-\x7f]`, `course_marker` (above), `autotest (?i)autotest\w*`, `control [\x00-\x08\x0b\x0c\x0e-\x1f\x7f]`, `cr \r`, `tab \t`, `std_prefix \bstd::`, `using_namespace \busing\s+namespace\b`, `bits_include #\s*include\s*<bits/`, and `non_code_first_line` (the first non-empty line does not start with `#` and contains none of `;{}()`).
  - It also records the length-bucket histograms. Output is `shortcuts.json` (`schema: graphito.charcnn_shortcuts/v1`), and it is report-only.
- **`v2/promote.py`**: `python -m models.char_cnn.v2.promote <run>/best.pth [--target models/char_cnn/best_model.pth] [--force] [--dry-run]`.
  - It requires a v2 checkpoint plus `metrics.json` and `calibration.json` in its run.
  - It runs `git status --porcelain -- <target>`. Non-empty output or git failure means it refuses unless `--force` is given.
  - It copies with `atomic_write_bytes` and writes `best_model.provenance.json` next to the target: run_id, source/target/previous sha256, git_sha, forced, headline AUCs and calibration path.
  - The git runner is injectable for tests. It is **not run in SDD-2**: today `best_model.pth` is modified, so it would refuse anyway.

## Data Flow

    split_v1.json.gz --load_manifest--> samples (reps / all test)
       |                                   |
       |                 data/raw/src + data/output (root / id)
       |                                   v
       |      v2.preprocess.normalize -> encode(uint8) --on_text--> leak guard / shortcuts
       v                                   v
    RunContext(runs/char_cnn/<ts>) <- fit(train,val): epoch 1:1 crops -> CharCNNV2 -> val AUC -> best.pth
                                           v
                     evaluate_run: val -> Platt -> calibration.json -> test once -> metrics/report (+ test_all/)
    best_model.pth (frozen) -> inference facade (legacy) -> backend / fusion / scripts / baseline -> runs/char_cnn_legacy/<ts>

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `models/char_cnn/v2/{__init__,config,preprocess,model,scoring,data,train,evaluate,shortcuts,baseline,promote}.py` | Create | v2 pipeline (D1) |
| `models/char_cnn/inference.py` | Modify | Version dispatch, new keys, legacy bodies moved verbatim |
| `models/char_cnn/train.py` | Modify | Delete `save_checkpoint`/`setup_model`/`run_training` (they wrote `best_model.pth`). `main` delegates to `v2.train.main`. `evaluate`/`compute_metrics`/`train_epoch` are kept. |
| `models/char_cnn/prepare_dataset.py` | Modify | Deprecation docstring plus a `DeprecationWarning` in `main` |
| `models/char_cnn/README.md` | Rewrite | Current arch v1/v2, preprocess v2, CLIs, run layout, deprecations, limitations |
| `data/train_charcnn.py` | Delete | Invalid PoC, with no importers |
| `models/char_cnn/{preprocess,model,dataset,config}.py`, `dataset_manifest.json`, `best_model.pth` | Unchanged | Frozen legacy. The JSON is deprecated in the README only (tests read its keys). |
| `backend/.../real_engine.py`, `scripts/benchmark_suite.py`, `scripts/benchmark_student_archetypes.py`, `scripts/generate_tt_figures.py`, `models/fusion.py` | Unchanged | They use only the constructor, `predict*`, `prob_sintetico`/`ai_probability`/`embedding` and `train.compute_metrics`. `generate_tt_figures.py` is SDD-4. |
| `tests/test_char_cnn_v2_{preprocess,model,data,inference,train,promote}.py`, `tests/fixtures/charcnn_legacy_golden.json` | Create | See Testing |

## Testing Strategy

| Layer | What | Approach |
|-------|------|----------|
| Unit | Preprocess | Each step is tested separately. Symmetry: a human-style variant (CRLF, BOM, tabs, header block comment, `printf("Zadaća 4, Zadatak 4");`, curly quotes, `č`) normalizes to the same output as its clean AI-style twin. LUT/index layout. Leak-pattern hits. Empty → `[UNK]`. |
| Unit | Model | Padding invariance: right-pad 0..300, atol 1e-5, eval mode. Batch invariance (bs=1 vs batched, mixed lengths). Masked pooling ignores pad values. `window_starts` (≤4096 → 1, even coverage, cap 8, last window reaches the end). |
| Unit | Data | `epoch_batches` is deterministic per (seed, epoch), differs across epochs, keeps 1:1 and every AI file appears once, crops ≤ window. Collate pads with 0. |
| Contract | Inference | Fake legacy checkpoint (pattern of `test_char_cnn_canonical.py:54`) gives all legacy keys plus `arch_version=1`. Fake v2 checkpoint (tiny dims) gives the v2 keys, abstention placeholders and `score=None`. Unknown version → `ValueError`. With `requires_charcnn_weights`: a CPU golden snapshot of `predict_text` on 3 snippets, **captured with the pre-change code** in that work unit (tol 1e-6). |
| Integration | Train/eval | Fixture tree from `tests/eval_factory.make_tree` plus `build_split`/`write_manifest` in `tmp_path`, with tiny config (window 256, stride 128, dims 8/4/16, 2 epochs, CPU). Two runs give identical `history.csv`, selected epoch, state_dict tensors and metrics. The run dir contains every artifact. A planted header file makes the guard exit with code 2. |
| Unit | Promote | Fake git runner: a dirty target refuses, `--force` writes the copy plus provenance, `--dry-run` writes nothing. A tmp target only, never the real file. |
| Regression | Legacy | Existing `tests/test_char_cnn_*.py` and `test_calibration_experiment.py` pass unmodified. |

## Migration / Rollout

No data migration. Suggested work-unit commits (advisory, about 400 authored lines each):
1. `feat(charcnn): add preprocess v2` + tests.
2. `feat(charcnn): add arch v2 model and windowed scoring` + tests.
3. `test(charcnn): capture legacy golden snapshot`, then `feat(charcnn): version-dispatching inference facade` + contract tests.
4. `feat(charcnn): manifest-driven encoded data and epoch sampler` + tests.
5. `feat(charcnn): seeded v2 trainer with AUC selection` + determinism test.
6. `feat(charcnn): val-only calibration and test report` + shortcut report + guard wiring.
7. `feat(charcnn): legacy baseline and promote CLIs` + tests.
8. `chore(charcnn): deprecations, train.py delegation, README`.
9. Real run (CUDA) plus the legacy baseline. Selected `metrics.json`/`report.md`/`calibration.json`/`shortcuts.json` are committed with `git add -f` (eval-foundation D9).

## Open Questions

- [ ] D4 defines "canonical whitespace" as line-preserving. If the parallel spec means the legacy `canonical` mode (no newlines), reconcile in `sdd-tasks`.
- [ ] `autotest` stays report-only (it is only seen inside header comments, which are stripped). Promote it to a stripped marker if `shortcuts.json` shows it in normalized human code.
