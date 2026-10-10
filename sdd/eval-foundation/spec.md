# Spec: eval-foundation

Keywords follow RFC 2119. All scenarios MUST be testable with pytest on small synthetic fixtures (temporary directories with a handful of fake `.c`/`.cpp` files and a fake ground-truth file); no real data, models or network are required. "Block" means the group key `course letter + Zx + Zy`, i.e. one assignment with its years merged (e.g. `A/Z3/Z1` groups A2016/Z3/Z1 and A2017/Z3/Z1; `A/Z3/Z2` is a separate block). Amended 2026-10-10 after the first real-data run: the earlier `course letter + Zx` unit gave only 5 (A) and 6 (B) blocks, so the 2-block test/val minimum left train the smallest split. "Course A" is C-only, "course B" is C++-only.

## Capability: dataset-split (new)

### DS1. Discovery and manifest schema
- DS1.1 The builder MUST discover samples from disk (`data/raw/src`, `data/output`), not from `.generation_state.json`. Roots MUST be overridable (CLI/function args) so tests can point at a fixture tree.
- DS1.2 Each manifest entry MUST contain: repo-relative `id` (POSIX separators), `course`, `block`, `assignment`, `student`, `lang`, `source` (`human`|`ai`), `model`, `profile`, `sha256`, `norm_hash`, `dup_group`, `cluster_id`, `split` (`train`|`val`|`test`), `flags` (list). Fields that do not apply (e.g. `model` for human files) MUST be `null`, not omitted.
- DS1.3 AI metadata (`model`, `profile`) MUST be parsed from `data/output/<course>/<Zx>/<Zy>/ref_<profile>_<model>_<ts>_<NNNN>.(c|cpp)`; a non-matching AI filename MUST get flag `unparsed_name` and be kept.
- DS1.4 The manifest MUST also contain `config` (seed, test/val fractions actually used, near-dup threshold, shingle size, min effective bytes, builder version) and `stats`.

Scenarios
- Given a fixture tree with one human C file and one AI C++ file, When the builder runs, Then both entries carry every DS1.2 key, the AI entry has non-null `model` and `profile`, and the human entry has `model: null`.
- Given an AI file named `weird.c`, When the builder runs, Then it is in the manifest with flag `unparsed_name`.

### DS2. Hygiene flags (flag, never delete)
- DS2.1 A file MUST be flagged `broken` (reason sub-flag `empty`, `too_short`, `no_student_id` or `copy_suffix`) if it is empty, has fewer than 50 effective bytes (after comment and whitespace stripping), has no parseable student id, or has a `(1)`-style copy suffix. Broken files MUST remain in the manifest and MUST be excluded from metrics and dup-group formation.
- DS2.2 The builder MUST NOT delete, move or modify any source file.
- DS2.3 Files with identical `norm_hash` (comments and whitespace stripped) MUST share one `dup_group`.
- DS2.4 Files within the same block whose identifier-normalized 5-token-shingle MinHash Jaccard estimate is >= 0.85 MUST be merged into the same `dup_group` (transitive closure). Near-dups across different blocks MUST NOT be merged but MUST be counted in `stats.cross_block_dup_groups`.
- DS2.5 `stats.dup_threshold_sensitivity` MUST report the number of dup groups at Jaccard 0.80, 0.85 and 0.90; 0.85 is the operative threshold recorded in `config`.

Scenarios
- Given a 0-byte file, a 30-byte file, a file with only comments, and a file named `x (1).c`, When the builder runs, Then all four are present and flagged `broken` with the matching sub-flag, and none appear in any dup group.
- Given two files differing only in comments, whitespace and a renamed variable, in the same block, When the builder runs, Then they share a `dup_group`.
- Given two identical files in different blocks, When the builder runs, Then they are not merged and `stats.cross_block_dup_groups` is >= 1.
- Given a fixture with known near-duplicate pairs, When the builder runs, Then the group counts at 0.80/0.85/0.90 are non-decreasing in threshold (higher threshold merges less, so more groups) and the 0.85 count equals the number of distinct `dup_group` ids among non-broken entries in that run.

### DS3. Group-level, seeded, deterministic assignment
- DS3.1 Split assignment MUST be performed per course letter at block granularity (one assignment, years merged): every entry of a block receives the same `split`. The group key rule MUST be recorded in `config.group_key`. Sibling assignments of one Zx MAY land in different splits; `stats.zx_groups_split` MUST report, per `letter/Zx`, how many of its blocks each split holds, and `stats.dedup.cross_split_near_pairs` MUST count cross-block near-dup pairs whose blocks land in different splits.
- DS3.2 Within each course letter (blocks counted as assignments, years merged), test MUST receive >= ~20% of blocks and val >= ~15% of blocks, with a minimum of 2 blocks each; the exact fractions used MUST be recorded in `config` and `stats`. If a course has too few blocks to satisfy the minimum, the builder MUST fail with an explicit error rather than silently under-allocate.
- DS3.3 All included (non-excluded) members of a `dup_group` MUST be in one split. A group whose blocks land in different splits MUST be pinned to its most held-out split (test > val > train); members in the other splits MUST be marked `excluded: true` with flag `cross_split_dup` (their `split` keeps the block value), and pinned exclusions MUST be counted in `stats`.
- DS3.4 Ground-truth clusters (from `data/raw/ground-truth-static-anon.txt`) MUST NOT span splits. A student appearing in two clusters of the same assignment MUST receive a single deterministic `cluster_id` (rule recorded in `config`), and those clusters MUST be merged. Clusters of the same student in different blocks MUST NOT be merged (on the real GT, 183/509 clustered students span blocks and merging would chain every block of a course letter into one unit, violating DS3.2); such links MUST be reported in `stats.gt.cross_split_student_clusters` as part of the student-overlap limitation.
- DS3.5 Cluster members absent on disk (e.g. B2016/Z6) MUST be recorded in `stats.unresolved_cluster_members` and MUST NOT be fabricated as entries.
- DS3.6 Entries from a course/year without ground truth (B2017) MUST have `cluster_id: null` and MUST be recorded as unlabeled for Channel A; they MUST NOT be exposed as negatives by the loader.
- DS3.7 With the same inputs and seed, the builder MUST write a byte-identical manifest (stable key order, sorted entries, no timestamps or absolute paths in the file). Different seeds MAY yield different assignments.
- DS3.8 Every split MUST contain both C and C++ entries and both human and AI entries whenever the (non-broken) input contains them; otherwise the builder MUST fail with an explicit error naming the missing stratum.
- DS3.9 `stats` MUST include: per-split counts by lang and source, block counts per course and split, student overlap across splits (count of student ids in >1 split, by pair), near-dups among GT negatives, and dup-group size distribution. Student overlap MUST be reported, not prevented.

Scenarios
- Given a fixture of 10 blocks per course letter, When the builder runs with seed 7 twice, Then the two manifests are byte-identical (`sha256` equal); with seed 8 the file is valid but MAY differ.
- Given the produced manifest, When entries are grouped by block, Then each block maps to exactly one split; the same holds for each `dup_group` and each `cluster_id`.
- Given a fixture where student S is in cluster 1 (block Z1) and cluster 2 (block Z4), When the builder runs, Then each cluster stays within one split, the blocks are not merged, and the link is counted in `stats.gt.cross_split_student_clusters` when the blocks land in different splits.
- Given a cluster listing a file not on disk, When the builder runs, Then the file appears in `stats.unresolved_cluster_members` and not in `entries`.
- Given B2017 fixture files without ground truth, When the loader is asked for Channel A negatives, Then none of those ids are returned.
- Given a fixture with C-only train candidates in all blocks of a course (so a stratum cannot be filled), When the builder runs, Then it raises an error naming the missing stratum.
- Given a course with only 3 blocks, When the builder runs, Then it raises an error stating the 2-block minimum cannot be met.
- Given the same student id in blocks assigned to different splits, When the builder runs, Then `stats` lists the overlap and no error is raised.

### DS4. Split loader API
- DS4.1 `models/evaluation` MUST expose a loader returning entries for a requested split (and optional filters: lang, source, course), validating the manifest schema, computing the manifest file's sha256, and refusing to load when a caller-supplied `expected_sha256` does not match. The manifest MUST NOT embed its own hash; consumers (calibration files, run reports) MUST record the manifest sha256 they used.
- DS4.2 The loader MUST NOT return `broken`-flagged entries unless `include_broken=True` is passed.

Scenarios
- Given a valid manifest, When `load_split("val")` is called, Then every returned entry has `split == "val"` and no `broken` flag.
- Given a manifest edited after generation, When it is loaded, Then the loader raises a hash-mismatch error.

## Capability: evaluation-metrics (new)

### EM1. Metrics (numpy/scikit-learn; vectorized)
- EM1.1 The package MUST provide ROC-AUC, PR-AUC, precision/recall/F1/FPR at a threshold, MAP@R, ECE (equal-width bins, count recorded), and per-group breakdown (by lang, source, course, model, profile).
- EM1.2 ROC-AUC MUST be computed by a vectorized rank-based method (no O(n*m) pair loops) and MUST handle ties by midranks.
- EM1.3 Single-class input to ROC-AUC/PR-AUC MUST NOT raise an unhandled exception and MUST NOT return a number; it MUST return `None`/NaN with a machine-readable reason (`single_class`).
- EM1.4 A group with zero samples MUST be omitted or reported with `n=0` and null metrics, never cause a division by zero.
- EM1.5 Threshold metrics MUST define precision as null (not 0 or 1) when there are no predicted positives, and recall as null when there are no positives.
- EM1.6 Threshold metrics MUST always be reported under an `observed` view (prevalence of the evaluated set) and a `balanced` view (class-reweighted to 0.5); a `natural` view MUST be added only when a prevalence value is configured for the channel. The view used MUST be labelled in the output.

Scenarios (known values)
- Given scores `[0.9,0.8,0.2,0.1]` with labels `[1,1,0,0]`, Then ROC-AUC = 1.0; with labels `[0,0,1,1]`, Then ROC-AUC = 0.0.
- Given all scores equal, Then ROC-AUC = 0.5 (ties via midrank).
- Given scores `[0.5,0.5,0.9,0.1]` and labels `[1,0,1,0]`, Then ROC-AUC = 0.875.
- Given labels all 0 (or all 1), Then ROC-AUC and PR-AUC are null with reason `single_class` and no exception.
- Given a large random score vector (n=20000) with random labels and seed, Then ROC-AUC is within 0.02 of 0.5 and the call completes (n is large enough that a quadratic pair loop would be impractical; no wall-clock assertion).
- Given a retrieval toy case where a query has R=2 relevant items and ranking `[rel, non, rel, non]`, Then AP@R considers only the top R results and equals 1/2 (precision 1 at rank 1, rank 2 not relevant, divided by R); a ranking `[rel, rel, non, non]` gives 1.0; MAP@R is the mean over queries, and a query with R=0 is excluded and counted.
- Given 10 predictions at confidence 0.8 of which exactly 8 are correct (one bin), Then ECE = 0; given the same with 5 correct, Then ECE = 0.3.
- Given predictions with no positive predictions at the threshold, Then precision is null and recall/FPR are still defined.
- Given a group filter with no matching rows, Then the breakdown contains `n=0` for it and no exception.

### EM2. Bootstrap confidence intervals
- EM2.1 Every headline metric MUST be reportable with a bootstrap CI95 (percentile method, default 1000 resamples, resampling unit configurable; for grouped data the unit SHOULD be the block or dup group).
- EM2.2 The bootstrap MUST be reproducible given a seed and MUST NOT mutate global RNG state.
- EM2.3 Resamples in which a metric is undefined (e.g. single class) MUST be skipped and their count reported; if too few valid resamples remain, the CI MUST be null.

Scenarios
- Given a fixed dataset and seed, When the CI is computed twice, Then results are identical; with another seed they MAY differ.
- Given a dataset, Then the point estimate lies within [lo, hi].
- Given a dataset with 2 positives among 100, Then `skipped_resamples` is reported and the CI is either valid or null, never an exception.

### EM3. Calibration and threshold selection (val only)
- EM3.1 The package MUST provide temperature, Platt and isotonic calibrators with `fit(scores, labels)` and `transform(scores)`.
- EM3.2 `fit` MUST be callable only with val-split data: the fitting entry point MUST require entries (or an explicit split tag) from the loader and MUST raise an error if any entry has `split != "val"`.
- EM3.3 Threshold selection MUST choose, on val, the lowest threshold whose FPR is <= the target (primary 5%, secondary 1%), and record achieved FPR, TPR and support (negatives count) at each target. A target whose val negatives count is below a configured minimum MUST be flagged `low_support`.
- EM3.4 If no threshold satisfies the target, selection MUST return an explicit `unachievable` result, not an arbitrary threshold.
- EM3.5 Fitted artifacts MUST be written to `calibration.json` with: schema version, channel, calibrator type and parameters, thresholds per FPR target, manifest hash, seed, val n and class counts, creation provenance (git sha). The writer MUST be deterministic for the same inputs.
- EM3.6 Loading `calibration.json` MUST validate schema and reproduce the calibrator: `transform` on a fixed vector before write and after round-trip MUST be equal within 1e-9.
- EM3.7 Applying a frozen calibration to test MUST NOT refit or change any parameter.

Scenarios
- Given synthetic val scores where negatives are Uniform(0, 0.6) and positives Uniform(0.4, 1), When thresholds are selected for FPR 5%, Then the achieved val FPR is <= 0.05 and no lower candidate threshold also satisfies it.
- Given val negatives that overlap perfectly with positives (AUC ~0.5) and a 1% target with few negatives, Then the result is flagged `low_support` or `unachievable`, as applicable.
- Given entries containing a test-split entry, When `fit` is called, Then it raises an error and no artifact is written.
- Given a fitted Platt calibrator, When saved and reloaded, Then `transform` outputs equal within 1e-9 and the file validates against the schema; a file with an unknown schema version or missing key is rejected.
- Given monotone raw scores, Then each calibrator preserves ranking (ROC-AUC unchanged) on a fixed vector.

### EM4. Seeding
- EM4.1 A single seeding helper MUST seed `random`, `numpy` and, if installed, `torch` (including deterministic flags), and return the seed for provenance. Importing the evaluation package MUST NOT require torch.

Scenario
- Given torch is not installed, When the helper is called, Then it succeeds and seeds the remaining libraries.

## Capability: evaluation-reporting (new)

### ER1. Run directory
- ER1.1 A run MUST write `runs/<channel>/<timestamp>/` (UTC, filesystem-safe timestamp; root overridable) containing: `config.json`, `metrics.json`, `report.md`, curve CSVs (ROC and PR points, reliability bins), and PNGs `roc.png`, `pr.png`, `confusion.png`, `reliability.png`.
- ER1.2 Provenance in `config.json` MUST include: git sha (and dirty flag; `unknown` if git is unavailable, without failing), seed, manifest sha256, calibration artifact hash (if used), split evaluated, channel, thresholds used, package versions of numpy/scikit-learn, and CLI args.
- ER1.3 `metrics.json` MUST include each headline metric with `value`, `ci95` (`[lo, hi]` or null), `n`, class counts, and the view (observed/balanced/natural).
- ER1.4 Plotting MUST use the matplotlib Agg backend and MUST work headless. If a plot cannot be produced (e.g. single class), the run MUST still complete, omit that PNG, and note the reason in `report.md`.
- ER1.5 `report.md` MUST state the split, manifest hash, thresholds, headline metrics with CIs, support warnings (`low_support`), and the student-overlap caveat.
- ER1.6 Two runs MUST NOT overwrite each other; a colliding timestamp MUST yield a distinct directory.
- ER1.7 `runs/` MUST be fully gitignored; selected `metrics.json`, `report.md`, `config.json` and `calibration*.json` MAY be committed explicitly with `git add -f` (documented in README).

Scenarios
- Given a synthetic scored dataset, When a run is written, Then the directory contains all ER1.1 files and `config.json` has non-empty `seed`, `manifest_sha256`, `git_sha` keys.
- Given the repo is not a git checkout, When a run is written, Then `git_sha` is `"unknown"` and the run succeeds.
- Given single-class input, When a run is written, Then `roc.png` is absent, `report.md` explains why, and `metrics.json` carries null AUC with reason.
- Given two runs started within the same second, Then two distinct directories exist.
- Given `.gitignore`, Then `git check-ignore` matches both `runs/char_cnn/x/roc.png` and `runs/char_cnn/x/metrics.json` (selective commits use `git add -f`).

## Capability: benchmark-suite (modified)

- BS1 `scripts/benchmark_suite.py` MUST obtain its samples only through the split loader with `split="test"` and MUST raise an error if any sample it is given has another split value.
- BS2 It MUST read decision thresholds from `calibration.json`; hardcoded threshold literals (0.85, 0.70, `THRESHOLD_AI=0.20`) MUST NOT be used as defaults. If `calibration.json` is missing, it MUST fail with an actionable message rather than fall back to constants.
- BS3 Metrics MUST be computed through `models/evaluation` and the run MUST write a full run directory (ER1) with the test split recorded.
- BS4 The suite MUST NOT fit or modify calibration.
- BS5 Legacy `benchmark_*results.json` files MUST be marked as legacy/non-comparable in the README; new results MUST carry the manifest hash.

Scenarios
- Given a fixture manifest and a `calibration.json` with thresholds 0.61/0.33, When the suite runs with a stub scorer, Then the reported thresholds in `config.json` are 0.61 and 0.33.
- Given samples including a `val` entry, When passed to the suite, Then it raises an error naming the offending id.
- Given no `calibration.json`, When the suite runs, Then it exits non-zero with a message pointing to the calibration step.
- Given a grep of `scripts/benchmark_suite.py`, Then no numeric threshold default literal remains.

## Capability: golden-set (modified)

- GS1 The golden set MUST be rebuilt exclusively from `split == "test"` manifest entries; its manifests (`manifest*.json`) MUST record the source manifest hash.
- GS2 The golden set MUST contain zero ids whose split is `train` or `val`; this MUST be verified by a test against the split manifest.
- GS3 `broken`-flagged entries MUST NOT be included.
- GS4 Selection MUST be deterministic for a given seed and replace the per-file sha256 hashing in `data/golden_set/build_manifest.py`.
- GS5 `perturb_corpus.py` and its tests MUST read the rebuilt golden set and MUST NOT reference train/val files.
- GS6 `data/golden_set/README.md` MUST describe the new provenance and the leakage that the previous version had (1825/2621 overlap).

Scenarios
- Given a fixture manifest with train/val/test entries, When the golden set is built, Then every golden id has `split == "test"` and the intersection with train and val ids is empty.
- Given a `broken` test entry, When built, Then it is absent from the golden set.
- Given the same seed, When built twice, Then the golden manifests are byte-identical.
- Given a golden manifest, Then it contains `source_manifest_sha256` equal to the hash of `split_v1.json`.

## Non-functional and compatibility

- NF1 No new runtime dependency beyond numpy, scikit-learn; `matplotlib` is added to `requirements-dev.txt` only. `datasketch` MUST NOT be used.
- NF2 Backend runtime paths MUST NOT import `models/evaluation`; `models/char_cnn/dataset_manifest.json` and `scripts/generate_tt_figures.py` are unchanged by this change.
- NF3 `pytest tests/ backend/tests/` MUST pass for the new and updated tests, including `tests/test_char_cnn_robustness.py` if it reads golden or split data, without requiring Postgres, Chroma or model weights.
