# Verification Report

**Change**: fix-charcnn-implementation (SDD-2)
**Branch verified**: `feat/fix-charcnn-05-run` @ `8b2ba44` (chain base `feat/fix-charcnn-implementation` @ `31a9ed4`)
**Mode**: Standard (no strict-TDD flag supplied; RED/GREEN evidence is recorded per task in `tasks.md`)
**Date**: 2026-10-10
**Verifier**: read-only; no source, test, data, run or git state was modified.

## Verdict

**PASS WITH WARNINGS**

Every CP/CT/CI/NF requirement has passing runtime coverage or committed-artifact evidence. The one
failing test is the known, unrelated `test_graphcodebert_calibration`, and its test file is identical
to `main`. Two documented, stricter-than-spec deviations remain (CP10.2, CT9.2), plus the deferred
follow-ups. The CRITICAL list is empty.

## Completeness

| Metric | Value |
|---|---|
| Tasks total (1.1-9.7) | 30 |
| Tasks complete | 30 |
| Tasks incomplete | 0 |

No unticked checkbox. Each WU has RED -> GREEN evidence and its commit (16 commits `ac672a1..8b2ba44`).

## Build and Tests

`python -m pytest tests/ backend/tests/ -q -p no:cacheprovider -rs` (full suite, 145 s):

```text
1 failed, 716 passed, 2 skipped, 20 warnings
FAILED tests/test_calibration_experiment.py::test_graphcodebert_calibration
  AssertionError: QuickSort deberia tener muy baja similitud (<25%), dio: 0.3142
SKIPPED tests/test_char_cnn_robustness.py:52: Dataset de subproblemas no visto no esta presente en disco local (0 muestras encontradas).
SKIPPED tests/test_char_cnn_v2_inference.py:214: best_model.pth sha256 d3692747d276 differs from the golden capture 58f7007479de; real-weight golden cases only apply to that checkpoint
```

- The failure is pre-existing and outside this change. `git diff main HEAD -- tests/test_calibration_experiment.py`
  is empty, and it exercises GraphCodeBERT (Channel A), which this change does not touch.
- Skip 1 is pre-existing: the legacy robustness dataset is not on disk.
- Skip 2 is the expected hash-pinned legacy golden case. The committed `best_model.pth` blob (HEAD and
  base) is `58f70074...`, which is what the golden was captured against. The working copy is the user's
  uncommitted `d3692747...`, so the test skips by design.
- Targeted spot run (16 passed, 18.9 s): `-k` selection over twins-encode-identically,
  guard-raises-above-threshold, padding invariance, capped linspace windows, no BatchNorm,
  prepare_dataset DeprecationWarning, leaking-preprocessing abort, val-only calibration fit, fixture
  golden, real checkpoint loads as legacy (ran on the user's checkpoint, not skipped), promote refusal on
  a dirty target, two identical CPU runs, real checkpoint untouched.
- Coverage: not available (no coverage tooling configured).

## Requirement -> Evidence Matrix

Test file prefix `tests/test_char_cnn_v2_`. Status: COMPLIANT = covering test passed (or, for static
NF items, committed diff evidence); DEVIATION = documented reconciliation that differs from the spec
text.

### charcnn-preprocessing

| ID | Evidence | Status |
|---|---|---|
| CP1.1 order | `preprocess.py::test_newlines_controls_and_zero_width`, `test_comment_marker_removed_with_comment`; `preprocess_v2` = clean_controls -> fold -> strip_comments -> strip_course_markers -> canonical_whitespace (`v2/preprocess.py:146-151`) | COMPLIANT |
| CP1.2 PREPROC_VERSION=2 | `preprocess.py::test_versions_and_alphabet_layout`, `test_to_dict_records_versions_and_alphabet`; run `config.json` `preproc_version: 2` | COMPLIANT |
| CP1.3 idempotent | `preprocess.py::test_idempotent` | COMPLIANT |
| CP1.4 label-free | signature `preprocess_v2(text: str) -> str` (static); `shortcuts.py::test_audit_is_report_only_on_the_data_pass` | COMPLIANT |
| CP2.1 CR/C0/DEL/ZW | `preprocess.py::test_newlines_controls_and_zero_width`, `test_clean_controls_keeps_tab_and_lf`, `test_cr_only_file_is_not_one_comment` | COMPLIANT |
| CP3.1 folding | `preprocess.py::test_fold_unicode` | COMPLIANT |
| CP3.2 non-ASCII dropped, not UNK | `preprocess.py::test_non_ascii_is_dropped`, `test_non_ascii_never_reaches_unk_after_preprocessing` | COMPLIANT |
| CP4.1 delegate strip_comments | `preprocess.py::test_comments` (`1'000`, `'"'`, `"http://a"`); imports `models.evaluation.normalize.strip_comments`, no copy. The digit-separator shield (decimal + hex) wraps the call without changing it | COMPLIANT |
| CP5.1 leading headers | `preprocess.py::test_leading_header_lines_equal_body` (3 forms). Leading course-header line rule is a documented spec-driven addition | COMPLIANT |
| CP5.2 print-line removal + leftover tokens | `preprocess.py::test_header_print_line_removed_entirely`, `test_print_line_variants_removed`, `test_marker_tokens_removed_everywhere_else` (spec text matches the reconciliation) | COMPLIANT |
| CP5.3 identifiers preserved | `preprocess.py::test_identifiers_preserved` | COMPLIANT |
| CP6.1 line-preserving whitespace | `preprocess.py::test_whitespace_layout_is_removed`, `test_literal_spacing_is_preserved`, `test_empty_and_blank_inputs` | COMPLIANT |
| CP7.1 alphabet PAD/UNK | `preprocess.py::test_encode_layout`, `test_padding_is_distinct_from_real_chars`, `test_out_of_alphabet_chars_map_to_unk`, `test_empty_encodes_to_unk` | COMPLIANT |
| CP8.1 class symmetry | `preprocess.py::test_human_and_ai_twins_encode_identically` | COMPLIANT |
| CP9.1 leak patterns | `preprocess.py::test_leak_patterns_names`, `test_leak_hits`. `non_alphabet` (`[^\n\x20-\x7e]`) covers non-ASCII, CR, C0, DEL and tab in one pattern; `course_marker` includes `autotest` (D-B, detected only) | COMPLIANT |
| CP9.2 guard + trainer abort | `preprocess.py::test_guard_passes_on_clean_texts`, `test_guard_passes_at_threshold` (1/1000), `test_guard_raises_above_threshold` (2/1000); `train.py::test_leaking_preprocessing_aborts_before_any_checkpoint` (exit 2, no checkpoint), `test_clean_corpus_passes_with_zero_shares` | COMPLIANT |
| CP10.1 v1 frozen | `inference.py::TestLegacyGolden::test_v1_preprocess_and_encode_table`; legacy `preprocess.py` has zero diff vs base | COMPLIANT |
| CP10.2 version dispatch | `inference.py::test_absent_preproc_version_selects_v1`, `test_explicit_v1_versions_are_legacy`, `test_unsupported_versions_raise`, `test_checkpoint_versions`. A mixed pair (`arch` absent + `preproc_version: 2`) raises `ValueError` rather than selecting v2 (D14 fail-closed) | DEVIATION (documented) |

### charcnn-training

| ID | Evidence | Status |
|---|---|---|
| CT1.1 split_v1 manifest only | `data.py::test_views_are_manifest_representatives`, `test_non_representatives_are_never_read_by_representative_views`, `test_foreign_sample_is_rejected`; no `dataset_manifest`/`prepare_dataset` reference in `v2/{train,data,evaluate}.py` | COMPLIANT |
| CT1.2 labels, broken excluded | `data.py::test_labels_follow_source`, `test_broken_entries_are_excluded` | COMPLIANT |
| CT1.3 no split overlap | `data.py::test_splits_do_not_overlap` | COMPLIANT |
| CT2.1 seed before data/model | `train.py::test_seed_runs_before_data_and_model` (`seed_everything(seed, deterministic_torch=True)`, `v2/train.py:400`) | COMPLIANT |
| CT2.2 1:1 keyed resampling | `data.py::test_balanced_epoch_uses_all_ai_and_equal_humans`, `test_epoch_is_reproducible_and_varies`, `test_human_draw_uses_keyed_rng`, `test_fewer_humans_than_ai_uses_all_and_records_shortfall`; real run `sampling.human_shortfall: 0` | COMPLIANT |
| CT2.3 seeded crop, no dummy pass | `data.py::test_crops_are_bounded_and_keyed`; `model.py::test_random_crop_is_deterministic_per_key`; `train.py::test_no_forward_before_the_first_real_batch`, `test_crops_use_the_run_config_window` | COMPLIANT |
| CT3.1 selection rule | `train.py::test_fit_selects_epoch_2_from_stubbed_val_metrics`, `test_fit_ties_keep_the_earlier_epoch`, `test_fit_skips_null_auc_epochs`, `test_selection_tuple_prefers_auc_then_pr_then_earlier_epoch` | COMPLIANT |
| CT3.2 Platt on val only | `train.py::test_calibration_is_fitted_on_val_ids_only`; real `calibration.json` `fit_set.split: "val"`, n=3077 (2868/209) | COMPLIANT |
| CT3.3 test once after calibration | `train.py::test_test_is_scored_once_after_calibration`, `test_main_invokes_evaluate_run_once` | COMPLIANT |
| CT4.1 reproducibility | `train.py::test_two_cpu_runs_are_identical` (history, selection, metrics, test_all, calibration, shortcuts, tensors) | COMPLIANT |
| CT5.1 writes only under runs/ | `train.py::test_writes_only_under_the_runs_root_and_never_promotes`, `test_real_checkpoint_is_untouched` | COMPLIANT |
| CT5.2 config.json keys | `train.py::test_config_json_records_provenance`; real config has arch/preproc 2, alphabet, conv sizes, dropout, seed 42, epochs, lr, manifest sha, git sha | COMPLIANT |
| CT5.3 run artifacts | `train.py::test_run_has_every_artifact`; real run dir has config, best.pth, history.csv, calibration, metrics (+per_group), test_all/, shortcuts (weights/CSVs local only, by design 9.5) | COMPLIANT |
| CT5.4 checkpoint embeds config | `train.py::test_best_checkpoint_is_weights_only_and_self_describing` | COMPLIANT |
| CT6.1 metrics via models.evaluation | `train.py::test_ci_is_bootstrapped_by_dup_group`, `test_operating_points_come_from_val_calibration`; real metrics `views: [observed, balanced]`, `bootstrap.unit: dup_group` | COMPLIANT |
| CT6.2 per-group, low support, n=0 | `train.py::test_per_group_breakdowns`, `test_small_group_is_low_support_and_absent_group_is_empty`, `test_per_generator_compares_each_group_with_all_humans` (model/profile live in `per_generator`) | COMPLIANT |
| CT6.3 headline + secondary | `train.py::test_headline_and_secondary_views`; real `n` 4531 (headline) / 9649 (`test_all`), both labelled | COMPLIANT |
| CT7.1 shortcuts.json | `shortcuts.py::test_pattern_keys_cover_ct7`, `test_using_namespace_only_in_human_files`, `test_every_key_for_both_classes_raw_and_normalized`, `test_length_buckets`, `test_audit_is_report_only_on_the_data_pass` | COMPLIANT |
| CT8.1 legacy baseline | `baseline.py::test_config_is_labelled_contaminated_and_manual`, `test_headline_and_secondary_views`, `test_scores_come_from_the_legacy_facade`, `test_report_states_the_contamination`, `test_checkpoint_is_read_only` | COMPLIANT |
| CT9.1 promote copy + provenance | `promote.py::test_force_copies_a_dirty_target_and_records_provenance`, `test_clean_target_is_copied_without_force`, `test_dry_run_writes_nothing` | COMPLIANT |
| CT9.2 refusals | `promote.py::test_modified_or_untracked_target_is_refused`, `test_unversioned_source_is_refused`, `test_git_failure_is_refused`. Stricter than spec: also requires run `status: complete`, binding to the run's `best.pth` + `best_sha256`, a staged sidecar and rollback | DEVIATION (documented, stricter) |
| CT9.3 never invoked | `train.py::test_writes_only_under_the_runs_root_and_never_promotes` (spy); no `best_model.provenance.json` exists in `models/char_cnn/` | COMPLIANT |
| CT10.1 deprecation and cleanup | `cleanup.py::test_poc_trainer_is_removed`, `test_deprecated_dataset_files_remain_and_are_marked`, `test_importing_prepare_dataset_warns` | COMPLIANT |

### charcnn-inference

| ID | Evidence | Status |
|---|---|---|
| CI1.1 arch v2 | `model.py::test_has_no_batchnorm`, `test_single_dropout`, `test_masked_pool_ignores_pad_values`, `test_batch_of_one_in_train_mode` | COMPLIANT |
| CI1.2 v1 available | `model.py::test_v1_model_matches_frozen_state_dict_fixture` (strict load vs 38-key shape fixture) | COMPLIANT |
| CI2.1 padding invariance | `model.py::test_padding_invariance` (0/100/3000 PAD), `test_batch_matches_single` | COMPLIANT |
| CI3.1 windows | `model.py::test_window_starts_regular` (4096->1, 6144->2, 6145->3), `test_window_starts_capped_linspace` (100000->8), `test_every_window_ends_inside_input`, `test_score_is_softmax_of_mean_window_logits` | COMPLIANT |
| CI3.2 deterministic | `model.py::test_window_starts_*` (pure function), `test_score_matches_direct_forward_and_restores_mode` | COMPLIANT |
| CI4.1 result contract | `inference.py::TestV2Contract::test_normal_input_contract`, `TestLegacyContract::test_legacy_checkpoint_adds_new_keys` (JSON-serializable floats) | COMPLIANT |
| CI4.2 score == ai_probability | same tests (`score == ai_probability`) | COMPLIANT |
| CI5.1 abstention | `inference.py::test_short_input_abstains`, `test_abstention_placeholders_equal_the_legacy_path_values`, `test_legacy_abstention_keeps_placeholders` | COMPLIANT |
| CI6.1 checkpoint config rebuild | `inference.py::test_rebuilds_model_from_checkpoint_config` (non-default conv sizes, 1e-6), `test_config_argument_is_ignored_with_warning` | COMPLIANT |
| CI7.1 legacy loading | `inference.py::TestLegacyGolden::test_fixture_checkpoint_matches_golden` (1e-6), `TestLegacyContract::test_real_checkpoint_loads_as_legacy` ([legacy-compat], ran on the user's checkpoint) | COMPLIANT |
| CI8.1 consumers unchanged | `real_engine.py` not in the change diff and reads only `prob_sintetico`/`ai_probability` (`real_engine.py:76-79`); `tests/test_char_cnn_{guard,canonical,robustness}.py` and `backend/tests/` pass unmodified | COMPLIANT |

### Non-functional

| ID | Evidence | Status |
|---|---|---|
| NF1 models/evaluation unchanged | `git diff --stat feat/fix-charcnn-implementation HEAD -- models/evaluation` is empty | COMPLIANT |
| NF2 float contract | `assert_contract` in `inference.py` tests (`type(...) is float`, [0,1], `json.dumps`) | COMPLIANT |
| NF3 best_model.pth byte-identical | committed blob `58f70074...` identical at base and HEAD (not in the diff); working copy `d3692747...` unchanged before/after the baseline run (legacy `config.json` before == after) and before/after this verification | COMPLIANT |
| NF4 no new deps | no requirements/dependency file in the change diff | COMPLIANT |

**Totals (56 IDs):** 54 COMPLIANT, 0 PARTIAL, 0 MISSING, 2 DEVIATION (both documented).

## Real-Run Artifact Checks

v2 run `runs/char_cnn/20261011-015734/` (committed: config, calibration, leak_guard, metrics, report,
shortcuts, plots, test_all/):

| Check | Observed | Result |
|---|---|---|
| `status` | `complete`, `failure: null` | OK |
| versions | `arch_version: 2`, `preproc_version: 2` | OK |
| seed | 42 (top level and hyperparams) | OK |
| `manifest_sha256` | `e835362d2e7a4153ef97204d4b30e769759a0f8f54f7db67b9e1fb2639e5238f` | OK |
| `best_sha256` | `ec365f98...6672bd6` present | OK |
| calibration fit set | `fit_set.split: "val"`, n 3077 (neg 2868 / pos 209), Platt, same manifest sha | OK |
| leak guard | `passed: true`, threshold 0.001; human shares course_marker 5.63e-5, non_alphabet 0.0 (both < 0.001); 17,757 human texts | OK |
| metrics views | `views: [observed, balanced]`; ROC/PR/ECE with `ci95`, 1000 boots, unit `dup_group` | OK |
| headline/secondary | `test` n 4531 (330 AI) "headline: test representatives"; `test_all` n 9649 (331 AI) "secondary: all non-broken test files" | OK |
| per-generator | `per_generator.{model,profile}`; `low_support` flags (only deepseek-chat 227 and qwen3 100 are supported) | OK |
| shortcuts.json | per class, raw + normalized, all CT7 keys, length buckets, `note: report-only` | OK |
| selection | epoch 30 of 38, val ROC 0.99905 / PR 0.98895, early stop | OK |

Legacy baseline `runs/char_cnn_legacy/20261011-033124/`: `contaminated: true` with the overlap and
preprocessing note (config, metrics and test_all/metrics, plus `warnings`); `arch_version`/
`preproc_version` 1; `checkpoint_sha256_before == checkpoint_sha256_after == d3692747...`;
`status: complete`; operating point `argmax_0.5` with `source: "manual"`. OK.

## Legacy Compatibility

| Check | Result |
|---|---|
| `inference.py` dispatches unversioned checkpoints through the frozen path; fixture golden passes at 1e-6 | OK |
| `models/char_cnn/{preprocess,model,dataset,config}.py` diff vs `feat/fix-charcnn-implementation` | empty, OK |
| `models/evaluation` diff vs base | empty, OK |
| `real_engine.py` unchanged and consumes legacy keys (`prob_sintetico`, then `ai_probability`) | OK |
| The real checkpoint loads as legacy with arch/preproc/n_windows = 1/1/1 | OK (runtime) |

## NF and Safety

- Trainer writes only under the runs root (test above); docstring and code never reference `best_model.pth`.
- Tracked changes under `models/` vs base: only `README.md`, `inference.py`, `prepare_dataset.py`,
  `train.py` and the new `v2/` package. No weights. `best_model.pth` is unchanged in git, and the working
  copy is still the user's version.
- `data/train_charcnn.py` deleted (`D` in the diff, absent on disk).
- `prepare_dataset` import emits `DeprecationWarning` (test passed); `dataset_manifest.json` kept.
- Promote never run against the repo: no `*provenance*` file in `models/char_cnn/`.
- Final working-copy check: `models/char_cnn/best_model.pth` sha256 = `d3692747d2767b56806964ba2a23e686aa5e8515994d449f6b5e3afb18cb19e7` (unchanged); `git status` shows only ` M models/char_cnn/best_model.pth` (plus this report).

## README Results Consistency (`models/char_cnn/README.md` lines 145-203)

Every number was checked against the committed JSON:

| README value | Source value | Match |
|---|---|---|
| Leak guard 0.0056% course marker, 0% non-alphabet | 5.63e-5, 0.0 | yes |
| Epoch 30 of 38, val ROC 0.9991 / PR 0.9890 | 30/38, 0.99905 / 0.98895 | yes |
| Val 2,868 human / 209 AI | calibration fit_set | yes |
| Headline 4,531 (330): ROC 0.994 [0.991, 0.996], PR 0.958 [0.944, 0.973], ECE 0.009 | 0.99371 [0.99091, 0.99645], 0.95806 [0.94369, 0.97263], 0.00878 | yes |
| All files 9,649 (331): ROC 0.993 [0.990, 0.997], PR 0.938 [0.919, 0.959], ECE 0.004 | 0.99339 [0.98971, 0.99654], 0.93817 [0.91936, 0.95881], 0.00432 | yes |
| Headline @1%: FPR 0.95% [0.69, 1.28], recall 0.888 [0.858, 0.922], precision 0.880 [0.840, 0.912] | 0.952% [0.688, 1.281], 0.8879 [0.8579, 0.9217], 0.8799 [0.8399, 0.9120] | yes |
| Headline @5%: FPR 4.57% [3.97, 5.18], recall 0.973 [0.956, 0.989], precision 0.626 [0.583, 0.669] | 4.570% [3.971, 5.179], 0.9727 [0.9559, 0.9886], 0.6257 [0.5830, 0.6693] | yes |
| All files @1%: FPR 0.93% [0.61, 1.30], recall 0.888, precision 0.772 | 0.934% [0.615, 1.300], 0.8882, 0.7717 | yes |
| All files @5%: FPR 9.28% [4.14, 14.58], recall 0.973, precision 0.271 | 9.283% [4.142, 14.581], 0.9728, 0.2713 | yes |
| Prevalence 7.3% / 3.4% | 0.0728 / 0.0343 | yes |
| deepseek-chat n=227 ROC 0.992 recall@1% 0.88; qwen3 n=100 ROC 0.997 recall@1% 0.90 | 0.9920 / 0.8811; 0.9974 / 0.90 | yes |
| Shortcuts: std:: 46% vs 24%; using namespace 7% vs 30%; 1-2 KB 42% vs 24%; >=4 KB 3% vs 13.5% | 0.4604/0.2364; 0.0702/0.30; 0.4242/0.2426; 0.0333/0.1354 | yes |
| 99% of AI test files from two generators | 327/330 = 99.1% | yes |
| Legacy: ROC 0.999 [0.998, 1.000], PR 0.993, recall 0.967 at FPR 0.26% | 0.99894 [0.99765, 0.99974], 0.99258, 0.9667 at 0.262% | yes |

No discrepancies.

## Design Coherence

| Decision | Followed | Notes |
|---|---|---|
| D1 frozen legacy files | yes | zero diff |
| D2 `load_manifest(...).samples(representatives_only=True)` | yes | |
| D5 alphabet 96 + PAD 0/UNK 1, vocab 98, uint8 | yes | |
| D6 channel LayerNorm, no BatchNorm | yes | |
| D8 one windowed scoring path (linspace beyond cap) | yes | under the cap the last start aligns to `n - window` (all windows full length) |
| D10 AUC tuple selection, ReduceLROnPlateau(max), no AMP | yes | |
| D11 fit vs evaluate_run separation | yes | |
| D12 RunContext, config rewrite with calibration ref | yes | |
| D14 primitives-only checkpoint, weights_only=True, fail-closed versions | yes, with deviation | legacy-only `weights_only=False` fallback with `UserWarning` (documented) |
| D15 abstention keeps legacy placeholders | yes | |
| D16 every file scored, `n_abstained` reported | yes | |

## Deviations (documented, accepted)

1. CP10.2 / D14: mixed version pairs (for example `arch_version` absent + `preproc_version: 2`) raise `ValueError` instead of selecting v2. This fails closed.
2. CT9.2: promote is stricter than spec. It also requires run `status: complete`, binds the source to the run's `best.pth` + `best_sha256`, stages the sidecar and rolls back on failure. Exit-code table in `models/char_cnn/v2/runs.py`.
3. Legacy-only `weights_only=False` fallback (v2 checkpoints must be `weights_only`).
4. Design-vs-spec reconciliations where the spec wins and the implementation matches the spec: CP5.2 whole print-line removal, CP6.1 line-preserving whitespace, CI3.1 linspace windows, leading course-header rule, digit-separator shield (decimal + hex), DeprecationWarning on import.

## Deferred Follow-ups (not failures; none violates a MUST)

From `tasks.md` WU8/WU9:
- Duplicated per-view metrics loop in `v2/baseline.py` and `v2/evaluate.py`.
- Baseline v2-refusal goes through the legacy facade, which creates `models/char_cnn/{weights,logs}` relative to cwd. Both directories are gitignored (`.gitignore:36-37`) and exist locally.
- Review items (a)-(h) on 42172d7: TOFU `best_sha256` for old runs, hard-killed re-evaluation left `running`, disk-full during restore, exit 4 semantics, staged-sidecar exit code, unreachable `!!` branch, untested restore-failure paths, duplicated sidecar JSON writer.

## Issues

**CRITICAL**: None.

**WARNING**:
1. Full suite exits non-zero because of the pre-existing `test_graphcodebert_calibration` failure (Channel A, file unchanged vs `main`). It is not caused by this change, but the suite is not green.
2. The hash-pinned real-weight golden (`test_real_checkpoint_matches_golden`) cannot run while the user's uncommitted `best_model.pth` (`d3692747...`) replaces the committed one (`58f70074...`). Byte-level equality against real weights was therefore not re-verified in this pass. The fixture golden (1e-6) and the real-checkpoint legacy-load test did run and pass.
3. The baseline run writes `models/char_cnn/{weights,logs}` (gitignored) through the frozen legacy config. This is deferred, but it is a write under `models/` outside `runs/`. CT5.1 applies to the trainer only, so this is not a spec violation.
4. Run `config.json` records `dirty: true` and absolute local paths. This is disclosed in the README.

**SUGGESTION**:
1. On `test_all`, 1,333 of 9,318 human files (14%) are below the 60 non-whitespace-character abstention threshold but are still scored (D16). This likely explains the 9.28% FPR at the 5% threshold. Before SDD-4, add an abstention-filtered view.
2. Once the user decides the fate of the local checkpoint, re-run `test_real_checkpoint_matches_golden` against the committed blob (for example in a clean worktree).
