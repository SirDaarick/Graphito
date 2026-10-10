# Proposal: Evaluation Foundation (eval-foundation)

## Intent

The model audit found leaky, non-reproducible evaluation: the golden set reuses 1825/2621 CharCNN train/val samples, splits are sha256-hashed per file (`data/golden_set/build_manifest.py:45-48`), thresholds are hardcoded with no fitted artifact (0.85/0.70, `THRESHOLD_AI=0.20`), training reports only argmax acc/P/R/F1 without seeding, and figures use literal numbers. No reported metric can be defended in the thesis. This change (SDD-1 of Phase 1) builds one honest, shared split and evaluation toolkit before SDD-2/3/4 fix and re-measure the models.

## Scope

### In Scope
- **Split builder** + committed manifest `data/splits/split_v1.json`: group key = course letter + Zx block (A2016/Z3 and A2017/Z3 share a group); per course ~20% blocks test, ~15-20% of the remainder val, rest train; seeded, deterministic, C and C++ in every split.
- **Hygiene (flag, never delete)**: exclude only broken files (empty, < ~50 effective bytes, missing student id, `(1)` copies); exact dedup on comment/whitespace-stripped hash; near-dup MinHash (numpy, 5-token shingles, normalized identifiers, Jaccard >= 0.85) within block; each dup group in exactly one split.
- **Manifest fields**: repo-relative id, course, block, assignment, student, lang, source (human/ai), model, profile, sha256, norm_hash, dup_group, cluster_id, split, flags; plus config and stats (student overlap, cross-block dup groups, near-dups among GT negatives).
- **`models/evaluation/` package**: metrics (ROC-AUC, PR-AUC, P/R/F1/FPR at threshold, MAP@R, ECE, bootstrap CI95, per-group breakdown); calibration (temperature/Platt/isotonic) and threshold selection fitted on val only, persisted as `calibration.json`; FPR target 5% primary, 1% secondary; balanced and natural-prevalence views; global seeding; split loader API for SDD-2/3.
- **Run reports** in `runs/<channel>/<timestamp>/`: config, manifest hash, git sha, seed, `metrics.json`, `report.md`, curve CSVs, ROC/PR/confusion/reliability PNGs (matplotlib Agg).
- **Consumers**: rebuild golden set from the test split; `scripts/benchmark_suite.py` evaluates test split only via `models/evaluation`; update `tests/test_benchmark_suite.py`, `tests/test_perturb_corpus.py`, `data/golden_set/perturb_corpus.py`, `data/golden_set/README.md`, regenerated `manifest*.json`, `tests/test_char_cnn_robustness.py` if it reads golden/split data.
- Add `matplotlib` to `requirements-dev.txt`; gitignore `runs/` except selectively committed `metrics.json`/`report.md`.

### Out of Scope
- Model code fixes and retraining (SDD-2 CharCNN, SDD-3 GraphCodeBERT DFG input).
- Backend calibration/threshold integration (SDD-4); `models/char_cnn/dataset_manifest.json` and `scripts/generate_tt_figures.py` stay untouched until SDD-2/SDD-4.
- Content-level AI sample quality filtering (SDD-2).
- Phase 2: contrastive training, AI data regeneration, leave-one-LLM-out, TF-IDF probe.

## Capabilities

### New Capabilities
- `dataset-split`: deterministic assignment-block split, hygiene flags, dedup groups, manifest + stats.
- `evaluation-metrics`: metrics, bootstrap CIs, per-group breakdown, val-only calibration and threshold selection.
- `evaluation-reporting`: reproducible run directories with provenance, metrics, curves and plots.

### Modified Capabilities
- `benchmark-suite`: evaluates only the test split through `models/evaluation`; no hardcoded thresholds.
- `golden-set`: rebuilt from the test split; no train/val leakage.

## Approach

- Disk is source of truth (not `.generation_state.json`). Scan `data/raw/src` and `data/output`, normalize, flag, dedup, then assign groups to splits with a seeded RNG; cross-block dup groups are pinned to one split and counted.
- Plagiarism labels from `data/raw/ground-truth-static-anon.txt`; clusters referencing files not on disk (B2016/Z6) are recorded, not invented. B2017 is unlabeled for Channel A (never treated as negatives).
- Pure-numpy/scikit-learn metrics with vectorized AUC (replaces O(n*m) loop). Calibrators and thresholds are fit on val, frozen to `calibration.json`, then applied to test.
- Student overlap across splits is unavoidable (ids recur across courses/years); measured and reported, not hidden.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `scripts/build_split.py` (name TBD in design) | New | Split builder |
| `data/splits/split_v1.json` | New | Committed manifest |
| `models/evaluation/` | New | Metrics, calibration, reporting, loader, seeding |
| `scripts/benchmark_suite.py` | Modified | Test-split only, uses evaluation package |
| `data/golden_set/*` | Modified | Rebuilt manifests, perturb script, README |
| `tests/test_benchmark_suite.py`, `tests/test_perturb_corpus.py`, `tests/test_char_cnn_robustness.py` | Modified | Align with new split |
| `tests/` | New | Unit tests for split determinism, metrics, calibration |
| `requirements-dev.txt`, `.gitignore` | Modified | matplotlib; `runs/` rules |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Student overlap across splits inflates Channel A/B scores | High | Report overlap counts and per-group metrics; document as limitation |
| Few Zx blocks per course make val/test small and noisy | Med | Bootstrap CI95; report block counts; secondary 1% FPR flagged as low-support |
| MinHash threshold (0.85) over/under-groups templated assignments | Med | Record threshold in config; report group-size stats; sensitivity check at 0.80/0.90 |
| Historical benchmark JSONs (`benchmark_*results.json`) become non-comparable | High | Mark as legacy in README; new runs carry manifest hash |
| Cross-block dup groups distort per-course split ratios | Low | Count and flag; report actual ratios |
| GT clusters with missing files or overlapping membership | Med | Record unresolved members; deterministic cluster assignment rule |

## Rollback Plan

All work lands as new files plus scoped edits on a feature branch. Revert the work-unit commits; the previous golden set manifests and benchmark script are restored from git. No backend runtime path depends on this change, so rollback has no service impact.

## Dependencies

- numpy, scikit-learn (present); matplotlib (added to `requirements-dev.txt`). No datasketch.

## Success Criteria

- [ ] Rebuilding the split with the same seed yields a byte-identical `split_v1.json`.
- [ ] No assignment block, dup group, or GT cluster spans more than one split.
- [ ] Golden set contains zero train/val samples.
- [ ] Every split contains both C and C++ and both human and AI samples.
- [ ] Thresholds/calibration are produced from val only and stored in `calibration.json`; benchmark reads them instead of constants.
- [ ] A benchmark run writes a complete `runs/<channel>/<timestamp>/` directory with git sha, seed, manifest hash, metrics with CI95.
- [ ] `pytest` passes for updated and new tests.

## Open Questions

- Final val fraction (15% vs 20%) given actual block counts per course.
- Whether near-dup sensitivity (0.80/0.90) is reported in SDD-1 or deferred.
