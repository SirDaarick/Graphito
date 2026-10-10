# Verification Report: eval-foundation

- Change: `eval-foundation` (Graphito)
- Branch verified: `feat/eval-foundation-05-data` (HEAD `5f84c75`, 25 commits over `main`)
- Mode: standard verify (no Strict TDD flag supplied), openspec file persistence
- Date: 2026-10-10
- Verifier: read-only; no source, test or data file was modified

## Verdict

**PASS WITH WARNINGS**

Every spec requirement has a passing covering test or a verified real artifact. Two requirements are
satisfied through documented amendments (DEVIATION, not failure). No CRITICAL issue. The warnings are a
pre-existing, unrelated test failure and deferred review follow-ups that do not break a MUST.

## Completeness (tasks.md)

| Metric | Value |
|---|---|
| Task checkboxes | 37 |
| Ticked | 37 |
| Unticked | 0 |
| Tasks with recorded evidence | all WU1-WU12 have an `Evidence` line (RED/GREEN + suite counts) |

WU6 is merged into WU12 as documented. Decisions D-A and D-B are resolved; D-C (chain strategy) was
resolved in practice (feature-branch chain, base `feat/eval-foundation`).

## Test Summary

Command: `python -m pytest tests/ backend/tests/ -q -p no:cacheprovider` (repo root, Python 3.14).

| Result | Count |
|---|---|
| Passed | 396 |
| Failed | 1 |
| Skipped | 1 |
| Duration | 112 s |

The single failure is `tests/test_calibration_experiment.py::test_graphcodebert_calibration`
(`AssertionError: QuickSort ... < 25%, dio: 0.3142`, a GraphCodeBERT similarity assertion on real model
weights). It is pre-existing and untouched by this change:

- `git diff --stat main -- tests/test_calibration_experiment.py` -> empty.
- `git diff --stat main -- models ':!models/evaluation'` -> empty (no model code the test depends on changed).
- Last change to the test file: `8c4eb3a` on `main`.

Targeted spot run (14 tests: repo config, BS2 AST guard, ROC-AUC known values, cross-block dup pinning,
gzip hash over decompressed bytes, golden `source_manifest_sha256`, val-only `fit`): **14 passed**.

## Requirement -> Evidence Matrix

Test file prefix `tests/` omitted. Status: COMPLIANT / PARTIAL / MISSING / DEVIATION (documented amendment).

### dataset-split

| ID | Evidence (test or artifact) | Status |
|---|---|---|
| DS1.1 | `test_eval_splits.py::TestDiscovery::test_every_file_on_disk_is_discovered`, `::test_roots_are_overridable`, `::test_root_outside_repo_root_raises` | COMPLIANT |
| DS1.2 | `TestDiscovery::test_every_entry_carries_every_key_with_null_for_not_applicable`, `::test_ids_are_sorted_repo_relative_posix_paths`; real manifest entry keys include all DS1.2 fields | COMPLIANT |
| DS1.3 | `TestDiscovery::test_ai_metadata_is_parsed_from_the_filename`, `::test_unparseable_ai_name_is_kept_with_flag`, `::test_parse_path` | COMPLIANT |
| DS1.4 | `TestDiscovery::test_config_and_stats_are_present`; real `config` has seed, fractions, dedup threshold 0.85, `shingle_k` 5, hygiene, `builder_version` 1.2 | COMPLIANT |
| DS2.1 | `TestHygieneDedup::test_broken_files_are_flagged_kept_and_ungrouped`, `::test_copy_suffix_without_student_id_gets_both_sub_flags`, `::test_hygiene_flags_unit`; `test_eval_normalize.py::test_effective_length_threshold_boundary` | COMPLIANT |
| DS2.2 | `TestDiscovery::test_source_files_are_untouched` | COMPLIANT |
| DS2.3 | `TestHygieneDedup::test_identical_files_across_blocks_share_one_exact_group`; `test_eval_normalize.py::test_norm_hash_ignores_comments_and_whitespace` | COMPLIANT |
| DS2.4 | `TestHygieneDedup::test_comment_whitespace_rename_pair_shares_a_dup_group`, `::test_cross_block_near_dups_are_counted_not_merged`, `::test_mid_pair_is_merged_and_low_pair_is_not_at_operative_threshold`; `test_eval_dedup.py` (MinHash/LSH) | DEVIATION (tasks.md WU4 interpretation (a) + DS3.3 amendment: exact dups group globally, blocks not merged, cross-block group pinned) |
| DS2.5 | `TestHygieneDedup::test_threshold_sensitivity_is_monotone_and_matches_operative_groups`; real: 0.80=18,773 <= 0.85=19,170 <= 0.90=19,479 | COMPLIANT |
| DS3.1 | `TestAssignment::test_one_split_per_block_dup_group_and_cluster`, `TestAssignmentBlocks::test_config_records_the_group_key_rule`, `::test_zx_groups_split_counts_sibling_assignments_per_split`, `TestAssignment::test_cross_split_near_pairs_are_counted` | COMPLIANT (amended unit letter/Zx/Zy, years merged) |
| DS3.2 | `TestAssignment::test_test_and_val_get_at_least_two_blocks_and_fractions_are_recorded`, `::test_three_block_course_raises_on_two_block_minimum`, `TestAssignmentBlocks::test_invariants_hold_and_quotas_apply_per_letter`; real A 13/3/4 (test 0.20, val 0.15), B 17/5/6 (0.214, 0.179) | COMPLIANT |
| DS3.3 | `TestAssignment::test_cross_block_dup_is_pinned_to_most_held_out_split`; `test_eval_manifest.py::test_representatives_only_keeps_one_included_member_per_group`; real: 236 `cross_split_dup` exclusions | DEVIATION (documented amendment: cross-block dup pinning to most held-out split) |
| DS3.4 | `TestAssignment::test_overlapping_gt_lines_share_one_cluster`, `::test_student_clusters_in_several_splits_are_reported`; `test_eval_ground_truth.py::test_student_in_two_lines_merges_them_into_one_cluster`, `::test_student_cluster_links_span_assignments` | COMPLIANT (amended: merge only within an assignment) |
| DS3.5 | `TestAssignment::test_unresolved_member_is_in_stats_and_not_in_entries`; `test_eval_ground_truth.py::test_missing_file_goes_to_unresolved_not_to_members` | COMPLIANT |
| DS3.6 | `TestAssignment::test_course_without_gt_is_unlabeled_with_null_cluster`; `test_eval_manifest.py::test_channel_a_negatives_never_include_unlabeled_entries`; `test_eval_ground_truth.py::test_course_absent_from_ground_truth_is_unlabeled` | COMPLIANT |
| DS3.7 | `TestAssignment::test_rebuild_with_same_seed_is_byte_identical`, `::test_manifest_file_is_lf_sorted_and_one_entry_per_line`, `::test_gz_manifest_is_deterministic_gzip_of_the_canonical_json`, `::test_parallel_file_analysis_matches_serial`; real rebuild byte-identical (see below) | COMPLIANT |
| DS3.8 | `TestAssignment::test_every_split_has_both_langs_and_sources`, `::test_unfillable_stratum_raises_naming_it`; `test_eval_manifest.py::test_check_invariants_names_the_first_missing_stratum`; real: all 4 strata in every split | COMPLIANT |
| DS3.9 | `TestAssignment::test_student_overlap_is_reported_without_error`, `::test_negative_near_dups_are_counted_with_a_jaccard_histogram`, `::test_negative_near_dup_histogram_buckets`, `::test_dup_group_size_distribution`; real `stats.gt.negative_near_dup` has `by_split`, `n_pairs`, `histogram`, no pair list | COMPLIANT |
| DS4.1 | `test_eval_manifest.py::test_sha256_is_computed_from_the_file_bytes`, `::test_expected_sha256_mismatch_raises`, `::test_manifest_edited_after_generation_fails_the_hash_check`, `::test_schema_validation_rejects_bad_files`, `::test_gz_and_json_manifests_load_identically`, `::test_gz_sha256_is_over_the_decompressed_bytes`, `::test_gz_expected_sha256_mismatch_raises`; real manifest does not embed its hash | COMPLIANT (amended: hash over decompressed bytes, `expected_sha256`) |
| DS4.2 | `test_eval_manifest.py::test_load_split_returns_only_that_split_without_broken_or_excluded`, `::test_include_broken_returns_broken_entries` | COMPLIANT |

### evaluation-metrics

| ID | Evidence | Status |
|---|---|---|
| EM1.1 | `test_eval_metrics.py::test_threshold_metrics_known_counts`, `::test_ap_at_r_toy_cases`, `::test_map_at_r_matches_musgrave_toy_and_brute_force`, `::test_ece_known_values`, `::test_per_group_reports_empty_and_single_class_groups`, `::test_pr_curve_ends_at_full_recall` | COMPLIANT |
| EM1.2 | `::test_roc_auc_known_values` (1.0/0.0/0.5 ties/0.875), `::test_auc_and_ap_match_sklearn_on_tie_heavy_data`, `::test_large_random_auc_is_near_half` | COMPLIANT |
| EM1.3 | `::test_single_class_returns_none_with_reason`, `::test_empty_input_reason` | COMPLIANT |
| EM1.4 | `::test_per_group_reports_empty_and_single_class_groups` | COMPLIANT |
| EM1.5 | `::test_precision_null_without_predicted_positives`, `::test_recall_null_without_positives` | COMPLIANT |
| EM1.6 | `::test_views_observed_and_balanced_always_natural_only_when_configured`, `::test_reweighted_views_on_single_class_are_null_for_precision`; `test_eval_report.py::test_natural_view_only_when_configured` | COMPLIANT (amended views) |
| EM2.1 | `::test_bootstrap_is_seed_reproducible_and_brackets_point`, `::test_grouped_bootstrap_resamples_whole_units`; `test_eval_report.py::test_grouped_bootstrap_and_non_probability_scores` | COMPLIANT |
| EM2.2 | `::test_bootstrap_is_seed_reproducible_and_brackets_point`, `::test_bootstrap_leaves_global_rng_state_untouched` | COMPLIANT |
| EM2.3 | `::test_bootstrap_skips_undefined_resamples`, `::test_bootstrap_point_undefined_gives_null_ci` | COMPLIANT |
| EM3.1 | `test_eval_calibration.py::test_calibrators_preserve_ranking`, `::test_temperature_recovers_known_t` | COMPLIANT |
| EM3.2 | `::test_fit_rejects_split_tag_other_than_val`, `::test_fit_rejects_any_non_val_entry_and_writes_nothing`, `::test_fit_checks_every_id_against_the_manifest` | COMPLIANT |
| EM3.3 | `::test_select_threshold_is_lowest_meeting_target`, `::test_low_support_and_unachievable` | COMPLIANT |
| EM3.4 | `::test_low_support_and_unachievable` | COMPLIANT |
| EM3.5 | `::test_writer_is_deterministic`, `::test_round_trip_and_schema`, `::test_build_requires_manifest_hash`, `::test_git_info_and_unknown_fallback` | COMPLIANT |
| EM3.6 | `::test_round_trip_and_schema`, `::test_load_rejects_bad_files`, `::test_validate_rejects_bad_params_and_thresholds` | COMPLIANT |
| EM3.7 | `::test_frozen_apply_changes_no_parameter`; `test_benchmark_suite.py::test_frozen_calibration_is_not_modified` | COMPLIANT |
| EM4.1 | `test_eval_seed.py::test_seed_everything_without_torch_seeds_random_and_numpy`, `::test_seed_everything_seeds_torch_when_installed`, `::test_package_imports_without_torch` | COMPLIANT |

### evaluation-reporting

| ID | Evidence | Status |
|---|---|---|
| ER1.1 | `test_eval_report.py::test_run_dir_has_every_artifact_and_provenance`, `::test_roc_csv_columns_match_roc_curve` | COMPLIANT |
| ER1.2 | `::test_run_dir_has_every_artifact_and_provenance`, `::test_no_git_gives_unknown_and_run_succeeds`, `::test_gzip_manifest_path_records_decompressed_sha256` | COMPLIANT |
| ER1.3 | `::test_run_dir_has_every_artifact_and_provenance`, `::test_operating_point_cis_are_reproducible_for_a_seed`, `::test_single_class_omits_roc_png_and_explains` | COMPLIANT |
| ER1.4 | `::test_single_class_omits_roc_png_and_explains`, `::test_plot_failure_is_recorded_and_run_completes`, `::test_missing_matplotlib_records_artifacts_missing`, `::test_package_imports_without_torch_or_matplotlib` | COMPLIANT |
| ER1.5 | `::test_report_md_states_split_hash_thresholds_support_and_overlap` | COMPLIANT |
| ER1.6 | `::test_runs_in_the_same_second_get_distinct_dirs`; `test_benchmark_suite.py::test_runs_with_the_same_timestamp_publish_to_distinct_dirs`, `::test_publish_retries_when_a_concurrent_run_takes_the_name` | COMPLIANT |
| ER1.7 | `test_eval_repo_config.py::test_runs_directory_is_fully_ignored`; `git check-ignore` matches `runs/x/metrics.json`, `runs/char_cnn/x/{roc.png,metrics.json}` via `.gitignore:45 runs/`; README.md:176 documents `git add -f` | DEVIATION (documented amendment / D-A: `runs/` fully ignored) |

### benchmark-suite

| ID | Evidence | Status |
|---|---|---|
| BS1 | `test_benchmark_suite.py::test_val_golden_set_passed_as_test_raises_naming_the_id`, `::test_non_test_split_id_behind_a_test_tag_raises_naming_it`, `::test_golden_manifest_without_source_hash_is_refused` | COMPLIANT |
| BS2 | `::test_frozen_thresholds_from_calibration_reach_config` (0.61/0.33), `::test_missing_calibration_exits_non_zero_pointing_to_the_calibration_step`, `::test_no_numeric_threshold_literal_in_the_suite`, `::test_threshold_literal_guard_catches_every_float_position` | COMPLIANT |
| BS3 | `::test_run_dir_is_complete_and_carries_the_manifest_hash`, `::test_published_run_records_final_paths_and_complete_status` | COMPLIANT |
| BS4 | `::test_frozen_calibration_is_not_modified`, `::test_fit_in_run_fits_on_val_only_and_freezes_before_test` | COMPLIANT |
| BS5 | README.md:177 marks root `benchmark_*results.json` / `benchmark_charcnn_*.json` legacy and non-comparable; `::test_run_dir_is_complete_and_carries_the_manifest_hash` (new results carry the hash) | COMPLIANT |

### golden-set

| ID | Evidence | Status |
|---|---|---|
| GS1 | `test_golden_set_split.py::TestBuildCorpus::test_test_corpus_holds_only_test_ids`, `::test_source_manifest_sha256_matches_the_split_file`, `TestBuildManifest::test_manifest_carries_provenance_and_no_train`; real golden manifests checked below | COMPLIANT |
| GS2 | `TestBuildCorpus::test_test_corpus_holds_only_test_ids`, `::test_train_split_is_refused`, `TestBuildManifest::test_train_entry_in_provenance_raises_naming_it`; real check: 0 train/val ids in test manifests | COMPLIANT |
| GS3 | `TestBuildCorpus::test_broken_and_excluded_entries_are_absent` | COMPLIANT |
| GS4 | `TestBuildCorpus::test_rebuild_is_byte_identical`, `TestBuildManifest::test_manifest_rebuild_is_byte_identical`, `::test_no_split_hashing_left`, `::test_tiny_fixture_dedups_by_dup_group` | COMPLIANT |
| GS5 | `test_perturb_corpus.py::test_perturbs_the_rebuilt_golden_set_without_train_or_val`, `::test_problems_from_split_lists_only_that_split`, `::test_strip_comments_is_the_evaluation_package_function` | COMPLIANT |
| GS6 | `data/golden_set/README.md:9-10` documents the old 1825/2621 leakage and new provenance | COMPLIANT |

### non-functional

| ID | Evidence | Status |
|---|---|---|
| NF1 | `test_eval_repo_config.py::test_matplotlib_is_a_dev_only_dependency`; `git diff --stat main` on requirements: only `requirements-dev.txt` (+1); `git grep datasketch` (outside sdd/docs): no hit | COMPLIANT |
| NF2 | `git grep models.evaluation -- backend`: no hit; `git diff --stat main -- models/char_cnn/dataset_manifest.json scripts/generate_tt_figures.py`: empty | COMPLIANT |
| NF3 | Full suite: 396 passed, 1 skipped; only failure is pre-existing and untouched; `tests/test_char_cnn_robustness.py` unchanged vs main and passing; no Postgres/Chroma needed | COMPLIANT (see WARNING W1) |

### Counts

| Status | Count |
|---|---|
| COMPLIANT | 55 |
| PARTIAL | 0 |
| MISSING | 0 |
| DEVIATION (documented) | 3 (DS2.4, DS3.3, ER1.7) |
| Total requirement IDs | 58 (DS 20, EM 17, ER 7, BS 5, GS 6, NF 3) |

Amended requirements that now pass as rewritten (DS3.1, DS3.4, DS4.1, EM1.6) are counted COMPLIANT
because the spec text itself was amended.

## Real-Artifact Checks

Run with `PYTHONPATH=<repo root>` via `models.evaluation.manifest`.

| Check | Result |
|---|---|
| `load_manifest("data/splits/split_v1.json.gz", expected_sha256=e835362d...)` | loaded; sha256 = `e835362d2e7a4153ef97204d4b30e769759a0f8f54f7db67b9e1fb2639e5238f` (match) |
| Wrong `expected_sha256` | raises `ManifestHashError` |
| `check_invariants` | ok |
| Entries | 45,291 (42,389 included) |
| Config | `group_key` "letter/Zx/Zy (years merged)", seed 42, builder 1.2; manifest does not embed its own hash |
| Blocks per letter (train/val/test) | A 13/3/4, B 17/5/6 |
| train (included) | c/human 12,398, c/ai 428, cpp/human 12,412, cpp/ai 469 |
| val (included) | c/human 3,167, c/ai 87, cpp/human 3,641, cpp/ai 138 |
| test (included) | c/human 4,198, c/ai 140, cpp/human 5,120, cpp/ai 191 |
| `load_split` train/val/test | 25,707 / 7,033 / 9,649; every sample has the requested split and no `broken` flag |
| `data/golden_set/manifest.json` | 455 split ids, all `test`; `source_manifest_sha256` == split hash |
| `data/golden_set/manifest_none.json` | 455 ids, all `test`; source sha matches |
| `data/golden_set/manifest_strip-comments.json` | 455 ids, all `test`; source sha matches |
| `data/golden_set/manifest_val.json` | 251 ids, all `val`; source sha matches |

All four strata (C/C++ x human/AI) are present in every split.

## Determinism

`python scripts/build_split.py --seed 42 --out <scratchpad>/split_rebuild.json.gz` (outside the repo):
50 s total (dedup 11.3 s), 45,291 entries, attempt 0, printed sha256 `e835362d...`.

| File | SHA-256 of gz bytes |
|---|---|
| rebuild (scratch) | `D0FD900313278EA3772F46C8829A9E3DA4AA58971230DF78BF323B84BE0A1959` |
| `data/splits/split_v1.json.gz` (3,045,767 bytes) | `D0FD900313278EA3772F46C8829A9E3DA4AA58971230DF78BF323B84BE0A1959` |

**Byte-identical.**

## Git Hygiene

| Check | Result |
|---|---|
| `git check-ignore -v runs/x/metrics.json` | ignored (`.gitignore:45 runs/`) |
| `git check-attr binary diff -- data/splits/split_v1.json.gz` | `binary: set`, `diff: unset` |
| `.gitattributes` | `data/splits/*.json -diff eol=lf linguist-generated`, `data/splits/*.json.gz binary`; existing `Documentacion/** linguist-vendored` kept |
| Tracked under `data/splits` / `runs` | only `data/splits/split_v1.json.gz`; nothing under `runs/` |
| NF2/NF3 files vs main | `models/char_cnn/dataset_manifest.json`, `scripts/generate_tt_figures.py`, `tests/test_char_cnn_robustness.py`: no diff |
| `scripts/benchmark_suite.py` float literals | AST guard `test_no_numeric_threshold_literal_in_the_suite` passes |
| Working tree before report | clean |

## Deviations (documented)

| Requirement | Deviation | Amendment |
|---|---|---|
| DS2.4 | Identical (same `norm_hash`) files in different blocks share one exact `dup_group`; the blocks are not merged and the group is pinned per DS3.3. Cross-block near-dups are counted only. | tasks.md WU4 interpretation (a); DS3.3 cross-block dup pinning |
| DS3.3 | Cross-split dup groups pinned to most held-out split; others `excluded` + `cross_split_dup` (236 on real data) | Spec DS3.3 amendment |
| ER1.7 | `runs/` fully gitignored; selective commits with `git add -f` | Decision D-A, spec ER1.7 amended |
| DS3.1 / DS3.2 | Split unit is `letter/Zx/Zy` with years merged (builder 1.1+) | Spec header amendment 2026-10-10 |
| DS3.4 | Clusters merged only within one assignment; cross-block links reported | Spec DS3.4 amendment |
| DS4.1 | Committed manifest is `.json.gz`; sha over decompressed bytes; loader `expected_sha256` | Decision D-B, spec DS4.1 amended |
| EM1.6 | Views `observed` + `balanced`; `natural` only if configured | Spec EM1.6 amendment |

## Deferred Follow-ups (tasks.md WU11)

Reviewed against MUST requirements; none violates one.

| Follow-up | MUST impact |
|---|---|
| Stale `runs/.staging/` cleanup | none (`runs/` ignored; ER1.6 holds) |
| Duplicated fused config keys | none |
| Fused warnings merged by substring | none |
| Fused ranking score computed twice | none (efficiency) |
| `build_corpus` validates ids while copying | none (GS2 holds; partial copy on bad id is a robustness gap) |
| KeyError path for unachievable fused operating points untested | indirect EM3.4 risk on the fused path only; real STUB run with unachievable 1% targets completed (tasks.md WU12) -> WARNING W2 |
| `_publish` rebasing writes outside the try block | none (raw OSError instead of `PublishError`) |
| `PublishError` reaches the user as a traceback | none (staged run is kept) |
| Out-of-range Platt/temperature should raise `BenchmarkError` at the source | none |
| Rename `_threshold_literals` | none |

## Issues

### CRITICAL

None.

### WARNING

- W1: The full suite command exits non-zero because of `tests/test_calibration_experiment.py::test_graphcodebert_calibration` (similarity 0.3142 vs < 0.25 on real GraphCodeBERT weights). Pre-existing on `main`, file and dependent model code unchanged by this change.
- W2: The fused-path `KeyError` for unachievable operating points is untested (deferred follow-up); the channel-level `unachievable` result (EM3.4) is tested and the real STUB run completed with unachievable 1% targets.
- W3: Real-data label noise: 364,125 of 365,329 GT-negative near-dup pairs are identical after normalization, so Channel A FPR at high similarity is an upper bound (reported in stats, not a spec violation; must be carried into SDD-2/3 reporting).
- W4: Structural student overlap (1,121 students in more than one split) and sibling-topic exposure (`stats.zx_groups_split`, 343 cross-split near-dup pairs) are reported, as the spec requires, but limit how held-out test is.

### SUGGESTION

- Close the WU11 follow-ups that touch user-facing error paths (`PublishError` in `main()`, `_publish` OSError wrapping) before the benchmark is used for thesis numbers.
- Mark or isolate `test_graphcodebert_calibration` (e.g. a model-weights marker) so the suite exit code reflects this change's tests.
