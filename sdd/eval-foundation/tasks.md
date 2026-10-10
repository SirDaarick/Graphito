# Tasks: Evaluation Foundation (eval-foundation)

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated authored changed lines | ~4,600 (code ~2,300 + tests ~2,300); generated `split_v1.json` and regenerated `manifest*.json` not counted |
| 400-line budget risk | High (per work unit: WU4 ~900, WU7 ~500, WU11 ~500; others 250-450) |
| Chained PRs recommended | Yes |
| Suggested split | PR1 = WU1-3 -> PR2 = WU4-5 -> PR3 = WU7-9 -> PR4 = WU10-11 -> PR5 = WU12 (data) |
| Delivery strategy | ask-on-risk (default; not supplied) |
| Chain strategy | pending |

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: pending
400-line budget risk: High

The ~400-line figure is advisory per work unit. Each WU = one Conventional Commit (English) with tests and docs. Every task below is RED (test) first, then GREEN (implementation). Runner: `pytest tests/ backend/tests/ -v` from the repo root; focused runs use `pytest tests/test_eval_<x>.py -v`. All fixtures are synthetic (`tmp_path`), with no real data, models or network.

### Work Units and Dependencies

| WU | Commit | Depends on | Parallel with |
|----|--------|-----------|---------------|
| 1 | `chore(eval): add repo config, seeding and C/C++ normalization` | none | WU7 |
| 2 | `feat(eval): add numpy MinHash/LSH dedup` | 1 | WU3, WU7 |
| 3 | `feat(eval): add ground-truth parser and cluster resolver` | 1 | WU2, WU7 |
| 4 | `feat(eval): add split builder and build_split CLI` (may land as 2 commits: 4.1-4.4, 4.5-4.7) | 1, 2, 3 | WU7 |
| 5 | `feat(eval): add split manifest loader` | 4 | WU7 |
| 6 | merged into WU12 (design commit 6, `data(splits)`) | 5 | |
| 7 | `feat(eval): add vectorized metrics and bootstrap CIs` | none (WU1 for package dir) | WU2-5 |
| 8 | `feat(eval): add calibration and val-only threshold selection` | 5, 7 | WU9 (after 7) |
| 9 | `feat(eval): add run reporting` | 7 (8 for calibration hash) | WU10 |
| 10 | `refactor(golden-set): rebuild from split manifest` | 1, 5 | WU9 |
| 11 | `refactor(benchmark): use evaluation package, modes and run dirs` | 7, 8, 9, 10 | none |
| 12 | `data(splits): add split_v1.json` + real-data validation | all | none |

Naming reconciliation (spec wins over design where they differ; the builder follows the spec): flags are `broken` plus sub-flags `empty|too_short|no_student_id|copy_suffix`, and `unparsed_name` (design said `name_copy`, `ai_name_unparsed`). Entries also carry `excluded` (true for broken and `cross_split_dup`). Stats expose the spec keys at top level (`stats.cross_block_dup_groups`, `stats.dup_threshold_sensitivity`, `stats.unresolved_cluster_members`). Run files are `config.json` (provenance inside, no separate `provenance.json`).

Decisions needed from the user (tasks flagged DECISION):
- D-A (1.1): `.gitignore` for `runs/`. Design D9 (ignore all, `git add -f`) conflicts with the ER1.7 scenario, where `metrics.json` must NOT match `git check-ignore`. RESOLVED (orchestrator): follow design D9 — ignore all of `runs/`, commit selected files with `git add -f`; spec ER1.7 updated accordingly.
- D-B (12.3): manifest over 25 MB -> commit `.json.gz` (mtime=0)? Decided only if the real size exceeds the limit.
- D-C: chain strategy (stacked-to-main vs feature-branch-chain), before apply.

## WU1: Repo config, seeding, normalization

- [x] 1.1 (D-A resolved: ignore all `runs/`). Edit `.gitignore` (`runs/` rules), edit existing `.gitattributes` (`data/splits/*.json -diff eol=lf linguist-generated`), edit `requirements-dev.txt` (`matplotlib`). RED first: `tests/test_eval_repo_config.py` (`git check-ignore` on `runs/char_cnn/x/roc.png`, `runs/char_cnn/x/metrics.json`, `data/splits/split_v1.json` attrs; skip if git is missing). [ER1.7, NF1, D7]
- [x] 1.2 RED `tests/test_eval_seed.py`: `seed_everything` without torch seeds random/numpy and returns the seed; `stable_rng` is deterministic; importing the package needs no torch. GREEN: create `models/evaluation/__init__.py`, `models/evaluation/seed.py`. [EM4.1]
- [x] 1.3 RED `tests/test_eval_normalize.py`: string-aware `strip_comments`; `effective_length` (< 50 case); `norm_hash` equal across comment/whitespace changes and different on logic change; `shingle_tokens` maps identifiers to `ID` and keeps keywords. GREEN: `models/evaluation/normalize.py` (port of `data/golden_set/perturb_corpus.py:35-66`, regex lexer). [DS2.1, DS2.3, DS2.4]
- Check: `pytest tests/test_eval_seed.py tests/test_eval_normalize.py tests/test_eval_repo_config.py -v`.
- Evidence: route delegated (writer had no shell; parent ran checks). 54/54 new eval tests pass; full suite 151 passed, 1 skipped, 1 pre-existing failure in untouched tests/test_calibration_experiment.py. RED was written first but not observed (executor lacked a shell).

## WU2: Dedup (independent of WU3)

- [x] 2.1 RED `tests/test_eval_dedup.py`: exact `jaccard`; MinHash estimate within +-0.1 of exact on planted pairs; LSH recall on planted near-dups; p = 2^31-1 with no uint64 overflow; `UnionFind`; determinism. [DS2.4, DS2.5]
- [x] 2.2 GREEN `models/evaluation/dedup.py` (`token_ids`, `shingle_hashes(k=5)`, `minhash`, `lsh_candidates` 16x8, `jaccard`, `UnionFind`). Check: the 2.1 tests pass.

## WU3: Ground truth (independent of WU2)

- [x] 3.1 RED `tests/test_eval_ground_truth.py` on a synthetic GT file: per-assignment clusters; a student in two clusters leads to a merge and one deterministic `A2016/Z1/Z1#03`-style id (rule returned for `config`); missing file goes to `unresolved`; course absent from GT is `unlabeled`; `pairs()` labels same-cluster = 1. [DS3.4, DS3.5, DS3.6]
- [x] 3.2 GREEN `models/evaluation/ground_truth.py` (`parse_ground_truth`, `resolve_clusters`, `pairs`). Check: the 3.1 tests pass.

## WU4: Split builder and CLI (depends on WU1-3)

- Review follow-up from PR1 (advisory, R3-gt-course-granularity-negative) — RESOLVED by commit 52a6305 (`fix(eval): treat unheaded GT assignments as unlabeled`): `resolve_clusters` labels as `negative` every file of a labelled course whose assignment has no GT header. Before 4.6, check `data/raw/readme.txt` for whether unheaded assignments were inspected; if not guaranteed, treat unheaded assignments as `unlabeled` and add a test (`ground_truth.py:147-165`).

- [x] 4.1 Create `tests/eval_factory.py`: synthetic tree in `tmp_path` (2 letters x 6 blocks, 2 years, C and C++, AI names incl. `weird.c`, GT file with overlapping lines and a missing member, `x (1).c`, 0-byte, 30-byte and comment-only files, a planted cross-block exact dup, B2017 without GT, a repeated student id).
- [x] 4.2 RED `tests/test_eval_splits.py::discovery`: DS1.2 keys all present with `null` for N/A, AI `model/profile` parsed, `unparsed_name` kept, `config`/`stats` present, roots overridable, source files untouched. [DS1.1-1.4, DS2.2]
- [x] 4.3 RED `::hygiene_dedup`: four broken files flagged with sub-flags and absent from dup groups; comment/whitespace/rename pair shares a `dup_group`; cross-block identical pair not merged and `cross_block_dup_groups` >= 1; sensitivity counts non-decreasing, 0.85 count equals distinct non-broken groups. [DS2.1-2.5]
- [x] 4.4 GREEN `models/evaluation/splits.py` part 1: `scan`, `parse_path`, `hygiene_flags`, norm/shingle, exact and near groups feeding three union-finds, `dup_group` id `dg-<sha256(min id)[:10]>`. Check: 4.2-4.3 pass.
- Evidence 4.1-4.4: RED observed (`ModuleNotFoundError: models.evaluation.splits`); GREEN 22/22 in tests/test_eval_splits.py. GT follow-up landed first as `fix(eval)`: RED `'negative' == 'unlabeled'`, GREEN 14/14 (readme gives no guarantee that unheaded assignments were inspected).
- [x] 4.5 RED `::assignment`: byte-identical rebuild (seed 7 twice; seed 8 valid); one split per block, per dup group and per cluster; a student in two clusters of one assignment gets one merged cluster, while clusters of the same student in different blocks are not merged and their cross-split links are reported in `stats.gt.cross_split_student_clusters` (amended DS3.4); unresolved member in stats and not in entries; B2017 `cluster_id` null; 3-block course raises (2-block minimum); unfillable stratum raises naming it; test/val >= 2 blocks and fractions recorded; cross-block dup pinned to the most held-out split with `excluded` + `cross_split_dup` counted; student overlap reported without error; both langs and sources in each split. [DS3.1-3.9]
- [x] 4.6 GREEN `splits.py` part 2: block assignment with attempt loop, GT cluster units, pinning (D4), `validate`, stats (overlap, GT negative near-dups, size distribution), deterministic `write_manifest` (LF, sorted keys, no timestamps or absolute paths). Check: 4.5 passes.
- [x] 4.7 RED+GREEN `scripts/build_split.py` (`--seed`, `--raw-root`, `--ai-root`, `--out`, per-stage timings; `sys.path` insert as in `scripts/benchmark_suite.py:26-29`) with a CLI test in `tests/test_eval_splits.py::cli`. Check: runs on the factory tree and exits 0.
- Evidence 4.5-4.7: RED observed (`ImportError` for `SPLITS/validate/write_manifest`; `TypeError` for `workers`; CLI `can't open file`); GREEN 42/42 in tests/test_eval_splits.py; CLI on the factory tree 0.7 s (132 files); 9.6k synthetic files 16 s with the auto process pool (129 s serial), output byte-identical for 1 vs N workers.
- Interpretations (flag for review): (a) exact dups (same `norm_hash`) group globally per DS2.3, so the DS2.4 scenario `identical files in different blocks ... not merged` is read as *blocks* not merged (D4 pinning applies); cross-block near-dups are counted (`stats.cross_block_dup_groups`, `stats.dedup.cross_block_near_pairs`) and never merged. (b) DS3.4 cross-block student links are reported (`stats.gt.cross_split_student_clusters`), not merged into one split: on the real static GT, students clustered in several blocks would chain every block of each letter into one unit (A/Z1-Z5 and B/Z1-Z6), making DS3.2 impossible; this matches design step 6 and DS3.9 (overlap reported, not prevented).

## WU5: Loader (depends on WU4)

- [x] 5.1 RED `tests/test_eval_manifest.py`: `load_split("val")` returns only val and no `broken`; `include_broken=True` returns them; filters lang/source/course; schema validation rejects bad files; sha256 computed; `expected_sha256` mismatch and edited-file hash errors raise; Channel A negatives never include B2017 `unlabeled`; `plagiarism_pairs`, `clusters`, `check_invariants`. [DS3.6, DS4.1, DS4.2]
- [x] 5.2 GREEN `models/evaluation/manifest.py` (stdlib + numpy only for `PairSet`). API: `load_manifest(path, expected_sha256)` -> `SplitManifest`; `load_split(split, *, path=DEFAULT, expected_sha256=None, lang, source, course, include_broken=False)` -> `list[Sample]` (spec scenario form). Extend `models/evaluation/__init__.py` exports. Check: 5.1 passes.
- Evidence 5.1-5.2: RED observed (`ModuleNotFoundError: models.evaluation.manifest`); GREEN 21/21 in tests/test_eval_manifest.py. Schema constants and `check_invariants` moved into `manifest.py` (stdlib + numpy); `splits.validate` delegates to them. Loader drops all `excluded` entries by default (broken back with `include_broken`, `cross_split_dup` only via `SplitManifest.samples(include_excluded=True)`); `channel_a_negatives` returns only `gt_status == negative`. Full suite: 215 passed, 1 skipped, 1 known failure (tests/test_calibration_experiment.py).
- Evidence PR2 review fixes (`fix(eval): harden split manifest loader and writer`): RED observed (pinned dup group lost under `representatives_only`; `PairSet` lacks `ambiguous`; non-object/unhashable entries raised `AttributeError`/`TypeError`; torn write clobbered the previous manifest; `MIN_EFFECTIVE_BYTES` ImportError) -> GREEN 88/88 in test_eval_ground_truth/splits/manifest. Representatives are now chosen per result set; ambiguous pairs carry label -1 plus `PairSet.ambiguous`; `write_manifest` writes a sibling temp file then `os.replace`.

## WU7: Metrics (independent; may start any time after WU1)

- [x] 7.1 RED `tests/test_eval_metrics.py` known values: ROC-AUC 1.0 / 0.0 / 0.5 (all ties) / 0.875; sklearn oracle on tie-heavy random data (`roc_auc`, `average_precision`); `single_class` returns `None` plus reason, no exception; n=20000 random AUC within 0.02 of 0.5. [EM1.2, EM1.3]
- [x] 7.2 RED threshold metrics: precision null without predicted positives, recall null without positives, FPR still defined; `observed` and `balanced` always, `natural` only when configured (labelled); per-group with empty group gives `n=0` and null. [EM1.1, EM1.4-1.6]
- [x] 7.3 RED retrieval and calibration error: AP@R = 1/2 for `[rel,non,rel,non]`, 1.0 for `[rel,rel,non,non]`, R=0 queries excluded and counted; ECE 0 (8/10 at 0.8) and 0.3 (5/10), bin count recorded. [EM1.1]
- [x] 7.4 RED bootstrap: seed-reproducible; point estimate in `[lo, hi]`; global RNG state unchanged; 2 positives in 100 gives `skipped_resamples` and valid or null CI; grouped (atomic unit/block) resampling. [EM2.1-2.3]
- [x] 7.5 GREEN `models/evaluation/metrics.py` (rank-based AUC with midranks, curves, AP, `threshold_metrics`, `map_at_r`, `ece`/`reliability_bins`, `bootstrap_ci`, `per_group`, `prevalence_weights`). Check: 7.1-7.4 pass.
- Evidence 7.1-7.5: RED observed (`ImportError: cannot import name 'metrics' from 'models.evaluation'`) -> GREEN 34/34 in tests/test_eval_metrics.py (sklearn oracle for AUC, weighted AUC, AP and ROC points; brute-force MAP@R oracle).

## WU8: Calibration (depends on WU5, WU7)

- [x] 8.1 RED `tests/test_eval_calibration.py`: `fit` raises `ValueError` on any non-val entry and writes no artifact; Platt/temperature/isotonic preserve ranking (AUC unchanged); temperature recovers a known T; `select_threshold` lowest t with FPR <= 5% (Uniform(0,0.6)/(0.4,1) case), `low_support`, `unachievable`; round trip `transform` within 1e-9; unknown schema version or missing key rejected; deterministic write; frozen apply to test changes no parameter. [EM3.1-3.7]
- [x] 8.2 GREEN `models/evaluation/calibration.py` (`ScoredSet`, `fit`, calibrators, `select_threshold`, `save/load_calibration`; thresholds in calibrated space) and `models/evaluation/provenance.py` (git sha + dirty with `unknown` fallback, file sha256; shared with WU9). Check: 8.1 passes.
- Evidence 8.1-8.2: RED observed (`ImportError` collecting tests/test_eval_calibration.py: no `calibration`/`provenance` modules) -> GREEN 25/25. Isotonic preserves ranking weakly (plateaus may tie; never invert), so the AUC-unchanged check applies to temperature/Platt; default `min_negatives = ceil(10 / target)` (design rule `n_neg * target < 10`), overridable. Temperature/Platt require scores in [0, 1].

## WU9: Reporting (depends on WU7; WU8 for the calibration hash)

- [x] 9.1 RED `tests/test_eval_report.py`: run dir has `config.json`, `metrics.json`, `report.md`, `roc/pr/reliability` CSVs and four PNGs; `config.json` has seed, `manifest_sha256`, `git_sha`, versions, argv; no git gives `"unknown"` and the run succeeds; single class gives no `roc.png`, reason in `report.md`, null AUC with reason; two runs in the same second give distinct dirs; missing matplotlib records `artifacts_missing` (`importorskip` for the PNG tests); `report.md` has split, hash, thresholds, `low_support`, student-overlap caveat. [ER1.1-1.6]
- [x] 9.2 GREEN `models/evaluation/report.py` (`RunContext.create`, writers, lazy Agg plots, `report.md` template). Check: 9.1 passes headless.
- Evidence 9.1-9.2: RED observed (`ImportError: cannot import name 'report' from 'models.evaluation'`) -> GREEN 12/12 in tests/test_eval_report.py (headless Agg canvas, no pyplot). Run dirs follow the spec (`runs/<channel>/<ts>[-N]/`, created atomically with `mkdir`); provenance lives in `config.json`; `RunContext.create` refuses a run without a manifest sha256 (DS4.1); the package exports calibration/report entry points and still imports with torch and matplotlib blocked.
- Evidence PR3 review fixes: RED 24 failed (roc.csv threshold column held FPR values; plot `RuntimeError` aborted `write`; 313 vs 26 `threshold_views` calls per point; `.calibration.json.tmp` left behind; T=0 / non-numeric / non-list / non-increasing params and non-mapping thresholds accepted; no `validate_labels`/`atomic_write_bytes`) -> GREEN 142/142 eval tests; seeded CI95 regression values unchanged; full suite 324 passed, 1 known env failure (`test_graphcodebert_calibration`).

## WU10: Golden set from split (depends on WU1, WU5; independent of WU9)

- [x] 10.1 RED: create `tests/fixtures/golden_set_tiny/provenance.json`; new `tests/test_golden_set_split.py` (build from a fixture split gives only test ids, zero train/val ids, broken absent, byte-identical rebuild, `source_manifest_sha256` equals the split file hash, `corpus_val` only with `--split val`, `build_manifest` without provenance requires `--synthetic`); update `tests/test_perturb_corpus.py` (reads rebuilt golden set, no train/val refs, `--split-manifest/--split`). [GS1-GS5]
- [x] 10.2 GREEN modify `data/golden_set/build_corpus.py` (`--split-manifest`, `--split test|val`, writes `provenance.json`), `data/golden_set/build_manifest.py` (drop `assign_split` and per-file sha256; assert no train), `data/golden_set/perturb_corpus.py` (re-export `strip_comments`, copy provenance, `problems_from_split`). Check: 10.1 passes plus the existing perturb tests.
- [x] 10.3 Docs: rewrite `data/golden_set/README.md` (new provenance, 1825/2621 leakage of the old version, val corpus used only to fit calibration). [GS6]
- Evidence 10.1-10.3: RED observed (7 failed + 14 errors: `build_corpus()` signature `TypeError`, no `default_out`/`problems_from_split`, no provenance/`--synthetic` checks, `perturb.strip_comments` not the package function) -> GREEN 34/34 in test_golden_set_split/perturb_corpus/benchmark_suite; full suite 342 passed, 1 skipped, 1 known env failure. Golden corpora are built on the `eval_factory` tree + `build_split` (no real data); dedup is by provenance `dup_group` (replaces per-file sha256), golden manifests have no wall clock (byte-identical rebuilds).

## WU11: Benchmark suite (depends on WU7-10)

- [x] 11.1 RED update `tests/test_benchmark_suite.py` (stub engine): thresholds 0.61/0.33 from `calibration.json` reach `config.json`; a `val` entry raises naming the id; missing calibration exits non-zero pointing to the calibration step; `uncalibrated` mode emits no operating points; `--calibrate` fits on val only and freezes before test; run dir complete with manifest hash; no numeric threshold literal in `scripts/benchmark_suite.py`. [BS1-BS4]
- [x] 11.2 GREEN modify `scripts/benchmark_suite.py`: samples via `load_split("test")`, metrics through `models.evaluation.metrics`, three modes (`calibrated-fit-in-run`, `calibrated-frozen`, `uncalibrated`), drop `DEFAULT_THRESHOLDS_SEM` and `THRESHOLD_AI=0.20`, provisional fused decision = OR of calibrated channel decisions (production fusion deferred to SDD-4), one `RunContext` per channel/fused. Check: 11.1 passes.
- [x] 11.3 Docs: README.md updates, marking the root `benchmark_*results.json` / `benchmark_charcnn_*.json` as legacy and non-comparable (new results carry the manifest hash); document `git add -f` for selected `metrics.json`/`report.md`. [BS5, ER1.7]
- Evidence 11.1-11.3: RED observed (15 failed: unknown `--mode`/`--calibration-*`/`--runs-root` flags, no `cosine`/`fuse`/`require_split`, float threshold literals) -> GREEN 15/15 in tests/test_benchmark_suite.py (45/45 with golden/perturb tests); full suite 353 passed, 1 skipped, 1 known env failure. Run layout `runs/benchmark/<ts>/{config,summary}.json` + `calibration_<channel>.json` + one `RunContext` per channel under `<channel>/<ts>/` (RunContext always nests `<channel>/<ts>`); Channel A = raw cosine (isotonic default; temperature/Platt need [0, 1]), Channel B = ai_prob (platt); fused = OR at calibrated thresholds, scored by max of calibrated scores; uncalibrated mode skips fused; frozen calibrations must match the split manifest sha256; optional D11 `--thresholds manual` not implemented (no numeric thresholds at all).
- Evidence PR4 review fixes: RED 13 failed (fused OR point evaluated as max-score >= 1: observed (tp,fp,fn,tn) (0,0,3,3) vs OR decision (2,1,1,2); no fused `dropped_without_reference`; failed scoring/fit left `runs/benchmark/<ts>` behind; `ValueError`/`ManifestHashError` escaped `main()` with a traceback; `golden_manifest` held the split manifest path; `float(0)` workaround; synthetic corpora kept byte-identical files; `../outside.c` copied from outside the repo root; perturb subset kept source totals and wrote provenance non-atomically) -> GREEN 74/74 in golden/perturb/benchmark/report tests; full suite 366 passed, 1 skipped, 1 known env failure (`test_graphcodebert_calibration`). Fused operating points are now computed on the 0/1 OR decision (threshold-free metrics stay on max of calibrated scores), runs are staged under `runs/.staging/` and renamed into `runs/benchmark/` on success, `main()` exits 2 on input errors.
- Evidence PR4 regression fixes: RED 11 failed (`require_split`/`_source_sha` raised bare `ValueError`; internal `ValueError` in `score_manifest`/`build_calibration`/`compute_metrics` became `ERROR:` + exit 2; a concurrent `<ts>` publish raised `FileExistsError` and deleted the completed run; a failed publish deleted the staged run; synthetic sha256 dedup dropped an exact copy of its original and identical files across problems) -> GREEN 69/69 in benchmark/golden/perturb tests. `main()` now catches only `BenchmarkError`/`ManifestError`, `_publish` claims `<ts>[-N]` by rename (100 attempts) and keeps the staged run on failure (`PublishError`), synthetic dedup is scoped to problem+class, and the BS2 guard walks the AST for any float literal other than 0.0/1.0.
- Deferred review follow-ups (not fixed here):
  - Clean up stale `runs/.staging/` entries (crashed or unpublished runs) on startup.
  - Duplicated fused config keys: `threshold_free_score` vs `score`, `operating_points` vs `decision`.
  - Fused warnings are merged by message substring; `compute_metrics` needs a structured warning key.
  - The fused ranking score (max of calibrated scores) is computed twice (`fused_metrics` and `_evaluate_run`).
  - `build_corpus` validates ids while copying; validate every id before the first copy.
  - The KeyError path for unachievable fused operating points is untested.
  - Run path rebasing is a substring replace that skips `calibration_*` files; document it or make it explicit.
  - `_publish` rebasing writes and the restore loop sit outside the try block: a write failure (disk full, locked file) escapes as raw OSError, not `PublishError` (review of d82e90c).
  - `PublishError` reaches the user as a traceback; catch it in `main()` and print the kept staged path.
  - User-selectable options that raise `ValueError` (e.g. Platt/temperature on Channel A scores outside [0, 1]) should be converted to `BenchmarkError` at the source.
  - Rename the BS2 helper `_threshold_literals` to reflect that it flags every float literal except 0.0/1.0.

## WU12: Real data (depends on all; 12.1-12.3 may run right after WU5 to de-risk, in the design's commit slot 6)

- [ ] 12.1 Run `python scripts/build_split.py` on the real corpus (seed fixed, record timings; target < 5 min).
- [ ] 12.2 Verify: invariants pass (`check_invariants`), rebuild is byte-identical, block counts per letter, C/C++ and human/AI in every split, student overlap, cross-block dup groups, near-dup sensitivity (0.80/0.85/0.90), GT negative near-dups, unresolved members (e.g. B2016/Z6). Paste stats in the PR description.
- [ ] 12.3 DECISION D-B. Check `data/splits/split_v1.json` size vs 25 MB (est. ~15 MB); if over, choose the `.json.gz` fallback; then commit `data(splits): add split_v1.json` (generated; not counted).
- [ ] 12.4 Rebuild golden test corpus (`build_corpus --split test`) and val corpus (`--split val` into `corpus_val/`), then regenerate `data/golden_set/manifest*.json`; assert zero train/val ids and `source_manifest_sha256`.
- [ ] 12.5 Run `scripts/benchmark_suite.py` with the STUB engine in `uncalibrated` and `calibrated-fit-in-run` modes; check run dir completeness, CIs, thresholds from val, manifest hash. Plumbing validation only: REAL-model numbers are not meaningful until SDD-2/3.
- [ ] 12.6 Final `pytest tests/ backend/tests/ -v` passes; `tests/test_char_cnn_robustness.py` unchanged (reads out-of-scope `models/char_cnn/dataset_manifest.json`); `git status` shows no changes to `models/char_cnn/dataset_manifest.json` or `scripts/generate_tt_figures.py`. [NF2, NF3]
- Real-run findings (first `build_split.py` run, seed 42, builder 1.0): grouping by letter + Zx gave only 5 blocks for A and 6 for B, so with the 2-block test/val minimum train became the smallest split (train 9,665 human / 334 AI; val 17,072 / 598; test 14,409 / 521), unusable for SDD-2/3 training. The real corpus has 20 distinct Zx/Zy assignments in A and 28 in B (years merged). `stats.gt.negative_near_dup.pairs` held 365,325 human-human GT-negative near-dup pairs (Jaccard >= 0.85; test 83,903, train 70,912, val 210,510), 32 MB of the 52.8 MB manifest.
- Decision 2026-10-10 (user): the split unit is one assignment with years merged (`A2016/Z3/Z1` + `A2017/Z3/Z1` -> block `A/Z3/Z1`; `config.group_key = "letter/Zx/Zy (years merged)"`, builder 1.1). Quotas per letter keep the same formula; near-dup scope stays within block; cross-block near-dup counting and exact-dup pinning are unchanged. Sibling-topic leakage is reported: `stats.zx_groups_split` (blocks per split for each `letter/Zx`) and `stats.dedup.cross_split_near_pairs`. `SplitConfig.group_key="zx_block"` keeps the old unit.
- Evidence `feat(eval): group split by assignment across years`: RED observed (8 failed + 6 errors: blocks still `A/Z1`, no `group_key` argument, no `zx_groups_split`/`cross_split_near_pairs`, 3-topic x 2-assignment factory tree hit the 2-block minimum) -> GREEN 83/83 in test_eval_splits/manifest; 168/168 in splits/manifest/golden/perturb/benchmark/report tests.
