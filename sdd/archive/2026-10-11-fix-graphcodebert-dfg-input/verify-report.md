# Verification Report: fix-graphcodebert-dfg-input (SDD-3)

- Branch: `feat/fix-graphcodebert-dfg-input` chain top `feat/fix-gcb-05-run` @ `355149c` (working tree clean)
- Base for frozen-path checks: `feat/fix-graphcodebert-dfg-input`
- Mode: standard verify (strict TDD not declared active; RED/GREEN evidence is recorded per task in `tasks.md`)
- Verifier: read-only; no source, test, data, run, stash or git state was modified

## Verdict

**PASS WITH WARNINGS**

No CRITICAL issues. Every spec requirement has a passing covering test or committed artifact; the
deviations are documented amendments. Warnings: one unticked task (8.4), the legacy class is not
byte-identical to the original beyond the header (documented adapter gate), NF5 not measured in
isolation.

## Tests

| Command | Result |
|---|---|
| `python -m pytest tests/ backend/tests/ -q -p no:cacheprovider -rs` | **1028 passed, 1 skipped, 0 failed** (174 s) |
| Skip | `tests/test_char_cnn_robustness.py:52` - unseen-subproblem dataset absent on disk (CharCNN, unrelated to SDD-3) |
| Spot run: `tests/test_gcb_reference_parity.py`, `test_gcb_v2_model.py::{test_mask_honoured_block_mask, test_mask_honoured_is_directional, test_hidden_states_equal_upstream_model_forward, test_real_model_loads_offline_and_honours_the_mask}`, `tests/test_lora_guard.py`, `tests/test_gcb_v2_windows.py`, `test_gcb_v2_encode.py::test_golden_real_tokenizer`, `test_gcb_facade.py::test_legacy_default_is_a_documented_deviation_until_sdd4` | **112 passed** (50.8 s, real-weights tests ran offline, none skipped) |

## Requirement -> evidence matrix

All test files are under `tests/`. Status reflects the full-suite run above (all listed tests passed).

| ID | Evidence | Status |
|---|---|---|
| GD1.1 | `test_gcb_reference_parity.py::{test_vendored_file_present, test_source_md_pins_a_40_hex_commit, test_vendored_files_are_byte_identical_to_recorded_hashes, test_license_is_mit, test_check_fails_when_a_reference_file_is_missing, test_check_fails_when_source_md_lacks_commit, test_check_fails_when_a_reference_file_is_modified}` | COMPLIANT |
| GD1.2 | `test_gcb_reference_parity.py::{test_token_parity_with_upstream, test_raw_walker_parity_with_upstream_dfg_java, test_filtered_dataflow_parity_with_upstream_extract_dataflow, test_parity_detects_a_divergence}` (18 snippets) | COMPLIANT (compound assignment excluded from parity, unit-tested under GD3.3; parent codes compared as sets as upstream uses `list(set())`) |
| GD1.3 | `test_dfg_parser.py::TestV2Declarators/TestV2Aggregates/TestV2ControlFlow` hand-written expectations | COMPLIANT |
| GD2.1 | `test_gcb_v2_dfg.py::test_dataflow_fields_and_nodes_alias`, `test_dfg_parser.py::TestV2NodeFormat::test_equal_length_parents_and_indices_point_to_tokens` | COMPLIANT (deviation (i): parent codes aligned 1:1 with idxs) |
| GD2.2 | `TestV2NodeFormat::test_edges_are_directional` | COMPLIANT |
| GD2.3 | `TestV2NodeFormat::test_deterministic_and_sorted_by_idx`, `test_gcb_v2_dfg.py::test_concurrent_extraction_is_deterministic` | COMPLIANT |
| GD3.1-3.2 | `TestV2DefUse::{test_declaration_with_initializer_defines, test_last_definition_wins}` | COMPLIANT |
| GD3.3 | `TestV2DefUse::test_compound_assignment_reads_and_writes_lhs` | COMPLIANT (deviation (g) vs design table, spec wins) |
| GD3.4 | `TestV2DefUse::{test_call_arguments_flow_into_definition, test_binary_unary_cast_subscript_reads}` | COMPLIANT |
| GD3.5 | `TestV2DefUse::{test_subscript_update_reads_and_writes_base, test_field_update_reads_and_writes_base}` | COMPLIANT |
| GD4.1 | `TestV2ControlFlow::{test_braceless_if_else_unions_both_branches, test_if_without_else_keeps_incoming_definition}` | COMPLIANT (deviation (f): else unions branch states only) |
| GD4.2 | `TestV2ControlFlow::{test_for_loop_carries_definitions_without_duplicates, test_for_second_pass_after_expression_initializer, test_while_and_dedup, test_range_for, test_do_while}` | COMPLIANT |
| GD4.3 | `TestV2ControlFlow::{test_switch_unions_all_cases, test_switch_default_case_is_walked}` | COMPLIANT |
| GD5.1-5.2 | `TestV2Declarators::{test_pointer_and_reference_declarators, test_pointer_return_function_parameters, test_array_and_reference_parameters, test_array_declarator_does_not_define_its_size}` | COMPLIANT |
| GD5.3 | `TestV2Aggregates::{test_struct_and_enum_bodies_are_tokens, test_field_write_defines_base_variable, test_function_scope_reset_and_globals}` | COMPLIANT |
| GD6.1 | `TestV2TokensAndErrors::{test_comments_absent, test_comment_markers_inside_strings_survive}` | COMPLIANT |
| GD6.2 | `TestV2TokensAndErrors::{test_parse_error_keeps_dfg, test_clean_parse_has_no_errors, test_missing_nodes_skipped}` | COMPLIANT |
| GE1.1 | `test_gcb_v2_encode.py::{test_token_split_in_three_is_contiguous, test_first_token_is_tokenized_without_prefix}` | COMPLIANT |
| GE1.2 | `test_gcb_v2_encode.py::test_config_450_plus_128_rejected`, `test_gcb_v2_dfg.py::test_invalid_config_rejected` | DEVIATION (amended: `code_length + data_flow_length <= 512`, `code_length` includes CLS/SEP, tasks 2.1) |
| GE1.3 | `test_gcb_v2_encode.py::{test_400_subtokens_with_full_dfg_are_truncated_to_384_minus_specials, test_small_input_is_not_truncated_and_has_fixed_length, test_excess_nodes_are_cut_in_order_and_flag_truncated, test_short_code_lends_its_unused_budget_to_nodes}` | DEVIATION (upstream node budget `L+D-len(source)`; tasks 3.2) |
| GE2.1-2.2 | `test_gcb_v2_encode.py::{test_positions_code_from_2_nodes_0_padding_1, test_node_position_does_not_depend_on_target_token, test_golden_*}` | COMPLIANT |
| GE3.1-3.2 | `test_gcb_v2_encode.py::{test_mask_rules_on_a_small_graph, test_golden_fake_tokenizer_real_dfg, test_golden_fake_tokenizer_synthetic, test_golden_real_tokenizer, test_golden_real_tokenizer_truncation}` | COMPLIANT |
| GE3.3 | `test_gcb_v2_encode.py::test_isolated_node_row_is_empty_as_upstream` | DEVIATION (isolated node row all-False as upstream; tasks 3.2) |
| GE4.1 | `test_gcb_v2_model.py::{test_node_embedding_is_mean_of_aligned_word_embeddings, test_node_embedding_on_encoded_input_uses_its_code_span}` | COMPLIANT |
| GE4.2 | `test_gcb_v2_model.py::{test_token_type_and_position_embeddings_are_added_by_hf, test_changing_token_type_embedding_changes_output, test_hidden_states_equal_upstream_model_forward}` | COMPLIANT |
| GE4.3 | `test_gcb_v2_model.py::{test_mask_honoured_is_directional, test_mask_honoured_block_mask, test_mask_honoured_on_an_encoded_input, test_real_model_loads_offline_and_honours_the_mask, test_encoder_is_eval_fp32_deterministic_and_batched}` | COMPLIANT |
| GE4.4 | `test_gcb_v2_model.py::{test_non_eager_attention_is_refused, test_mask_probe_raises_when_the_mask_is_ignored, test_3d_mask_is_rejected_or_equivalent_to_4d}` | COMPLIANT |
| GE5.1-5.3 | `test_gcb_v2_windows.py::{test_plan_fits_budget_is_a_single_upstream_input, test_plan_long_file_uses_382_191_windows, test_fitting_file_is_bit_identical_to_upstream_encode, test_starts_for_1000_subtokens_follow_the_spec_scenario, test_short_sequence_gives_one_window, test_last_window_ends_at_the_last_subtoken, test_cap_gives_evenly_spaced_starts_ending_at_file_end, test_long_file_windows_restrict_nodes_shift_spans_and_reindex_parents}` | COMPLIANT (windows 382/191/max 16 per design amendment) |
| GE5.4 | `test_gcb_v2_embed.py::test_file_embedding_is_the_unweighted_mean_of_window_poolings`, `test_gcb_v2_windows.py::{test_cap_sets_truncated, test_dfg_nodes_used_counts_distinct_nodes_and_node_budget_truncates}` | COMPLIANT |
| GE5.5 | `test_gcb_v2_windows.py::test_windows_do_not_split_by_lines` | COMPLIANT |
| GE6.1-6.2 | `test_gcb_v2_embed.py::{test_pool_hidden_cls_and_mean_over_code_positions_only, test_cls_and_mean_differ_and_come_from_one_forward_pass, test_pooling_is_echoed_and_selects_the_embedding}` | COMPLIANT (name `mean` = spec `mean_code`, documented) |
| GE7.1-7.2 | `test_lora_guard.py::{test_default_config_has_no_adapter_although_the_shipped_one_exists, test_default_engine_does_not_load_the_adapter, test_explicit_adapter_path_is_ignored_with_a_warning, test_peft_is_never_imported_on_the_facade_path, test_legacy_class_without_load_adapter_ignores_an_explicit_path}` | COMPLIANT |
| GE7.3 | `test_gcb_facade.py::{test_v2_keys_are_legacy_keys_plus_honest_fields, test_v2_success_is_honest, test_real_engine_style_call}` | COMPLIANT |
| GE7.4 | `test_gcb_facade.py::{test_v2_used_graph_is_false_without_variables, test_v2_used_graph_is_false_for_the_no_dfg_ablation, test_v2_long_file_has_several_windows_and_the_same_shape, test_real_facade_v2_smoke}` | DEVIATION (amended: facade default `legacy`, v2 explicit; `dfg_nodes_used` = distinct nodes placed) |
| GE7.5 | `test_gcb_facade.py::{test_default_dispatches_to_legacy_with_adapter_off, test_legacy_values_equal_the_frozen_legacy_class, test_legacy_default_is_a_documented_deviation_until_sdd4}`, `test_lora_guard.py::test_legacy_load_adapter_true_applies_the_shipped_adapter` | DEVIATION (amended 2026-10-11; see frozen-path note on `load_adapter` gate) |
| GE7.6 | `test_gcb_facade.py::test_fusion_config_fields_are_preserved`; `models/fusion.py` no diff | COMPLIANT |
| GV1.1-1.2 | `test_gcb_v2_pairs.py::{test_exclusions_are_counted, test_blocks_map_pair_indices_to_ids_of_their_assignment, test_embedding_scores_equal_brute_force_cosine}`; run `data_summary.json` exclusions | COMPLIANT |
| GV2.1-2.2 | `test_gcb_v2_cache.py::{test_cache_key_is_order_independent_and_sensitive_to_every_component, test_same_file_is_encoded_once_and_reloaded_from_disk, test_changed_key_component_misses, test_duplicate_contents_share_one_entry}` | DEVIATION (pooling stored inside the entry, not a key component; design D9) |
| GV3.1 | `test_gcb_v2_evaluate.py::test_test_metrics_bootstrap_by_assignment_with_val_operating_points`, `test_gcb_v2_pairs.py::test_map_at_r_ci_resamples_assignments_reproducibly` | COMPLIANT (MAP@R CI via assignment bootstrap, documented) |
| GV3.2 | `test_gcb_v2_evaluate.py::{test_selection_uses_val_files_only_and_test_after_selection, test_thresholds_are_selected_on_raw_val_scores, test_test_stage_requires_selection_and_runs_once, test_choose_pooling_by_val_pr_auc_then_map_then_cls}` | COMPLIANT |
| GV3.3 | `test_gcb_v2_evaluate.py::test_undefined_metrics_are_null_with_reason` | COMPLIANT |
| GV4.1-4.2 | `test_gcb_v2_pairs.py::{test_views_drop_only_identical_negatives, test_map_at_r_per_assignment_and_identical_negatives_removed}`; run dropped counts | COMPLIANT |
| GV5.1-5.2 | `test_gcb_v2_baselines.py::{test_token_jaccard_equals_reference_set_jaccard, test_winnowing_hand_case, test_all_methods_score_identical_pair_sets_per_view, test_legacy_*}`, `test_gcb_v2_evaluate.py::test_every_method_key_and_view_is_reported_with_identical_pair_counts` | COMPLIANT (failed embeddings score 0 to keep pair sets identical) |
| GV6.1-6.2 | `test_gcb_v2_evaluate.py::{test_full_run_completes_with_every_artifact, test_outputs_stay_under_runs_graphcodebert, test_expected_sha256_mismatch_refuses_without_writing}`, `test_gcb_v2_cache.py::test_writes_are_atomic`; committed run | COMPLIANT |
| GV6.3 | `models/graphcodebert/README.md` Results (negative result, label-noise caveat, legacy not comparable) | COMPLIANT (structural readback) |
| TH1.1 | `test_calibration_experiment.py::{test_channel_a_calibration_fits_on_val_and_scores_test_once, test_graphcodebert_v2_raw_cosine_ranks_variant_above_unrelated[cls,mean]}`; circular test removed | COMPLIANT |
| TH1.2 | `test_lora_guard.py` (rewritten, 10 tests) | COMPLIANT |
| TH1.3 | `test_dfg_parser.py::TestV2*` (GD2-GD6 constructs) | COMPLIANT |
| NF1-NF3 | `git diff feat/fix-graphcodebert-dfg-input HEAD -- models/evaluation backend models/fusion.py scripts models/graphcodebert/{parser,contrastive_graphcodebert,fine_tune_graphcodebert}.py models/graphcodebert/adaptador-lora-20k models/char_cnn/best_model.pth` empty; `test_dfg_parser.py::test_legacy_parser_is_frozen` | COMPLIANT |
| NF4 | run `config.json` records transformers 5.14.0, tree-sitter 0.26.0 (+ c 0.24.2, cpp 0.23.4); scipy pre-existing | COMPLIANT |
| NF5 | Full suite 174 s incl. other channels and real-weights tests; GCB-only offline time not measured separately | PARTIAL (SHOULD; not measured in isolation) |
| NF6 | `test_gcb_v2_evaluate.py::test_rerun_hits_the_cache`; run cache hits 5708/11886 | COMPLIANT |

## Real-run checks (`runs/graphcodebert/20261011-082155`)

| Check | Observed | Result |
|---|---|---|
| status | `config.json` `status: complete`, `failure: null`, `dirty: false`, git_sha `69a19d8` | OK |
| manifest | `manifest_sha256 e835362d2e7a4153ef97204d4b30e769759a0f8f54f7db67b9e1fb2639e5238f` | OK |
| versions | transformers 5.14.0, tree-sitter 0.26.0, torch 2.13.0+cu126 (`config.gcb_v2` / `config.versions`) | OK |
| model revision | `2b0488a7bb0eefc7041f1bb2cad1ab26b0da269d` | OK |
| selection on val | `selection.json` `split: val`, `view: all`, 5,089 files, 1,595,275 pairs; v2 -> mean, v2_nodfg -> mean, legacy -> cls | OK |
| thresholds from val | `thresholds_val.json` `split: val` for all 5 methods; every `*__all` operating point `source: val_raw_score` | OK |
| test evaluated once | single run dir, `split: test`; enforced by `test_test_stage_requires_selection_and_runs_once` | OK |
| both views | 10 dirs `<method>__{all,no_identical}` with metrics.json/report.md/plots | OK |
| baselines | jaccard, winnowing, v2_nodfg, legacy present; legacy `variant: legacy_adapter`, `adapter_loaded: true` | OK |
| embedding failures | `data_summary.json` `failed: 0` for v2, v2_nodfg, legacy | OK |
| n_boot | 1000 in config and every `metrics.json.bootstrap` (unit assignment, seed 42) | OK |
| summary vs metrics | every method/view `summary.json` value equals `metrics.json.threshold_free` (diff < 1e-12) | OK |

## README consistency (`models/graphcodebert/README.md` Results)

All 30 headline numbers (ROC-AUC, PR-AUC, MAP@R with CI95, 5 methods x 2 views) match `summary.json`
at the printed precision, including borderline roundings (v2 all ROC upper 0.89253 -> 0.893;
winnowing no_identical PR lower 0.02053 -> 0.021). Operating points match `*__all/metrics.json`:
Jaccard recall 0.609 at FPR 3.62%, v2 recall 0.249 at FPR 3.32% with threshold 0.9979; 1% target
unachievable (Jaccard, winnowing) or recall <= 0.003 (v2, v2_nodfg, legacy). Data table, exclusions
(147/2,374), dropped 62,487, chance PR-AUC 0.00018, val pooling (0.00073 vs 0.00057), parse-error
25%, truncation 11%/3.6%, 4.7 windows all match `data_summary.json`/`selection.json`. No mismatch.

## Frozen / protected paths

- `models/evaluation/`, `backend/`, `models/fusion.py`, `scripts/`, `models/graphcodebert/{parser,contrastive_graphcodebert,fine_tune_graphcodebert}.py`, `adaptador-lora-20k/`, `models/char_cnn/best_model.pth`: no diff vs base.
- `legacy_inference.py` vs base `inference.py`: 19 insertions, 3 deletions. Beyond the new module docstring/header (and a dropped UTF-8 BOM), the class body changes are: class rename to `LegacyGraphCodeBERTInference`, `SHIPPED_ADAPTER` constant, `import dataclasses`, new `load_adapter: bool = False` parameter, shipped-adapter fallback when `load_adapter` and `adapter_path` is unset, and the adapter gate `if load_adapter and ...`. All other lines are identical. This is the documented single behavioural change (tasks 6.4, GE7.5 amendment), not a verbatim move. WARNING.
- Vendored files: sha256 of `parser/DFG.py`, `parser/utils.py`, `clonedetection/run.py`, `clonedetection/model.py`, `LICENSE` all equal the values in `tests/reference/graphcodebert/SOURCE.md` (commit `c0de43d3aaf38e89290f1efb771f8de845e7a489`).

## Tasks

All tasks ticked with evidence except:

- **8.4** (debug run on fixture and `--limit-assignments 3` with real model, `--n-boot 20`): unticked. Superseded in practice by the 8.2 real-weights wiring check and the complete WU10 run, but not recorded. WARNING.

## Documented deviations (accepted, with amendment reference)

- Windows 382/191/max 16 (design D7; GE5.1 text already aligned).
- `dfg_nodes_used` = distinct nodes placed in at least one window (GE7.4 as amended).
- Facade default `input_version="legacy"` with adapter OFF until SDD-4; v2 explicit (GE7.4/GE7.5 amendment, user decision 2026-10-11; `test_legacy_default_is_a_documented_deviation_until_sdd4`).
- GE1.2 budget rule `code_length + data_flow_length <= 512` with `code_length` including CLS/SEP (tasks 2.1).
- Walker deviations (f)-(i) and C-specific deviations (tasks 2.4, module docstring of `v2/dfg.py`).
- GE3.3 isolated node row all-False; GE1.3 upstream node budget; special ids from tokenizer (tasks 3.2).
- Pooling name `mean` for spec `mean_code` (tasks 5.2).
- Cache key without pooling; both poolings stored in the entry (tasks 7.2, design D9).
- MAP@R CI95 via assignment bootstrap (tasks 7.1, 8.2).
- Failed embeddings score 0 to keep identical pair sets (tasks 7.1, 8.2).
- PR2 slice had no Gentle AI review (tool defect); independent verifier PASS WITH FINDINGS, fixed in `55a34e3`.

## Deferred follow-ups (from tasks.md, not blocking)

- Runtime embedding failures (e.g. CUDA OOM) should not be cached as permanent failures.
- Legacy cache key should include an adapter content digest.
- Negative test for legacy `truncated=False` on a short single-window file.
- `best_model.pth` stashed during SDD-3; restore after SDD-3 (user action).

## Issues

CRITICAL: none.

WARNING:
1. Task 8.4 unticked (debug run not recorded; superseded by the full run).
2. `legacy_inference.py` is not a verbatim move modulo header: adds the `load_adapter` gate and shipped-adapter fallback (documented, required by GE7.1/GE7.5 amendment).
3. NF5 (offline GCB tests < 60 s) not measured in isolation; full suite 174 s including other channels and real-weights tests.

SUGGESTION:
1. Tick 8.4 with a pointer to the 8.2 wiring check and the WU10 run, or drop it explicitly.
2. Record an offline-only GCB test timing (`-m "not requires_graphcodebert"`) for NF5.
