# Tasks: Fix GraphCodeBERT DFG Input (fix-graphcodebert-dfg-input)

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated authored changed lines | ~3,500 (code ~1,500 + tests ~1,700 + docs ~300); vendored upstream files, run artifacts and golden data not counted |
| 400-line budget risk | High in total; per work unit WU2/WU7/WU8 ~450-550, others 150-400 (advisory only) |
| Chained PRs recommended | Yes |
| Suggested split | PR1 = WU1-2 -> PR2 = WU3-4 -> PR3 = WU5-6 -> PR4 = WU7-8 -> PR5 = WU9-10 (docs + real run + artifacts) |
| Delivery strategy | ask-on-risk (default; not supplied) |
| Chain strategy | feature-branch-chain (PR1 base = `feat/fix-graphcodebert-dfg-input`; PR N base = PR N-1 branch) |

Decision needed before apply: Yes (D-A, D-B below, both only for WU10; none blocks WU1-9)
Chained PRs recommended: Yes
Chain strategy: feature-branch-chain
400-line budget risk: High

Push, PR creation and merge stay user decisions. Each WU = one Conventional Commit (English) with tests and docs; ~400 lines is advisory. Behavior tasks are RED (test fails) first, then GREEN. Runner: `python -m pytest tests/ backend/tests/ -q -p no:cacheprovider`; focused: `python -m pytest tests/test_gcb_<x>.py -q -p no:cacheprovider`. Fixtures are synthetic C/C++ snippets, `tmp_path`, `tests/eval_factory.py` (`make_tree`, `build_split`, `write_manifest`), a fake deterministic tokenizer and a tiny random `RobertaConfig` (CPU, eager). Golden/mask/encode tests run offline with no weights; only `requires_graphcodebert` tests need the HF cache (`microsoft/graphcodebert-base`).

Hard constraints for every task: `models/char_cnn/best_model.pth` (user's uncommitted change) is never touched, staged or committed (stage by explicit path, never `git add -A`). No diff under `models/evaluation/` (NF1), `backend/` (NF2), `models/fusion.py`, `scripts/`. Frozen files with zero edits: `models/graphcodebert/{parser,contrastive_graphcodebert,fine_tune_graphcodebert}.py`, `adaptador-lora-20k/` (NF3). No new runtime dependency (NF4). Known pre-existing failure `tests/test_calibration_experiment.py::test_graphcodebert_calibration` is removed/replaced in WU8 (TH1.1); afterwards the full suite must have no failures.

Decisions already taken (do not reopen): facade default `input_version="legacy"` with adapter off until SDD-4 (user, 2026-10-11); v2 is selected explicitly by the evaluation CLI and tests. This overrides spec GE7.4/GE7.5 wording "`input_version` MUST be 2 / legacy not default": the v2 contract holds when `input_version="v2"` is requested; the legacy default is a documented, tested deviation (task 6.5). Windows are 382/191/max 16 and `dfg_nodes_used` = distinct nodes placed (design wins).

### Work Units and Dependencies

| WU | Commit | Depends on | Parallel with |
|----|--------|-----------|---------------|
| 1 | `test(gcb): vendor upstream GraphCodeBERT reference` | none | none (first) |
| 2 | `feat(gcb): v2 C/C++ DFG walker` | 1 | 3.1-3.2 (test-only prep) |
| 3 | `feat(gcb): v2 feature builder and attention mask` | 1, 2.1 (config) | WU2.2+ |
| 4 | `feat(gcb): v2 encoder forward` | 3 | none |
| 5 | `feat(gcb): sliding windows, pooling and embed pipeline` | 2, 3, 4 | none |
| 6 | `refactor(gcb): freeze legacy path, facade dispatch, drop adapter default` | 5 | WU7 |
| 7 | `feat(gcb): embedding cache, pair scoring and lexical baselines` | 5 (6 for the legacy baseline wiring in 7.5) | WU6 |
| 8 | `feat(gcb): zero-shot evaluation CLI` | 6, 7 | none |
| 9 | `docs(gcb): README v2 section and deprecations` | 6, 8 (CLI flags) | none |
| 10 | `data(gcb): zero-shot v2 run artifacts` + `docs(gcb): results` | all | none |

Solo-writer rule: single writer throughout; "parallel" means order-independent, not concurrent.

## WU1 - Vendored reference (GD1, TH1.3 prerequisite)

- [x] 1.1 Download upstream microsoft/CodeBERT GraphCodeBERT `parser/DFG.py` (+ `parser/utils.py` if imported), `clonedetection/run.py`, `clonedetection/model.py` at one pinned commit into `tests/reference/graphcodebert/{parser,clonedetection}/`; add MIT `LICENSE` and `SOURCE.md` (URL, 40-hex commit, retrieval date, "read-only, never imported as tests"). Files byte-identical to upstream. Record in SOURCE.md the `run.py` truncation constant `k` (closes design open question 2). Files: `tests/reference/graphcodebert/**`.
  - Evidence: pinned `c0de43d3aaf38e89290f1efb771f8de845e7a489` (master head, 2023-07-09), sha256 per file recorded in `SOURCE.md`, `.gitattributes` `* -text` keeps bytes identical under `core.autocrlf=true`; `k = 3`. Deviation: `clonedetection/model.py` not vendored (network authorization covered DFG.py/utils.py/run.py/LICENSE only); add it before WU4.
- [x] 1.2 RED then GREEN: `tests/test_gcb_reference.py` fails when a reference file is missing, when LICENSE is missing, or `SOURCE.md` lacks a 40-hex commit (GD1.1); pytest must not collect the vendored files (check `pytest.ini`/`conftest` ignore; adjust only if needed). 
  - Evidence: lives in `tests/test_gcb_reference_parity.py` (allowed edit surface). RED: collection error, `harness.py` missing; GREEN: 17 passed. Negative cases use a `tmp_path` copy (missing file, edited file, commit removed). Default `python_files` already skips the vendored names; no pytest config change.
- [x] 1.3 `tests/gcb_reference.py` helpers (no test logic): `JavaView` node proxy (type/field renaming per design D2), AST-extract `convert_examples_to_features` and `TextDataset.__getitem__` from `run.py` into an injected namespace (stub `extract_dataflow`, tokenizer, args), loader for vendored `DFG_java`/`tree_to_token_index`. Smoke test: helpers import and extracted functions run on a fake tokenizer.
  - Evidence: helpers live in `tests/reference/graphcodebert/harness.py` (allowed edit surface; local file listed in `SOURCE.md`), loaded by path. Also provides `upstream_dataflow`/`upstream_raw_dfg` (real `extract_dataflow` with a C/C++ parser returning `JavaView`). Smoke tests pass with a char-level fake tokenizer.
- Forecast: ~150 authored lines (vendored files excluded). Commit `test(gcb): vendor upstream GraphCodeBERT reference`.
- Done: commit `228332a`. Route: delegated direct (single writer, PR slice 1).

## WU2 - v2 DFG walker (GD1.2-GD6, D2-D4)

- [x] 2.1 `models/graphcodebert/v2/{__init__,config}.py`: frozen side-effect-free `GCBV2Config` with `to_dict()` (code_length 384, data_flow_length 128, max_windows 16, pooling, use_dfg, attn_implementation, dtype), `INPUT_VERSION="v2"`; reject `code+dfg+3 > 512` (GE1.2). Test config validation. (GE1.2)
  - Evidence: tests in `tests/test_gcb_v2_dfg.py` (allowed surface; RED = `ModuleNotFoundError models.graphcodebert.v2`, GREEN = pass). Deviation: the literal `code+dfg+3 > 512` rule would reject the design default 384+128; implemented as `code_length + data_flow_length > 512` with `code_length` counting CLS/SEP as upstream `args.code_length` (450+128 still rejected). `window_code_tokens`=382 and `window_stride`=191 are derived properties; `pooling` in {cls, mean}, `attn_implementation` {eager}, `dtype` {float32}.
- [x] 2.2 RED: `tests/test_gcb_dfg_golden.py`, ~15 shared-construct snippets (decl with/without init, assignment, compound, update, if/else incl. braceless, `for` with decl init, while, range-for to enhanced_for, return, call): vendored `DFG_java(JavaView(root))` == v2 walker exact tuples, raw and post-filter; token parity vs vendored `tree_to_token_index`. (GD1.2, D2, D3)
  - Evidence: lives in `tests/test_gcb_reference_parity.py` (allowed surface), 18 snippets (15 C, 3 C++) x {tokens, raw `DFG_java`, upstream `extract_dataflow` post-filter} + a divergence guard. JavaView approach feasible, no fallback needed. Parent code lists compared as sets (upstream uses `list(set())`); idx lists exact. Compound assignment excluded from parity (design D3 list; spec GD3.3 requires the LHS read, unit-tested instead).
- [x] 2.3 RED: v2 unit cases appended to `tests/test_dfg_parser.py` (legacy classes untouched, frozen guard): `int b=a;`, last-def (`a=1;a=2;int c=a;`), call args, `a[i]++`/`s.n++`, braceless if/else union, loop dedup (no repeated `(code,idx,rel,parent_idxs)`), range-for, do, switch, pointer/reference declarators, pointer-return params, struct/enum tokens, field write, function scope reset, array declarator (`a[10]` does not define `10`), comments absent, MISSING skipped, non-ASCII byte offsets, parse-error keeps DFG and `parse_errors=True`, determinism and sort by idx, equal-length parent lists. (GD2-GD6, D4)
  - Evidence: RED = collection error (no v2 module). Frozen guard = sha256 of LF-normalised `parser.py`. Also covers compound assignment (GD3.3), casts/unary/subscript reads (GD3.4), `for` expression initializer (D4c), switch default.
- [x] 2.4 GREEN: `models/graphcodebert/v2/dfg.py` (`WALKER_VERSION="c-cpp-2"`, `extract_dfg_v2(code, lang)` -> `Dataflow(code_tokens, dfg, parse_errors, dfg_error, n_nodes_raw)`; strip_comments via `models.evaluation.normalize`; table in design). Verify tree-sitter-c/cpp node names (`else_clause`, `condition_clause`) hold for both languages (closes design open question 3); fix walker or record deviations. Recursion limit scoped; failure gives `dfg=[]` + `dfg_error`.
  - Evidence: `python -m pytest tests/test_gcb_v2_dfg.py tests/test_gcb_reference_parity.py tests/test_dfg_parser.py` -> 171 passed; full suite -> 846 passed, 2 skipped, 1 failed (known `test_graphcodebert_calibration`). Node names (tree-sitter-c 0.24.2 / cpp 0.23.4): `else_clause` in both; condition is `parenthesized_expression` in C and `condition_clause` in C++ (both walked by the default rule, no special case). Deviations beyond design D4 (documented in the module docstring): (f) `else_clause` unions branch states only (upstream also keeps pre-if states); (g) compound assignment reads the LHS previous definitions (spec GD3.3; design table said no self-link); (h) `primitive_type` leaves are keywords; (i) parent codes aligned 1:1 with parent idxs (GD2.1). Token indexing is iterative; `Dataflow.nodes` aliases `dfg` (spec naming).
- Forecast: ~550 lines (code ~250, tests ~300; slightly over advisory, single coherent unit). Commit `feat(gcb): v2 C/C++ DFG walker`.
- [x] 2.5 Follow-up (PR1 review): no process-wide recursion limit change. Walker-local guard: iterative `tree_depth` pre-check against `MAX_DEPTH=256` (per-call `max_depth`) gives `dfg=[]`, `dfg_error="max_depth"`; tree-sitter parsers are per thread (`threading.local`).
  - Evidence: RED = collection error (`MAX_DEPTH` missing); GREEN = `tests/test_gcb_v2_dfg.py tests/test_dfg_parser.py tests/test_gcb_reference_parity.py` 176 passed (depth 266/5000 -> `max_depth`, `sys.setrecursionlimit` never called, 2 threads x 20 rounds identical). Depth sample of 4000 dataset files: median 16, p99.9 67, max 129. Route: delegated direct (PR slice 2 writer).

## WU3 - Feature builder and mask (GE1-GE3)

- [x] 3.1 RED: `tests/test_gcb_encode.py`: `ori2cur_pos` contiguity (token split in three), budget truncation (400 subtokens -> 384 rule, `truncated`), 450+128 config rejection, positions (nodes 0, pad 1, code from 2; node position independent of target token, GE2.2), mask rules (padding rows/cols False, isolated node self-attends only as upstream behaves; document). Golden: extracted `run.py` features vs `encode` on same `(tokens, dfg)`: ids, positions, `dfg_to_code`, `dfg_to_dfg`, mask elementwise equal, with the fake tokenizer (always) and the real tokenizer (`requires_graphcodebert`). (GE1.1-GE3.3, GE2.1)
  - Evidence: lives in `tests/test_gcb_v2_encode.py` (allowed surface). RED = collection error (`models.graphcodebert.v2.encode` absent). Golden: 5 real-DFG C/C++ snippets + 7 synthetic budget cases + no-DFG case (fake tokenizer), 5 snippets + a truncation case (real tokenizer, ran, not skipped).
- [x] 3.2 GREEN: `models/graphcodebert/v2/encode.py` mirroring vendored `convert_examples_to_features` and `__getitem__` statement for statement, using the pinned constant `k` from SOURCE.md. Note: GE3.3 "node with no aligned token and no parent attends itself" - assert actual upstream behavior in the golden and record any gap as a documented deviation.
  - Evidence: 32 passed. API: `subtokenize`, `code_budget`, `build_features`, `build_attention_mask`, `encode(code_tokens, dfg, tokenizer, config) -> EncodedInput` (`attn_mask` [L,L] bool, `truncated`, counts). Deviations kept as upstream (documented in the module): GE3.3 isolated node row is all-False (no self-attention); GE1.3 nodes of cut code are kept; node budget is `L+D-len(source)`, so short files may carry more than D nodes. Special ids = tokenizer CLS/SEP ids (upstream hard-codes RoBERTa `[0,2]`).
- Forecast: ~350 lines. Commit `feat(gcb): v2 feature builder and attention mask`.

## WU4 - Encoder forward (GE4, D5, D6)

- [x] 4.1 RED: `tests/test_gcb_model.py` (offline, tiny random `RobertaConfig`, 2 layers, eager): mask honoured - perturbing an unreachable position's embedding leaves the protected output unchanged (<=1e-6) and a full-mask control changes it; node embedding = mean of aligned word embeddings (`+1e-10` rule); 3D==4D outputs when 3D is accepted; eval-mode determinism; upstream `model.py` forward (wrapper, `.roberta`) == `v2.model` hidden states (golden); raises if the mask cannot be honoured (GE4.4). (GE4.1-GE4.4)
  - Evidence: lives in `tests/test_gcb_v2_model.py` (allowed surface). RED = collection error (`models.graphcodebert.v2.model` absent). Upstream `clonedetection/model.py` vendored (sha256 `a03b0d6e...e63fe`, in `SOURCE.md` and the harness integrity check). transformers 5.14 raises `RuntimeError` on a 3D mask (no silent attend-all) and adds a 4D bool mask as 0/1, so 3D==4D is asserted only if 3D is accepted; golden wraps `.roberta` with the transformers 4.x 3D->4D additive conversion.
- [x] 4.2 GREEN: `models/graphcodebert/v2/model.py`: bool 3D -> 4D additive mask (0/`finfo.min`), `RobertaModel(..., attn_implementation="eager")` with `inputs_embeds`, `position_ids`, zero `token_type_ids`; fp32, `eval()`, `no_grad`, batched windows. fp16 explicitly out of scope (D6).
  - Evidence: 17 passed (incl. real weights, offline): block-mask and padding perturbation leave protected outputs unchanged (<=1e-6), full-mask controls change; upstream forward == v2 hidden states (<=1e-6); token-type embedding verified via embeddings hook. API: `additive_mask`, `node_input_embeddings`, `encoder_forward`, `forward_hidden`, `check_mask_honoured`, `batch_tensors`, `GraphCodeBERTV2Encoder(roberta, device, batch_size, verify_mask).encode(inputs) -> [N,L,H]`, `.from_pretrained(local_files_only=...)`. Non-eager or a failing mask probe raises `MaskNotHonouredError` (GE4.4). WU5+ unblocked.
- Forecast: ~300 lines. Commit `feat(gcb): v2 encoder forward`.

## WU5 - Windows, pooling, embed pipeline (GE5, GE6, D7-D9)

- [x] 5.1 RED: `tests/test_gcb_windows.py`: fits-budget file gives exactly one upstream-parity input; 1000 subtokens with 382/191 give starts 0,191,382,573,618 and 5 windows; 100 subtokens give 1 window; cap 16 sets `truncated` with evenly spaced starts and last window at file end; node restriction (fully inside window, first D by idx), parent reindex, span shift `-start+1`; node at token 600 appears only in containing windows; `dfg_nodes_used` counts distinct nodes; ablation (`use_dfg=False`) shares window starts (D8). (GE5.1-GE5.5)
  - Evidence: lives in `tests/test_gcb_v2_windows.py` (allowed surface). RED = collection error (`models.graphcodebert.v2.windows` absent). Also covers: exact-budget boundary, first window of a long file == upstream `encode` of the same slice, per-window node budget sets `truncated`, ablation on a fitting file keeps the same code, empty input.
- [x] 5.2 RED: pooling tests: `cls` vs `mean_code` (mean over code positions only: excludes CLS/SEP/nodes/pad) from one forward pass, differ, pooling echoed (GE6); file embedding = unweighted mean of window poolings, same shape for short and long files.
  - Evidence: lives in `tests/test_gcb_v2_embed.py`. RED = collection error (`models.graphcodebert.v2.embed` absent). One-forward check spies `encoder.encode` (1 call per file, N windows). Pooling name stays `mean` (`GCBV2Config.POOLINGS`), i.e. the spec's `mean_code`.
- [x] 5.3 GREEN: `v2/windows.py` (`plan_windows`), `v2/embed.py` (`GraphCodeBERTV2Embedder`: load tokenizer/model with `local_files_only` option, record HF snapshot revision, returns `cls`, `mean`, `n_windows`, `truncated`, `dfg_nodes_used`, `dfg_node_count`, `code_tokens_count`, `parse_errors`; empty input -> failure result without exception).
  - Evidence: `python -m pytest tests/test_gcb_v2_windows.py tests/test_gcb_v2_embed.py` -> 33 passed (real-weights smoke ran offline on CPU, 1.3 s incl. load). API: `window_starts(n, window, stride, max_windows) -> (starts, capped)`, `plan_windows(n_sub, n_dfg, config) -> WindowPlan(spans, single, capped)`, `encode_window`, `build_windows(code_tokens, dfg, tokenizer, config, use_dfg=None) -> WindowedInput(inputs, plan, node_ids, n_code_subtokens, dfg_node_count, truncated; n_windows, dfg_nodes_used)`; `pool_hidden`, `EmbedResult` (+`embedding`, `to_dict`), `GraphCodeBERTV2Embedder(tokenizer, encoder, config, model_revision).embed(code, language, use_dfg=None)`, `.from_pretrained(name, config, local_files_only, device, batch_size)` (revision = `config._commit_hash`). Choices: per-window node budget follows upstream (`L + D - len(source)`, 128 for a full window) rather than a flat D; `truncated` = cap hit, uncovered subtokens or nodes dropped (single input: `encode().truncated`); language aliases (`c++`, `cc`, ...) map to `cpp`; exceptions give `success=False` with `error`.
- Forecast: ~400 lines. Commit `feat(gcb): sliding windows, pooling and embed pipeline`.

## WU6 - Legacy freeze, facade, config (GE7, D1, D13, TH1.2)

- [x] 6.1 RED: `tests/test_gcb_facade.py` (monkeypatch `RobertaModel/Tokenizer.from_pretrained` to tiny/fake): with `input_version="v2"` keys = legacy keys + `dfg_nodes_used, n_windows, input_version, pooling, adapter_loaded, truncated, parse_errors`; `used_graph` iff `use_dfg and dfg_nodes_used>0` (code with no variables gives False); long file `n_windows>1` with same 768-d shape; honest `success` (True with parse errors, False on empty/exception). `real_engine`-style call (constructor, `predict`/`predict_code`, `embedding`, `config.embedding_dim/charcnn_embedding_dim/fused_dim`) works. (GE7.3, GE7.4, GE7.6)
  - Evidence: RED = collection error (`models.graphcodebert.legacy_inference` absent). Loaders are replaced on the `legacy_inference` module (tiny 32-d RoBERTa, fake tokenizer with `encode`/`__call__`); shape equality is checked on the tiny hidden size, 768 in the real-weights smoke.
- [x] 6.2 RED: default `input_version=="legacy"` dispatches to the legacy path with adapter off and the same old keys plus the new ones populated with legacy values/`chunks`; `contrastive_graphcodebert` private calls (`_build_graph_aware_input`, `_inject_dfg_embeddings`, `_dfg_extractor`, `encoder`, `tokenizer`) still resolve on the facade (import-level smoke). (D1, GE7.5 as amended)
  - Evidence: same file; legacy keys and values equal the frozen `LegacyGraphCodeBERTInference` on the same weights; the contrastive module imports (`importorskip("peft")`).
- [x] 6.3 RED: rewrite `tests/test_lora_guard.py`: default `adapter_path is None` although the shipped dir exists; explicit path logs WARNING and `adapter_loaded`/`is_lora_loaded` False; `"peft" not in sys.modules` on the facade path (subprocess or fresh import check); `lora_weights_applied` unit tests kept; legacy `load_adapter=True` still applies weights (`requires_graphcodebert` + `importorskip("peft")`). (GE7.1, GE7.2, TH1.2)
  - Evidence: RED = collection error (same import). Peft check runs in a fresh interpreter for both `legacy` and `v2` with an explicit path; `_load_merged_adapter` is patched to fail if ever called.
- [x] 6.4 GREEN: create `models/graphcodebert/legacy_inference.py` (current class moved verbatim; adapter only with `load_adapter=True`); rewrite `inference.py` as facade subclass with dispatch (default `"legacy"`) and re-export of `lora_weights_applied`; edit `config.py` (delete adapter auto-default; add `input_version="legacy"`, `pooling`, `use_dfg`, `code_length`, `data_flow_length`, `max_windows`, `attn_implementation`; fusion fields unchanged). Static test: `fusion.py` config field names unchanged (GE7.6).
  - Evidence: `tests/test_gcb_facade.py tests/test_lora_guard.py` -> 32 passed (incl. 3 real-weights tests, none skipped). Legacy file diff vs old `inference.py`: docstring, `SHIPPED_ADAPTER`, class rename, `load_adapter` gate (falls back to the shipped adapter when `adapter_path` is unset). v2 shares the base encoder, switched to eager via `set_attn_implementation` on first v2 use. `GraphCodeBERTConfig.v2_config()` validates the v2 fields (invalid -> `ValueError`). v2 failure -> `success=False`, `embedding=[]`. README gained a short facade/adapter section (full rewrite stays WU9). Side effect: the known failure `test_graphcodebert_calibration` now passes (adapter no longer auto-loaded); WU8 still replaces it as planned.
- [x] 6.5 Add a test documenting the legacy-default deviation (default config -> legacy, v2 only on explicit request) with a pointer to SDD-4 in the test docstring.
  - Evidence: `test_legacy_default_is_a_documented_deviation_until_sdd4`. Verification: focused command 176 passed; full suite 967 passed, 1 skipped, 0 failed. Route: delegated direct (PR slice 3 writer).
- Forecast: ~450 lines (move of legacy class not counted as authored). Commit `refactor(gcb): freeze legacy path, facade dispatch, drop adapter default`.

## WU7 - Cache, pair scoring, baselines (GV1.2, GV2, GV4, GV5, D10-D11)

- [ ] 7.1 RED: `tests/test_gcb_pairs.py`: per-assignment `E_g E_g^T` scoring equals brute-force cosine on a fixture; pair `a`/`b` index to ids/starts correct; views `all`/`no_identical` (drop label-0 equal-`norm_hash`, keep label-1) with dropped counts; MAP@R per assignment, identical-hash negatives `-inf` in `no_identical`, same-student count reported. (GV1.2, GV4)
- [ ] 7.2 RED: cache tests: key = sha256(file bytes) + `cache_key` json of {input_version, walker_version, variant, model_revision, budgets, max_windows, dtype}; same file encoded once; changed key component misses; duplicate contents share an entry; atomic write; stores both `cls` and `mean`. (GV2, NF6)
- [ ] 7.3 RED: baselines tests: token Jaccard (5-shingles via `models.evaluation`) equals reference set Jaccard on a fixture; winnowing w=4 fingerprint Jaccard on a hand case; all methods score identical pair sets per view. (GV5.1, GV5.2)
- [ ] 7.4 GREEN: `v2/embed_cache.py`, `v2/pairs.py`, `v2/baselines.py` (scipy sparse incidence product; scipy is already present - verify, else fall back to numpy and note).
- [ ] 7.5 GREEN: legacy baseline adapter (`LegacyGraphCodeBERTInference(load_adapter=True)`; falls back to `legacy_base` if `peft` missing or weights not applied, reason recorded; `skipped` entry when weights unavailable). Unit-tested with a stub.
- Forecast: ~500 lines. Commit `feat(gcb): embedding cache, pair scoring and lexical baselines`.

## WU8 - Evaluation CLI and test repair (GV1-GV6, TH1.1, D10-D12)

- [ ] 8.1 RED: `tests/test_gcb_evaluate.py` (fixture manifest from `eval_factory.make_tree`, stub hash-vector embedder): ambiguous/unlabelled excluded and counted; stage order enforced - embedder raises if a test id is requested before `selection.json` exists; selection on val only (assert ids); pooling chosen on val PR-AUC (ties MAP@R then CLS); thresholds from `select_threshold` on raw val cosine at `DEFAULT_TARGETS`; test evaluated exactly once (second call raises); undefined metrics null with reason; bootstrap by assignment; cache hit on rerun; exit 1 on `--expected-sha256` or file sha mismatch with nothing written; `--local-files-only` missing model -> exit 1; outputs only under `runs/graphcodebert/<ts>/` (`config.json` with transformers/tree_sitter versions, `selection.json`, `thresholds_val.json`, `calibration.json`, `<method>__<view>/{metrics.json,report.md}`, `summary.json`, `data_summary.json`, root `report.md`), `status` running->complete|failed, exit codes 0/1/3.
- [ ] 8.2 GREEN: `v2/runs.py` (copy of char_cnn v2 run contract, D12), `v2/evaluate.py` (`python -m models.graphcodebert.v2.evaluate`, flags per design incl. `--n-boot`, `--methods`, `--limit-assignments`, `--no-cache`, `--cache-dir`). Isotonic `calibration.json` for SDD-4 only (D10).
- [ ] 8.3 Replace the circular `test_graphcodebert_calibration` in `tests/test_calibration_experiment.py` with a `requires_graphcodebert` smoke: raw cosine(fizzbuzz, variant) > cosine(fizzbuzz, quicksort), no thresholds; CharCNN/orchestrator tests there stay. A val-only fit/threshold, test-only evaluation test is covered by 8.1 (TH1.1). Confirm the previously failing test no longer fails.
- [ ] 8.4 Debug-run on the fixture and with `--limit-assignments 3` using the real model, `--n-boot 20` (parent-run, short), to validate wiring before WU10.
- Forecast: ~550 lines. Commit `feat(gcb): zero-shot evaluation CLI`.

## WU9 - Docs (GV6.3 partial, D13)

- [ ] 9.1 Rewrite `models/graphcodebert/README.md`: v2 input and masking, windows (382/191/16), pooling, adapter policy (never loaded; explicit path ignored), facade default `legacy` until SDD-4, CLI and run layout, legacy/deprecation notes (contrastive/fine_tune use the legacy encoding until Phase 2), limitations (label noise, Chroma reindex needed in SDD-4, fp32 only, over-approximated switch fallthrough). Results section left as a marked placeholder filled in WU10. Structural readback only (passive docs).
- Forecast: ~200 lines. Commit `docs(gcb): README v2 section and deprecations`.

## WU10 - Real run, artifacts, results (parent-run; subagents must not launch long runs)

- [ ] 10.1 (parent) Build embedding caches for val and test labelled human entries: `v2` (CLS+mean), `v2_nodfg`, `legacy`. Launch detached; log to scratch; resumable via cache (NF6). Record wall times, parse-error and truncation rates.
- [ ] 10.2 (parent, DECISION D-A) Run `python -m models.graphcodebert.v2.evaluate --manifest data/splits/split_v1.json.gz --expected-sha256 <sha> --device cuda --local-files-only --n-boot <N>` detached. Proposal: first a `--n-boot 300` full pass (~1 h) to validate and read results; run `--n-boot 1000` (~3 h) only for the final artifacts if time allows. Test is evaluated once per run; a rerun creates a new run dir.
- [ ] 10.3 Commit selected artifacts only, with `git add -f` by explicit path: `config.json`, `metrics.json`, `report.md`, `calibration.json` (plus `summary.json`, `selection.json`, `thresholds_val.json`, `data_summary.json` if small). NOT caches, curve CSVs or embeddings. Commit `data(gcb): zero-shot v2 run artifacts`.
- [ ] 10.4 README results section, honest: report measured PR-AUC/MAP@R/ROC with CI for v2 (selected pooling), v2_nodfg, Jaccard, winnowing, legacy (labelled, not comparable); include a negative result if v2 does not beat Jaccard; label-noise caveat. Commit `docs(gcb): results`.
- [ ] 10.5 (parent) Final full `python -m pytest tests/ backend/tests/ -q -p no:cacheprovider`: zero failures, `git status` shows `best_model.pth` only as the user's pre-existing modification, no diff under `models/evaluation/` or `backend/`.
- Forecast: ~100 authored lines (artifacts not counted). 

## Decisions needed

- D-A (WU10.2): `--n-boot` value. Default 1000 is ~3 h; proposed 300 for the validating pass, 1000 for the final artifacts only if the user accepts the wait.
- D-B (WU10.3): which extra small JSON files (`summary.json`, `selection.json`, `thresholds_val.json`, `data_summary.json`) to commit besides the four required; proposed: all four, each is small.
- Resolved in-task (no user input): vendored commit hash and `k` (1.1), tree-sitter node names (2.4), GE3.3 isolated-node behavior vs upstream (3.1).

## Risks

- Mask semantics under transformers 5.14 (D5): the mask-honoured test in WU4 is the arbiter; failing it blocks WU5+.
- Legacy-default facade (user decision) deviates from spec GE7.4/7.5; keep the deviation tested and documented so SDD-4 flips one default.
- WU2/WU7/WU8 exceed ~400 lines; kept as one unit each for coherence (advisory heuristic).
- Evaluation runtime depends on assumed ~10k labelled files; measure in 8.4 before committing to n_boot.
