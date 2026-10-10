# Design: Evaluation Foundation (eval-foundation)

## Technical Approach

A new import-only package `models/evaluation/` holds everything that SDD-2/3/4 will share: seeding, C/C++ normalization, dedup, ground-truth parsing, the split builder and loader, metrics, calibration and run reporting. One thin CLI (`scripts/build_split.py`) writes the committed manifest `data/splits/split_v1.json`. Consumers (`data/golden_set/*`, `scripts/benchmark_suite.py`) stop hashing their own splits and hardcoding thresholds. Instead they read the manifest and an optional `calibration.json`. Disk is the source of truth. Nothing is deleted. Every exclusion is a flag with a reason.

## Architecture Decisions

| # | Decision | Rejected alternative | Rationale |
|---|----------|----------------------|-----------|
| D1 | Builder logic lives in `models/evaluation/splits.py`. The CLI is `scripts/build_split.py`, which inserts `ROOT` into `sys.path` (same pattern as `scripts/benchmark_suite.py:26-29`). | `python -m models.evaluation.splits build` | Matches the repo convention that CLIs live in `scripts/`. The library stays import-only and testable. pytest already has `pythonpath = .`. |
| D2 | The loader lives in its own `manifest.py` (stdlib only). Builder-only code (`dedup`, numpy) is never imported by consumers. | A single `splits.py` | SDD-2/3 training code then imports a light, stable API. |
| D3 | The split unit is the **block** = one assignment with its years merged, course letter + Zx + Zy (`A/Z3/Z1` covers A2016/Z3/Z1 and A2017/Z3/Z1). Amended 2026-10-10: the first real-data run with the earlier letter + Zx unit gave 5 (A) and 6 (B) blocks, so the 2-block test/val minimum made train the smallest split (train 9,665 human / 334 AI vs val 17,072 / 598 and test 14,409 / 521); per assignment the letters have 20 (A) and 28 (B) blocks. Sibling assignments of one Zx may land in different splits; that topic leakage is reported (`stats.zx_groups_split`, `stats.dedup.cross_split_near_pairs`), not prevented. `SplitConfig.group_key="zx_block"` keeps the old unit. Dup groups and GT clusters are unioned into **atomic units** (union-find). These are used to check invariants, pin cross-block groups and drive the grouped bootstrap. | Assigning atomic units directly; hashing per file | Assigning whole blocks guarantees that within-block groups never straddle splits. Atomic units are needed only for the cross-block exact dups and for honest CIs. |
| D4 | A cross-block exact dup group whose blocks land in different splits is **pinned** to its most held-out split (test > val > train). Members in other splits get `excluded: true` plus the flag `cross_split_dup`. Their `split` keeps the block's value. | Merging the blocks into one super-block | With roughly 20-28 blocks per letter (5-6 under the old letter + Zx unit), merging chains could collapse the quotas. Pinning keeps the block invariant strict, removes the leak from training and is counted in stats. |
| D5 | New `normalize.py` owns the string-aware `strip_comments` (ported from `perturb_corpus.py:35-66`) plus a regex C/C++ lexer. `perturb_corpus.py` re-exports it. | `CharPreprocessor.strip_c_comments` (`models/char_cnn/preprocess.py:40`); the tree-sitter parser | SDD-2/3 rewrite those modules, so coupling to them would break the split. The state machine is already tested and keeps the line count. |
| D6 | MinHash/LSH in pure numpy: 128 permutations, 16 bands x 8 rows, candidates verified by **exact** Jaccard on the shingle sets. | datasketch; LSH estimate only | No new dependency. Exact verification lets one pass serve the 0.80/0.85/0.90 sensitivity counts. |
| D7 | The manifest is a single deterministic JSON file: a header plus one sample object per line, LF only, `sort_keys`, no wall clock, no absolute paths. `.gitattributes`: `data/splits/*.json -diff eol=lf linguist-generated`. | `.json.gz` (zlib output can differ by platform); pretty JSON (about 2x size) | Byte identity is testable. Diffs stay readable per line. `eol=lf` protects identity under Windows `core.autocrlf`. |
| D8 | Metric cores are numpy (AUC via average ranks, AP, threshold metrics, ECE, MAP@R, bootstrap). sklearn is used only for Platt/isotonic and as the test oracle. scipy (pulled in by sklearn) is used for the 1-D temperature fit. | sklearn for everything | Small, auditable functions with explicit tie and single-class behavior. This replaces the O(n*m) loop at `benchmark_suite.py:38-51`. |
| D9 | `runs/` is fully gitignored. Selected `metrics.json`, `report.md`, `provenance.json` and `calibration.json` are committed with `git add -f` (documented). | Negation patterns `runs/*/*/*` + `!…` | Negation leaves every run showing up as untracked noise. Force-adding is explicit and selective. |
| D10 | `calibration.json` is per channel, fit on val only (raises `ValueError`, not `assert`, so `-O` cannot strip the check). Thresholds live in calibrated space. | Thresholds in raw space | Isotonic plateaus make a raw-space inverse ambiguous, so consumers always apply calibrator then threshold. |
| D11 | The benchmark has three explicit modes: `calibrated-fit-in-run` (`--calibrate`: score val, fit, freeze, score test), `calibrated-frozen` (`--calibration-a/-b PATH`) and `uncalibrated` (threshold-free metrics only, plus optional `--thresholds` labelled `manual`). | Falling back to `settings.THRESHOLD_*` | Constants are never used silently. The mode is written into `metrics.json`. |

## Module Layout (`models/evaluation/`)

| File | Responsibility |
|------|----------------|
| `__init__.py` | Re-exports `load_split`, `seed_everything`, `SplitManifest` |
| `seed.py` | `seed_everything(seed, deterministic_torch=False) -> np.random.Generator` (random, numpy, torch if importable). `stable_rng(seed, key) -> random.Random` (sha256-derived, as in `build_corpus.py:70`) |
| `normalize.py` | `strip_comments`, `tokenize(code) -> list[str]` (regex: string/char literals, numbers, identifiers, multi-char operators, punctuation), `effective_length`, `norm_hash` (sha256[:16] of space-joined tokens, identifiers kept), `shingle_tokens` (identifiers -> `ID`, literals -> `NUM/STR/CHR`, about 90 C/C++ keywords kept) |
| `dedup.py` | `token_ids` (blake2b-8 per unique token), `shingle_hashes(k=5)` (numpy rolling uint32), `minhash(sh, a, b)` with `(a*x+b) mod p`, p = 2^31-1, on uint64 with x reduced mod p and a, b < p (so a*x+b < 2^62: no overflow; a 2^61-1 modulus would overflow uint64 for a*x), `lsh_candidates(sigs, bands, rows)`, `jaccard(a, b)` (sorted unique arrays), `UnionFind` |
| `ground_truth.py` | `parse_ground_truth(path) -> dict[assignment, list[set[str]]]`, `resolve_clusters(...)`, `pairs(...)` |
| `splits.py` | `scan`, `parse_path`, `hygiene_flags`, `build_split(config) -> dict`, `validate(manifest)`, `write_manifest(dict, path)` |
| `manifest.py` | `load_split`, `SplitManifest`, `Sample`, `PairSet` |
| `metrics.py`, `calibration.py`, `report.py` | See the Interfaces section |

## Split Algorithm (`build_split`)

1. **Scan** `data/raw/src/**/*.{c,cpp}` (human) and `data/output/**/*.{c,cpp}` (AI). Sort by repo-relative POSIX id.
2. **Parse the path**: `course/Zx/Zy/<file>` gives `course` (A2016), `block` (`A/Z1/Z1`, years merged), `assignment` (`A2016/Z1/Z1`). Human: `student` = stem if it matches `^student\d+$`. AI: `^ref_(?P<profile>[a-z-]+)_or-(?P<model>.+)_\d{8}_\d{6}_\d+$`. On no match: `model/profile = null` and flag `ai_name_unparsed`.
3. **Hygiene**. Excluding flags: `empty`, `too_short` (`effective_length < 50`), `no_student_id`, `name_copy` (`\s\(\d+\)`, as in `build_corpus.py:37`). Informational flags: `non_utf8`, `ai_name_unparsed`.
4. **Normalize**: compute `norm_hash` and the 5-token shingles for all non-excluded files.
5. **Exact groups**: global, keyed by `norm_hash`. **Near-dup groups**: within a block, LSH candidates, then exact Jaccard. Each verified pair feeds three union-finds (0.80/0.85/0.90). A pair already joined in the 0.90 union-find skips verification, except human-human pairs, which are always verified for GT stats. `dup_group` = union of exact edges and 0.85 edges. The id is `dg-` + sha256(min member id)[:10], so it stays stable when unrelated files are added. `dup_rep` = smallest id in the group.
6. **GT clusters** (static file only): each line inside an assignment is a cluster. Lines that share a student are merged (counted). Members map to every file of that student in the assignment. Missing files or dirs (for example B2016/Z6) and excluded files are recorded as `unresolved` with a reason. `gt_status` per human sample: `positive` / `negative` / `ambiguous` (listed only in the dynamic or full GT) / `unlabeled` (course absent from every GT file, for example B2017). AI samples get `n/a`.
7. **Atomic units** = union-find over dup edges and cluster membership.
8. **Assign blocks** per course letter L. Sort the blocks and set n = count, `n_test = max(2, ceil(0.20 n))`, `n_val = max(2, ceil(0.15 n))`, and require `n_train >= 1`, else raise. Shuffle with `stable_rng(seed, f"{L}:{attempt}")` and take test, then val, then train. Check globally that every split has C, C++, human and AI. On failure, `attempt += 1` (cap 1000, then raise). The final `attempt` and the exact fractions go into `config`.
9. **Pin cross-block groups** (D4), then run `validate`. Validation raises if a block, an included dup group or a cluster spans more than one split, or if the lang/source coverage check fails.
10. **Stats, then write** with the deterministic serializer (floats rounded: ratios to 6 places, Jaccard to 4).

## Data Flow

    data/raw/src + data/output + ground-truth*.txt
        -> splits.build_split -> data/splits/split_v1.json (committed)
             |-> manifest.load_split -> SDD-2 CharCNN / SDD-3 GraphCodeBERT training
             |-> golden_set/build_corpus --split test|val -> corpus/ , corpus_val/ (+ provenance.json)
                    -> build_manifest -> manifest*.json -> benchmark_suite
                         val scores -> calibration.fit -> calibration_<channel>.json
                         test scores -> metrics -> report -> runs/benchmark/<ts>/

## Interfaces / Contracts

**Manifest `data/splits/split_v1.json`** (`"schema": "graphito.split/v1"`):
- `config`: seed, roots, group_key, fractions (target and actual per letter), min_blocks_per_split, attempt, hygiene thresholds, dedup params (k, num_perm, bands, rows, operative 0.85, sensitivity list, scope `block`), gt files, unlabeled_courses, builder_version.
- `blocks`: `{"A/Z1/Z1": {"split", "courses", "n_samples"}}`.
- `stats`: counts split x source x lang; block counts and ratios per letter; `zx_groups_split` (per `letter/Zx`, blocks per split); `student_overlap` (distinct students shared by train-val, train-test and val-test, overall and per letter); hygiene counts per flag; dedup (exact groups, near-dup `{0.80, 0.85, 0.90}: {n_groups, n_samples, max_size}`, mixed-source groups, cross-block groups, `cross_split_near_pairs` and pinned exclusions); gt (clusters per split, merged lines, `unresolved[]`, `negative_near_dup` counts per split plus the sorted human-human pair list).
- `groups`: non-singleton `dup` groups `{members, kind: exact|near|mixed, blocks, cross_block}` and `clusters` `{members, students, unresolved}`. Cluster id format: `A2016/Z1/Z1#03`.
- `samples[]`: `id, course, block, assignment, student, lang, source, model, profile, sha256, norm_hash, n_tokens, dup_group, dup_rep, cluster_id, gt_status, split, excluded, flags`.
- Size: about 44k records x about 330 B, so about 15 MB. If the file goes over 25 MB, the fallback is `.json.gz` with `mtime=0`, hashed on the decompressed bytes (open question).

```python
def load_split(path="data/splits/split_v1.json", expected_sha256: str | None = None) -> SplitManifest
class SplitManifest:
    path: Path; sha256: str; config: dict; stats: dict
    def samples(self, split=None, source=None, lang=None, *, include_excluded=False,
                representatives_only=False) -> list[Sample]
    def split_of(self, sample_id: str) -> str
    def clusters(self, split=None) -> dict[str, list[str]]
    def plagiarism_pairs(self, split: str, include_ambiguous=False) -> PairSet
        # all same-assignment human pairs in labeled courses; label 1 = same cluster
    def check_invariants(self) -> None
@dataclass(frozen=True)
class PairSet: a: np.ndarray; b: np.ndarray; label: np.ndarray; assignment: np.ndarray; ids: list[str]
```

**`metrics.py`**: pure functions on numpy arrays, with an optional `sample_weight` where it applies.
- `roc_auc(y, s) -> float | None` (average ranks via stable argsort and tie groups; `None` for a single class); `roc_curve`; `pr_curve`; `average_precision` (step-wise, sklearn definition).
- `threshold_metrics(y, s, t)`: tp/fp/tn/fn, precision, recall, f1, fpr, tpr, using `s >= t`.
- `map_at_r(sim, cluster_labels)` for one assignment. Queries are members of clusters of size >= 2. Candidates are all other samples, and the diagonal is excluded. R = cluster size - 1. AP@R = (1/R) * sum over i <= R of P(i) * rel(i). Ties use a stable index order. `mean_map_at_r(iterable)` takes the macro mean over all queries.
- `ece(y, p, n_bins=15)` and `reliability_bins` (equal-width bins, weighted |frac_pos - mean_pred|).
- `bootstrap_ci(fn, y, s, *, n_boot=1000, seed, groups=None, alpha=0.05) -> {value, lo, hi, n_valid}`: percentile method. `groups` resamples units with replacement. Single-class resamples are skipped and counted. The default unit in reports is the atomic unit. `block` is available as a sensitivity option.
- `per_group(fn, y, s, groups) -> {g: {n, n_pos, value}}`.
- `prevalence_weights(y, pi)`: class weights for the `observed` / `balanced` (pi = 0.5) / `natural` (pi from config; omitted when absent) views. AUC is invariant to these weights.

**`calibration.py`**: `ScoredSet(ids, scores, y, split, manifest_sha256)`. `fit(data, method: "temperature"|"platt"|"isotonic") -> Calibrator` raises unless `data.split == "val"` and, when a manifest is given, every id is in val. Temperature: `sigmoid(logit(clip(s)) / T)`. Platt: `sigmoid(a * logit(s) + b)`. Isotonic stores `X_`/`y_` with clip. `select_threshold(y, p, target_fpr) -> {threshold, achieved_fpr, tpr, n_neg, n_pos, low_support}`: the lowest t with FPR <= target, and `low_support = n_neg * target < 10`. `save/load_calibration`. Default method: `platt`.

```json
{"schema": "graphito.calibration/v1", "channel": "channel_b", "score_name": "ai_prob",
 "method": "platt", "params": {"a": 1.7, "b": -0.4},
 "thresholds": {"fpr_0.05": {"target_fpr": 0.05, "threshold": 0.81, "achieved_fpr": 0.048,
                             "tpr": 0.7, "n_neg": 1200, "n_pos": 900, "low_support": false},
                "fpr_0.01": {"...": "..."}},
 "primary": "fpr_0.05",
 "fit_set": {"split": "val", "n": 2100, "ids_labels_sha256": "..."},
 "manifest": {"path": "data/splits/split_v1.json", "sha256": "..."},
 "provenance": {"git_sha": "...", "dirty": false, "seed": 42}}
```

**`report.py`**: `RunContext.create(kind, config, seed, manifest_path, root="runs")` makes `runs/<kind>/<YYYYmmdd-HHMMSS>/` (UTC; adds a `-N` suffix on collision). `kind` is `benchmark`, `charcnn` or `graphcodebert`. The benchmark writes one subdir per channel (`channel_a/`, `channel_b/`, `fused/`). Files:
- `provenance.json`: git sha, `dirty`, argv, seed, manifest path and sha256, calibration sha256, python, platform, versions of numpy/sklearn/torch (via `importlib.metadata`, when present), config, created_at.
- `metrics.json` (`graphito.metrics/v1`): channel, split, mode, n, n_pos, prevalence_observed, `threshold_free {roc_auc, pr_auc, ece, map_at_r}`, each `{value, ci95, n_boot_valid}`, `operating_points {fpr_0.05: {threshold, source, low_support, observed, balanced, natural}}`, `per_group {lang, course, block, model, profile}`, bootstrap settings, warnings.
- `roc.csv`, `pr.csv`, `reliability.csv`; `roc.png`, `pr.png`, `confusion.png`, `reliability.png` (lazy `matplotlib.use("Agg")`; when matplotlib is missing, `artifacts_missing` is recorded instead of crashing).
- `report.md`: a template with provenance header, threshold-free table with CI95, operating points with low-support markers, per-group table, embedded plot links, and limitations (student overlap and block counts copied from the manifest stats).

## Consumers

- `build_corpus.py --split-manifest --split test|val`: keeps only included samples of that split, skips `unlabeled`/`ambiguous` humans (B2017 is skipped for human classes), uses `gt_status` instead of re-parsing GT, and writes `provenance.json` (corpus path -> split id, split, model, profile, dup_group). The default out is `corpus/` for test and `corpus_val/` for val (already gitignored by `corpus_*/`).
- `build_manifest.py`: drops `assign_split`. Split and metadata come from `provenance.json`. Without provenance, the build requires `--synthetic` (split = `test`). It asserts that no sample is train.
- `perturb_corpus.py`: re-exports `strip_comments` from `models.evaluation.normalize` and copies `provenance.json`. `--only-problems-from` is replaced by `--split-manifest/--split`, using `problems_from_split`.
- `benchmark_suite.py`: its metric functions delegate to `models.evaluation.metrics`. It adds the D11 modes and drops `DEFAULT_THRESHOLDS_SEM`. In calibrated modes, fused = OR of the channel decisions at calibrated thresholds, scored by the max of calibrated scores. Evaluating fused through the production `compute_decision` path moves to SDD-4. Every run writes a `RunContext`. The legacy `benchmark_*results.json` files are marked as legacy in the README.
- `tests/test_char_cnn_robustness.py` reads `models/char_cnn/dataset_manifest.json`, which is out of scope, so it stays unchanged.

## File Changes

| File | Action |
|------|--------|
| `models/evaluation/{__init__,seed,normalize,dedup,ground_truth,splits,manifest,metrics,calibration,report}.py` | Create |
| `scripts/build_split.py`, `data/splits/split_v1.json`, `.gitattributes` | Create |
| `data/golden_set/{build_corpus,build_manifest,perturb_corpus}.py`, `README.md`, `manifest*.json` | Modify / regenerate |
| `scripts/benchmark_suite.py` | Modify |
| `tests/test_benchmark_suite.py`, `tests/test_perturb_corpus.py`, `tests/fixtures/golden_set_tiny/provenance.json` | Modify / create |
| `tests/test_eval_{normalize,dedup,ground_truth,splits,manifest,metrics,calibration,report}.py`, `tests/eval_factory.py` | Create |
| `requirements-dev.txt` (`matplotlib`), `.gitignore` (`runs/`) | Modify |

## Testing Strategy

| Layer | What | Approach |
|-------|------|----------|
| Unit | normalize, dedup, GT, metrics, calibration | Hand-computed cases. sklearn as oracle for AUC/AP on random data with heavy ties. MinHash estimate within ±0.1 of exact Jaccard. LSH recall on planted near-dups. Temperature fit recovers a known T. Selected threshold meets FPR <= target. `fit` raises on non-val data. |
| Builder | split invariants | `tests/eval_factory.py` writes a synthetic tree into `tmp_path` (2 letters x 6 blocks, both years, C and C++, AI names, a GT file with overlapping lines, a missing-file member, a `(1)` copy, short files, a planted cross-block exact dup). Checks: byte-identical rebuild, different seed gives different blocks, min 2 blocks per split, pinning exclusion, `check_invariants`. |
| Integration | golden + benchmark | Existing tiny fixture plus provenance. Stub engine in each of the 3 modes. Run dir contents and schema keys. `uncalibrated` emits no operating points. |
| Real data | none in CI | Manual `scripts/build_split.py` run. Its stats go into the PR description. |

**Performance estimate (about 44k files)**: read and lex about 15 s; shingles and 128-permutation MinHash about 10-20 s (about 300 shingles x 128 uint64 per file); LSH and verification are block-local. Worst case is templated AI batches (about 2k similar files per block, about 2M pairs at about 20 µs each, so about 40 s per block). The 0.90 union-find skip prunes most of this. Target: under 5 min on a laptop. The builder logs per-stage timings.

## Migration / Rollout

No runtime migration. The old golden `manifest*.json` files are regenerated from the new corpus (real data, local). Historical benchmark JSONs are kept and marked legacy. Rollback = revert the work-unit commits.

Proposed work-unit order (about 400 authored lines each; advisory only):
1. `chore(eval)`: `.gitignore`, `.gitattributes`, requirements-dev, `seed.py`, `normalize.py` + tests
2. `feat(eval)`: `dedup.py` + tests
3. `feat(eval)`: `ground_truth.py` + tests
4. `feat(eval)`: `splits.py`, `scripts/build_split.py`, `tests/eval_factory.py` + tests
5. `feat(eval)`: `manifest.py` loader + tests
6. `data(splits)`: generated `split_v1.json` (generated, not counted as authored)
7. `feat(eval)`: `metrics.py` + tests
8. `feat(eval)`: `calibration.py` + tests
9. `feat(eval)`: `report.py` + tests
10. `refactor(golden-set)`: corpus/manifest/perturb from the split, plus fixture, tests, README
11. `refactor(benchmark)`: evaluation package, modes, run dirs, plus tests; regenerate golden manifests

## Risks

- Few blocks per letter: test/val CIs are wide and the sample ratios can deviate a lot from the block quotas. Actual ratios are reported; block-level bootstrap is a sensitivity option.
- Templated assignments or same-model AI batches can form very large near-dup groups. `max_size` and the sensitivity counts expose this. Groups never cross blocks, so this cannot leak.
- The manifest size (about 15 MB) is an estimate; the gzip fallback is an open question.
- Student overlap across splits is structural. It is measured, not fixed.
- The regex lexer misses raw strings, digit separators and `\` continuations in `//` comments (same limits as `preprocess.py`). The impact is limited to dedup recall.

## Open Questions

- [ ] If the real manifest exceeds about 25 MB, commit `.json.gz` (`mtime=0`) instead of plain JSON?
- [ ] Natural-prevalence value per channel. Until the thesis supplies a figure, the `natural` view is omitted and `observed` and `balanced` are always reported.
