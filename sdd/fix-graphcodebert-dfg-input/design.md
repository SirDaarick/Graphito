# Design: Fix GraphCodeBERT DFG Input (fix-graphcodebert-dfg-input)

## Technical Approach

The current pipeline is frozen as a labelled **legacy** path. `parser.py` gets zero edits. The body of the current `inference.py` class moves verbatim to `legacy_inference.py`, with one gate: the adapter loads only when `load_adapter=True` is passed. All new behaviour lives in `models/graphcodebert/v2/`. It is a faithful port of upstream GraphCodeBERT (`parser/DFG.py` walker style plus `clonedetection/run.py` features, mask and model forward) to tree-sitter C/C++, with sliding windows for long files. `models/graphcodebert/inference.py` becomes the facade. `GraphCodeBERTInference` subclasses the legacy class, so `contrastive_graphcodebert.py` and its private calls (`_build_graph_aware_input`, `_inject_dfg_embeddings`, `_dfg_extractor`, `encoder`, `tokenizer`) still import and run unchanged. `predict`/`predict_code` dispatch on `config.input_version` (default `"v2"`). The evaluation CLI consumes `models.evaluation` unchanged and writes only under `runs/graphcodebert/`. `real_engine.py`, `fusion.py` and `scripts/` are not edited: they only use the constructor, `predict*`, `embedding` (768-d), `success` and `config.embedding_dim/charcnn_embedding_dim/fused_dim`.

## Architecture Decisions

| # | Decision | Rejected alternative | Rationale |
|---|----------|----------------------|-----------|
| D1 | `v2/` subpackage. `parser.py`, `contrastive_graphcodebert.py`, `fine_tune_graphcodebert.py` and the adapter dir are untouched. The legacy class lives in `legacy_inference.py`, and the facade subclasses it. | Versioned functions inside `inference.py`/`parser.py`; composition facade | `tests/test_dfg_parser.py` imports `parser.DFGExtractor/DFGEdge`. `contrastive_graphcodebert.py:98-128` calls private legacy methods on the engine. Subclassing keeps them working with one shared base encoder. |
| D2 | Golden parity of the walker runs the **vendored `DFG_java`** on the *same C tree* through a `JavaView` node proxy (type and field renaming), then compares tuple lists exactly. | Installing `tree-sitter-java` and comparing equivalent Java snippets modulo indexing | Same tree means same `index_to_code`, so the comparison is exact equality, needs no new dependency and introduces no translation error. An optional real-Java test may run if `tree_sitter_java` is importable (skip otherwise). |
| D3 | Parity scope = constructs shared with the Java walker (declaration with/without init, assignment, update, if/else incl. braceless, `for` with declaration init, while, range-for ↔ enhanced_for, return, call). C-specific **deviations** are explicit flags-free behaviour, unit-tested separately (D4). | Full parity including deviations | The upstream quirks below are wrong for C. Parity snippets avoid them, so the golden stays exact. |
| D4 | Deviations from upstream: (a) the `init_declarator` name is the innermost declarator identifier (`a[10]` does not define `10`); (b) states reset at each `function_definition` (globals persist); (c) the `for` second pass starts after the `initializer` child of any type (upstream only after a declaration); (d) `do`/`switch` handled (below); (e) zero-width MISSING nodes are skipped; (f) tokens are sliced by byte offsets. | Pure upstream port | Each fixes a C-specific false edge or a missed flow found in exploration. All are recorded in `WALKER_VERSION` notes. |
| D5 | The encoder gets a **4D additive mask** `[B,1,L,L]` (0 / `finfo(dtype).min`) built from the upstream 3D bool mask, via `RobertaModel.from_pretrained(name, attn_implementation="eager")(inputs_embeds, attention_mask, position_ids, token_type_ids=0)`. | Passing the 3D bool mask as upstream does (transformers 4.x `get_extended_attention_mask`); the legacy hand-built embeddings plus `encoder.encoder(...)` | transformers 4.x mapped 3D to exactly this 4D form. 5.x masking utilities treat a 4D mask as precomputed, while 3D handling is version-dependent. HF adds the token_type and position embeddings, LayerNorm and dropout itself. A mask-honoured test (offline, tiny random config) is the arbiter and fails on drift. A second test asserts 3D==4D outputs when 3D is accepted. |
| D6 | fp32 only in this change. `dtype` is recorded. fp16 is deferred until a parity test exists (cos ≥ 0.9995 vs fp32 on fixtures). | fp16 autocast for speed | The runtime is affordable in fp32 (see Runtime). Parity first. |
| D7 | Windows: a file that fits the upstream dynamic budget gets exactly the upstream single input. Otherwise fixed windows of `Wc = code_length-2` subtokens, stride `Wc//2`, at most `max_windows=16` (evenly spaced starts, last ends at the file end). The window embedding is the unweighted mean. | Line chunking (legacy `inference.py:102-153`); head truncation | The DFG is parsed once on the full file, so parsing never breaks. Single-window files are bit-parity with upstream. |
| D8 | The no-DFG ablation reuses the **same window starts** as the DFG variant and only drops nodes. | Recomputing windows with the 0-node budget | Same code context isolates the DFG effect. |
| D9 | Both poolings (CLS, mean over code-token positions excluding CLS/SEP/nodes/pad) come from one forward pass and are both cached. Selection is on val PR-AUC (`all` view), with ties broken by MAP@R, then CLS. | Fixing CLS a priori | The proposal requires val-only selection. Mean pooling is a common zero-shot winner, so both are measured. |
| D10 | Thresholds: `select_threshold` on **raw val cosine** at `DEFAULT_TARGETS` (0.05, 0.01). The resulting points feed `compute_metrics` on raw test cosine. An isotonic `calibration.json` (`build_calibration`, ScoredSet of pair ids `"a\|b"`, `split="val"`, `manifest=None`) is written for SDD-4 only. | Isotonic calibration, then thresholds in calibrated space for the metrics | Cosine is not in [0,1], so Platt/temperature refuse it. Isotonic plateaus would tie test scores and lower ROC/PR. One raw score space gives a single bootstrap pass. `_require_val(manifest)` cannot resolve pair ids, so the split guarantee comes from building val pairs only. |
| D11 | Bootstrap unit = **assignment** (`bootstrap_groups=pair.assignment`). | dup_group (pairs span two files); per-pair resampling | Every file's pairs live inside one assignment, so assignments are the independent units. |
| D12 | Run plumbing: `v2/runs.py` copies the char_cnn v2 contract (status `running→complete\|failed`, exit 0/1/3/4, `write_json`, `set_run_status`, `describe_error`, `resolve_device`). | Importing `models.char_cnn.v2.runs` (pulls `models/char_cnn/__init__` → legacy CharCNN); lifting to a shared module (edits archived char_cnn) | Same semantics across channels without cross-channel coupling. Lifting it to `models/common` is a later refactor. |
| D13 | Adapter: the `config.py` auto-default is deleted. The facade logs `WARNING adapter_path ignored (zero-shot v2/legacy facade never loads adapters)` when a path is given (the backend passes one, `real_engine.py:35-37`). `is_lora_loaded=False` and `adapter_loaded=False`, and `peft` is never imported on the facade path. | Raising on an explicit path | Raising would break the backend until SDD-4. |

## DFG v2 (`v2/dfg.py`, `WALKER_VERSION = "c-cpp-2"`)

- **Pre-processing**: `code.decode(utf-8, errors="replace")` → `models.evaluation.normalize.strip_comments` (string-aware, keeps lines) → UTF-8 bytes → tree-sitter C or C++ (`Sample.lang`).
- **Tokens** (`tree_to_token_index`): leaves, plus atomic `string_literal`, `char_literal`, `raw_string_literal`, `system_lib_string`, minus `comment` and zero-width nodes. `index_to_code[(start_point,end_point)] = (idx, text)`, where text = bytes slice decoded.
- **Node tuple**: `(code, idx, "comesFrom"|"computedFrom", [parent codes], [parent idxs])`. `states: dict[str, list[int]]` holds the last definitions.
- **Leaf rule** (upstream): if `type == text`, skip. If the text is in states → `comesFrom` states. Else, if it is an `identifier`, define it with `comesFrom []`.
- **Variable index**: non-keyword leaves (literals count as sources, as upstream).

| tree-sitter C/C++ node | Handling |
|---|---|
| `init_declarator` (`declarator`,`value`) | Walk the value. The name (innermost identifier, D4a) gets `comesFrom` each value var. The state is set. `int b = a;` → `b ← a`. |
| `declaration` without init, `parameter_declaration`, `enumerator` | Leaf rule defines the identifiers (params incl. pointer-returning `function_declarator` nested in `pointer_declarator`). `enumerator` with a value is treated as `init_declarator`. |
| `assignment_expression` (all ops) | Walk the right side. Left vars (`identifier`, `field_expression` → obj and `field_identifier`, `subscript_expression`, `pointer_expression`) get `computedFrom` right vars. The state is set (upstream: compound ops do not self-link). |
| `update_expression` | Each var gets `computedFrom` itself. The state is set. |
| `if_statement` / `else_clause` | The condition and consequence run sequentially. `else_clause` runs from the pre-if states. Result = union of branch states, plus pre-if states when there is no else (set-sorted). Braceless bodies are plain statements. |
| `for_statement` | One pass over all children, then a second pass after the `initializer` (D4c). Dedup merge by `(code,idx,rel)`. |
| `for_range_loop` (C++) | Upstream enhanced_for: two passes of {range value; declarator `computedFrom` range vars; body}, then merge. |
| `while_statement`, `do_statement` | Two passes over the children in source order, then merge (do = body, then condition). |
| `switch_statement` | The condition runs sequentially. Each `case_statement` walks from the post-condition states. Union of all case states plus post-condition (fallthrough over-approximated). |
| `function_definition` | Walked with a copy of the translation-unit states (D4b). |
| `struct/enum/union_specifier`, `field_declaration` | Default walk. `field_identifier` leaves define nothing. Field *writes* go through assignment. |
| `ERROR`, any other node | Default: walk the children in order with threaded states. Missing fields fall back to the default walk. |

**Loops** are deduplicated by the upstream merge (parents unioned, idxs sorted), so no duplicate tuples remain. **Post-filter** (upstream `extract_dataflow`): sort by idx, keep nodes that have parents or are someone's parent. **Errors**: `parse_errors = root.has_error`, and the walk proceeds anyway. Any exception or `RecursionError` (the limit is raised inside a scoped context) gives `dfg=[]` with `dfg_error` recorded and tokens kept. Output: `Dataflow(code_tokens, dfg, parse_errors, dfg_error, n_nodes_raw)`.

## Input v2 (`v2/encode.py`, `INPUT_VERSION = "v2"`; `v2/model.py`)

This mirrors the vendored `convert_examples_to_features` and `TextDataset.__getitem__` statement for statement. The golden test is the arbiter, including the exact truncation constants.
1. Subtokens: `tokenize(x)` for token 0, `tokenize('@ ' + x)[1:]` otherwise. `ori2cur_pos[-1]=(0,0)`, and `ori2cur_pos[i]` = cumulative span. Flatten.
2. Truncate code to the upstream budget `B(n_dfg) = L + D - k - min(n_dfg, D)` (then `[:512-k]`, `k` as in the vendored file), with L=384 and D=128. `[CLS] code [SEP]`, `position_idx = i + pad_id + 1` (from 2).
3. Nodes `dfg[:L+D-len(source)]`: id `unk`, position 0. Pad to L+D: id `pad`, position 1. Reindex parents (`reverse_index`, drop parents that were cut). `dfg_to_code = ori2cur_pos[idx] + 1` (CLS offset).
4. Mask `[L+D, L+D]` bool: code↔code `[:node_index,:node_index]`. CLS/SEP rows → all non-pad. node↔aligned code span (both directions, if inside the code). node → its parent nodes. Pad rows stay empty (eager gives a uniform row, never read).
5. Model (`model.py`, upstream `model.py`): `nodes = pos==0`, `tokens = pos>=2`. Node embedding = mean of the word embeddings of aligned code tokens (`einsum` over `nodes&tokens&mask`, `+1e-10`). Then `roberta(inputs_embeds, attention_mask=to_4d(mask), position_ids=pos, token_type_ids=zeros)`. `model.eval()`, `torch.no_grad()`, fp32, batches of windows (default 16).
- **Windows** (`v2/windows.py`): `plan_windows(n_sub, n_dfg_cfg) -> [(start,end)]` per D7. The window node set = nodes whose span lies fully inside `[start,end)`, first D by idx. Parents are restricted to that set. Spans are shifted by `-start+1`. Outputs: `n_windows`, `truncated` (any subtoken uncovered), `dfg_nodes_used` (unique nodes placed), `dfg_node_count` (post-filter total).

## Facade (`inference.py`) and Config

`GraphCodeBERTConfig` adds `input_version="legacy"` (user decision 2026-10-11: the facade default stays the legacy pipeline, adapter off, until SDD-4 switches to `"v2"` and reindexes Chroma; `"v2"` is selected explicitly by the evaluation CLI and tests), `pooling="cls"`, `use_dfg=True`, `code_length=384`, `data_flow_length=128`, `max_windows=16`, `attn_implementation="eager"`. The legacy fields stay, `adapter_path` stays (ignored, D13), and the auto-default is removed. `v2/config.py` holds a frozen, side-effect-free `GCBV2Config` with `to_dict()` (cache key and run config).

| Key | legacy | v2 |
|---|---|---|
| `embedding` (768), `language` | as today | mean of window poolings (`pooling`) |
| `code_tokens_count` | as today | DFG-level code tokens of the full file |
| `dfg_node_count` | as today | post-filter nodes (full file) |
| `success` | as today | embedding produced (True with parse errors; False on empty input or exception) |
| `used_graph` | as today | `use_dfg and dfg_nodes_used > 0` |
| `dfg_nodes_used`, `n_windows`, `truncated`, `parse_errors` | legacy values / `chunks` / False / `has_error` | measured |
| `input_version`, `pooling`, `adapter_loaded` | `"legacy"`, `"cls"`, `is_lora_loaded` | `"v2"`, config, `False` |

## Evaluation (`python -m models.graphcodebert.v2.evaluate`)

- **Flags**: `--manifest data/splits/split_v1.json.gz`, `--expected-sha256` (refuse → exit 1), `--root .`, `--runs-root runs`, `--device`, `--batch-size 16`, `--seed 42`, `--n-boot 1000`, `--methods v2,v2_nodfg,jaccard,winnowing,legacy`, `--cache-dir runs/graphcodebert/_cache`, `--no-cache`, `--local-files-only` (model missing → exit 1), `--limit-assignments N` (debug, recorded).
- **Data**: `load_manifest` → `plagiarism_pairs("val")` and `("test")` (ambiguous and unlabeled excluded by default). Files = `PairSet.ids` → `Sample` via an id→sample dict. Bytes are read from `root / id`, and the sha256 must equal `Sample.sha256` (mismatch → refused). Pair labels = `PairSet.label`, with `a`/`b` indexing `ids`.
- **Embed cache** (`v2/embed_cache.py`): `<cache-dir>/<cache_key>/<sha[:2]>/<sha256>.npz`, where `cache_key = sha256(json{input_version, walker_version, variant(dfg|nodfg|legacy_adapter|legacy_base), model_revision, budgets, max_windows, dtype})`. Each entry stores `cls`, `mean` (both poolings, so pooling is a field rather than a key), plus the facade flags. Writes are atomic (`provenance.atomic_write_bytes`). Duplicate contents share entries.
- **Pair scoring** (`v2/pairs.py`): `PairSet` rows are contiguous per assignment (`ids` sorted by assignment, then id). Per assignment, `E_g` = L2-normalized `[n_g,768]`, `S_g = E_g E_gᵀ`, and `score = S_g[a-start, b-start]`. No pair-sized embedding gather (1.9M×768 would be ~11 GB).
- **Views**: `all`. `no_identical` drops label-0 pairs with `norm_hash[a]==norm_hash[b]`.
- **MAP@R**: per assignment, `map_at_r(S_g, cluster_id or None)` → `mean_map_at_r`. In `no_identical`, identical-hash negative candidates get `-inf` (equivalent to removal). Same-student off-diagonal count is reported (expected 0).
- **Baselines** (`v2/baselines.py`): token Jaccard = `shingle_tokens` → `token_ids` → `shingle_hashes(k=5)`, scored per assignment via a sparse incidence product (scipy) `|A∩B|/|A∪B|`. Winnowing: positional rolling hashes (same formula, re-implemented locally since `shingle_hashes` returns unique sorted values), window w=4, fingerprint-set Jaccard. Legacy: `LegacyGraphCodeBERTInference(load_adapter=True)`. If `peft` is missing or weights are not applied, it falls back to `legacy_base` and the run records the reason. Results are labelled `legacy`, and old numbers are never mixed in.
- **Stages**: (1) embed and score **val** only. (2) `selection.json`: pooling per embedding method (D9), point PR/ROC/MAP@R for both poolings, no bootstrap. (3) Thresholds (D10) → `thresholds_val.json`, `calibration.json` (v2 selected). (4) Embed and score **test once**. For each method × view, `compute_metrics(y, s, channel="graphcodebert", split="test", mode=f"{method}/{view}", operating_points, bootstrap_groups=assignment, bootstrap_unit="assignment", map_at_r=…)`, then `RunContext(path=run/f"{method}__{view}", …).write`. The non-selected pooling gets test point values only (secondary, no CI). (5) `summary.json` plus a comparison table appended to the root `report.md`.
- **Run dir** `runs/graphcodebert/<ts>/`: `config.json` via `RunContext.create("graphcodebert", seed, split="test", mode="zero_shot", manifest_sha256, config={GCBV2Config, versions{torch, transformers, tree_sitter, tree_sitter_c, tree_sitter_cpp}, model_revision (HF snapshot sha), device, methods}, status)`. Also `selection.json`, `thresholds_val.json`, `calibration.json`, `<method>__<view>/` (`metrics.json`, `report.md`, curves), `summary.json`, `data_summary.json` (files, pairs, positives per split and view, parse-error and truncation rates). Exit: 0 complete, 1 refused (nothing written or run untouched), 3 failed (stage and reason recorded).
- **Runtime/memory (estimate; logged at start)**: N ≈ 10k labelled val+test files (assumed). DFG + tokenization at ~30 ms/file ≈ 5 min. Forward at ~1.5 windows/file, 16/batch, ~15 ms/window on the 2060S ≈ 4 min per embedding variant (legacy ~10 min). The largest `S_g` is a few MB. The bootstrap dominates: ~1 s/resample on 1.9M pairs gives ~17 min per method×view, so ~3 h total at `--n-boot 1000` (`--n-boot 300` for iteration). Curve CSVs reach about 1 GB in `runs/` (gitignored).

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `models/graphcodebert/v2/{__init__,config,dfg,encode,windows,model,embed,embed_cache,pairs,baselines,evaluate,runs}.py` | Create | v2 pipeline |
| `models/graphcodebert/legacy_inference.py` | Create | Current class moved verbatim. Adapter only with `load_adapter=True`. |
| `models/graphcodebert/inference.py` | Rewrite | Facade subclass with dispatch and new keys. Re-exports `lora_weights_applied`. |
| `models/graphcodebert/config.py` | Modify | Adapter auto-default removed, new v2 fields |
| `models/graphcodebert/README.md` | Rewrite | v2 input, windows, adapter policy, CLI, run layout, legacy and deprecation notes (contrastive/fine_tune use the legacy encoding until Phase 2), limitations |
| `models/graphcodebert/{parser,contrastive_graphcodebert,fine_tune_graphcodebert}.py`, `adaptador-lora-20k/` | Unchanged | Frozen or out of scope |
| `tests/reference/graphcodebert/{parser/DFG.py,parser/utils.py,clonedetection/run.py,clonedetection/model.py,LICENSE,SOURCE.md}` | Create | Vendored read-only (MIT, pinned commit in SOURCE.md). Never collected or imported as tests. |
| `tests/gcb_reference.py` | Create | Helpers: `JavaView` proxy, AST-extract `convert_examples_to_features` / `TextDataset.__getitem__` from `run.py` into an injected namespace (stub `extract_dataflow`, tokenizer, args) |
| `tests/test_gcb_{dfg_golden,encode,model,windows,facade,pairs,baselines,evaluate}.py` | Create | See Testing |
| `tests/test_dfg_parser.py` | Modify | Legacy classes untouched (frozen guard), plus v2 classes |
| `tests/test_lora_guard.py` | Rewrite | Adapter never loaded |
| `tests/test_calibration_experiment.py` | Modify | Remove the circular `test_graphcodebert_calibration`. The CharCNN and orchestrator tests stay. |
| `backend/**`, `models/fusion.py`, `scripts/*` | Unchanged | Contract keys and dims preserved |

## Testing Strategy

| Layer | What | Approach |
|---|---|---|
| Golden (offline) | Walker parity | ~15 C/C++ snippets of D3 constructs. Vendored `DFG_java(JavaView(root))` == v2 walker, raw and post-filter, exact tuples. Proxy: `init_declarator→variable_declarator(name←declarator)`, `declaration→local_variable_declaration` inside `for`, `else_clause` flattened to `else`+stmt, `for_range_loop→enhanced_for_statement`, `char_literal→character_literal`. Tokenization parity vs vendored `tree_to_token_index`. |
| Unit | v2 DFG | `int b=a;`, braceless if, loop dedup (no duplicate keys), range-for, do, switch, field write, pointer-return params, function scope reset, array declarator, parse-error file keeps the DFG and sets `parse_errors`, comments absent from tokens, MISSING skipped, non-ASCII byte offsets |
| Golden | Features and mask | Extracted `run.py` code vs `encode` on the same `(tokens, dfg)`: ids, positions, `dfg_to_code`, `dfg_to_dfg`, mask equal. With a **fake deterministic tokenizer** (always runs) and the real tokenizer (`requires_graphcodebert`). |
| Unit (offline) | Mask honoured | Tiny random `RobertaConfig` (2 layers, eager). Position j unreachable by any row except itself: perturbing its embedding leaves the others unchanged, and the full-mask control does change. 3D==4D when 3D is accepted. Upstream `model.py` forward (wrapper with `.roberta`, identity classifier) == `v2.model` hidden states. |
| Unit | Windows and pooling | Budget boundary (fits → 1 window, parity), coverage, cap with `truncated`, node restriction and parent reindex, mean excludes CLS/SEP/nodes/pad, ablation shares starts |
| Contract | Facade | `RobertaModel/Tokenizer.from_pretrained` monkeypatched to tiny or fake: v2 and legacy keys, honest `used_graph`/`n_windows`/`truncated`/`parse_errors` on fixtures. `real_engine`-style call works. |
| Guard | Adapter | Default `adapter_path is None` even though the shipped dir exists. An explicit path → warning, `adapter_loaded`/`is_lora_loaded` False, `"peft" not in sys.modules`. `lora_weights_applied` unit tests kept. Legacy `load_adapter=True` still applies the weights (`requires_graphcodebert` + `importorskip("peft")`). |
| Integration | Evaluate | `tests/eval_factory.make_tree` manifest in `tmp_path`, stub embedder (hash vectors). Pair-index→id mapping, views, MAP@R, an embedder that raises if a test id is requested before `selection.json` exists, cache hits on rerun, exit 1 on sha mismatch, run artifacts and status. |
| Smoke | Real model | `requires_graphcodebert`: raw cosine(fizzbuzz, variant) > cosine(fizzbuzz, quicksort). No thresholds (replaces the circular test). |

Offline availability: `microsoft/graphcodebert-base` is cached locally (refs/main `2b0488a7…` has the tokenizer, config and `pytorch_model.bin`). The existing `requires_graphcodebert` marker (`tests/conftest.py`, `AutoConfig local_files_only`) gates real-weight tests. All golden and mask tests run without weights.

## Migration / Rollout

No data migration. Embeddings change meaning (legacy+adapter → v2 zero-shot), so existing Chroma vectors are incomparable. Reindexing belongs to SDD-4. Work-unit commits (advisory, ~400 authored lines, vendored files excluded):
1. `test(gcb): vendor upstream GraphCodeBERT reference` + `gcb_reference.py` helpers.
2. `feat(gcb): v2 C/C++ DFG walker` + golden parity + v2 `test_dfg_parser` cases.
3. `feat(gcb): v2 feature builder and attention mask` + run.py golden.
4. `feat(gcb): v2 encoder forward` + mask-honoured and model.py golden.
5. `feat(gcb): sliding windows, pooling and embed pipeline` + tests.
6. `refactor(gcb): freeze legacy path, facade dispatch, drop adapter default` + `test_lora_guard` rewrite + contract tests.
7. `feat(gcb): embedding cache, pair scoring and lexical baselines` + tests.
8. `feat(gcb): zero-shot evaluation CLI` + integration test + removal of the circular test.
9. `docs(gcb): README v2 section and deprecations`.
10. Real run. Selected `metrics.json`/`report.md`/`summary.json`/`selection.json` committed with `git add -f`.

## Open Questions

- [ ] The facade defaults to `input_version="v2"`, which changes backend embeddings before SDD-4 reindexes Chroma. Alternative: default `"legacy"` (adapter off) until SDD-4. Needs an owner decision.
- [ ] The vendored commit hash and the exact `run.py` truncation constant (`k`) are fixed in work unit 1. The design defers to the file.
- [ ] Whether `tree-sitter-c` 0.26 grammar node names (`else_clause`, `condition_clause`) hold for both C and C++ is verified by the walker tests in work unit 2.
