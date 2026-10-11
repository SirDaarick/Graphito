# Spec: fix-graphcodebert-dfg-input

Keywords follow RFC 2119. Scenarios MUST be testable with pytest on small synthetic snippets. Tests MUST NOT need GraphCodeBERT weights, Postgres or ChromaDB, except scenarios marked `[real-weights]`, which MUST use the existing `requires_graphcodebert` marker (skip when weights are missing). Golden and encoding tests use a tiny offline vocabulary fixture (a word-level or char-level tokenizer stub with the same `tokenize` contract) and a tiny randomly initialised RoBERTa-style model on CPU. Consumed unchanged from `eval-foundation`: `load_split`, labelled pairs via `models.evaluation.ground_truth.pairs` (with the ambiguous mask), `metrics` (`roc_auc`, `average_precision`, `map_at_r`, grouped bootstrap CI), val-only `calibration`, `provenance` (`package_versions`, `file_sha256`), `RunContext`, `normalize.strip_comments`, token shingles and Jaccard helpers. Constants: `INPUT_VERSION = 2`, code budget 384, DFG budget 128, max length 512, window stride default 192, shingle size 5, split `split_v1`.

Reference: `tests/reference/graphcodebert/` holds read-only copies of upstream `parser/DFG.py` and `clonedetection/run.py` (microsoft/CodeBERT) with `LICENSE` (MIT) and a `SOURCE.md` naming the upstream commit. Upstream has no C/C++ walker.

## Capability: gcb-dfg-extraction (new)

### GD1. Reference vendoring and golden parity
- GD1.1 The reference files MUST be present unmodified, with the MIT LICENSE and the upstream commit hash. A test MUST fail if either file is missing or `SOURCE.md` lacks a 40-hex commit.
- GD1.2 For constructs shared with the reference languages (declarations with and without initializer, assignment including compound, if/else, for, while, return, calls), the v2 walker MUST produce nodes whose `(code, relation, parent_codes)` sequence equals the sequence produced by the upstream C# or Java walker on an equivalent snippet. Parity is on semantic content, not on token indices, which differ across grammars.
- GD1.3 For C/C++-only constructs (pointers, `field_expression`, `update_expression` on subscripts, `for_range_loop`, `do`, `switch`, struct/enum bodies, pointer-return function params, braceless bodies) there is no upstream oracle. Tests MUST use hand-written expected node lists.

Scenarios
- Given `int a = 1; int b = a; return b;` and the Java equivalent, When both are walked, Then the `(code, relation, parent_codes)` lists are equal.
- Given `x += y;` (C) and the Java equivalent, When walked, Then both give `x computedFrom [x, y]` plus the `x`/`y` reads.
- Given a deleted reference file, When the vendoring test runs, Then it fails.

### GD2. Node format
- GD2.1 `extract_dfg_v2(code) -> DfgResult` MUST return `nodes`, `parse_errors: bool` and `code_tokens`. Each node MUST be `(code, idx, relation, parent_codes, parent_idxs)` with `relation` in `{comesFrom, computedFrom}` and `idx` the index of the variable occurrence in `code_tokens`. `parent_codes` and `parent_idxs` MUST have equal length.
- GD2.2 Nodes MUST represent variable occurrences. Edges MUST be directional (child to parent), not symmetric pairs.
- GD2.3 Output MUST be deterministic: two runs on the same input MUST be identical, and nodes MUST be sorted by `idx`.

Scenarios
- Given `int a; a = 1; int b = a;`, When walked, Then every node has equal-length parent lists and `idx` values point to tokens equal to `node.code`.
- Given the same input twice, Then both results are equal.

### GD3. Def-use and states
- GD3.1 The walker MUST keep a states map from variable name to the indices of its last definitions. A read MUST emit `comesFrom` to those indices.
- GD3.2 `int b = a;` MUST emit `b comesFrom/computedFrom [a]` (a declaration with initializer is a definition). A declaration without initializer MUST define the name with no parents.
- GD3.3 A compound assignment (`x += y`) MUST read and write the LHS: `x computedFrom [x, y]`.
- GD3.4 RHS expressions MUST be recursed, including calls (`f(a, b)` yields reads of `a`, `b`), binary and unary expressions, subscripts and casts.
- GD3.5 `update_expression` (`i++`, `--i`, `a[i]++`, `s.n++`) MUST read and write the operand; for subscripts and fields the base identifier MUST be updated.

Scenarios
- Given `int a = 1; int b = a;`, Then a node `b` with parent `a` exists.
- Given `a = 1; a = 2; int c = a;`, Then `c` has only the second definition of `a` as parent.
- Given `x = f(a, b);`, Then `x` has parents `a` and `b`.
- Given `a[i]++;` and `s.n++;`, Then `a` and `s` each have a node with itself as an earlier-definition parent.

### GD4. Control flow
- GD4.1 `if`/`else` bodies MUST be walked whether braced or not (braceless included). States after the branches MUST be the union of the states from each branch and the incoming state when no `else` exists.
- GD4.2 `for`, `while`, `do` and `for_range_loop` bodies MUST be walked twice so loop-carried definitions reach earlier uses. Resulting nodes and edges MUST be deduplicated (no repeated `(code, idx, relation, parent_idxs)` tuple).
- GD4.3 `switch` MUST walk every `case` and `default` body, with union of states.

Scenarios
- Given `int a=0; if (c) a=1; else a=2; int b=a;`, Then `b` has both definitions of `a` as parents (braceless).
- Given `if (c) a=1; int b=a;` with prior `a=0`, Then `b` has parents for both `a=0` and `a=1`.
- Given `int s=0; for (int i=0;i<n;i++) s=s+i;`, Then `s` in the body comes from the initial and the loop definition, and no node tuple repeats.
- Given a `do { } while` loop, a `for (auto x : v)` loop and a `switch` with two cases, Then each yields nodes from all bodies.

### GD5. Declarators, parameters and aggregates
- GD5.1 Pointer and reference declarators (`int *p = &a;`, `int &r = a;`, `int **q`) MUST resolve to the underlying identifier as the defined name.
- GD5.2 Function parameters MUST be definitions, including parameters whose function declarator sits under a pointer return type (`char *f(int n)`), array and pointer parameters, and reference parameters.
- GD5.3 `struct`/`class`/`enum` bodies MUST NOT be treated as leaves: field declarations and enumerators MUST appear in `code_tokens` and fields written through `field_expression` (`s.n = 1`) MUST be definitions of the base variable.

Scenarios
- Given `int *p = &a; int &r = a;`, Then nodes `p` and `r` have parent `a`.
- Given `char *f(int n) { return n; }`, Then `n` is defined as a parameter and the later read has it as parent.
- Given `struct P { int x; }; P s; s.x = 1; int y = s.x;`, Then tokens include `x` from the struct body and `y` has parent `s`.

### GD6. Tokens and parse errors
- GD6.1 Comments MUST be absent from `code_tokens` and from the parse used for nodes (removal via `strip_comments` before parsing, or node-skipping with equal effect).
- GD6.2 A parse error MUST NOT drop the DFG. The walker MUST traverse the tree despite `ERROR` or `MISSING` nodes, return the nodes extractable from healthy subtrees, and set `parse_errors=True`. A clean parse MUST set `parse_errors=False`.

Scenarios
- Given `int a = 1; // int z = a;`, Then no token or node comes from the comment.
- Given `int a = 1; int b = a; int c = ;`, Then nodes for `b` and `a` exist and `parse_errors` is True.
- Given a fully valid snippet, Then `parse_errors` is False.

## Capability: gcb-input-encoding (new)

### GE1. Alignment and budgets
- GE1.1 Code subtokens MUST be `tokenizer.tokenize('@ ' + token)[1:]` per Tree-sitter token. `ori2cur_pos` MUST map each original token index to its `(start, end)` range in the subtoken list; subtokens of one token MUST be contiguous and in order.
- GE1.2 The builder MUST take configurable `max_code_tokens` (default 384) and `max_dfg_nodes` (default 128) and MUST reject a configuration where `max_code_tokens + max_dfg_nodes + 3 > 512` (CLS, SEP, plus nodes) or where it exceeds the model position capacity.
- GE1.3 The sequence MUST be `[CLS] code_tokens [SEP] dfg_nodes [PAD...]` with total length exactly `max_length` (default 512). Nodes whose `idx` falls outside the retained code range MUST be dropped. Excess nodes beyond the budget MUST be dropped in `idx` order and the result MUST flag `truncated=True` only when code or nodes were actually cut.

Scenarios
- Given a token that the fixture tokenizer splits in three, Then its `ori2cur_pos` range has length 3 and the next token starts where it ends.
- Given 400 code subtokens and default budgets, Then 384 are kept and `truncated` is True.
- Given a config of 450 + 128, Then construction raises a configuration error.

### GE2. Position ids
- GE2.1 Position ids MUST equal those produced by the vendored `run.py` logic on the same input: DFG nodes 0, padding 1, code tokens (CLS first) from 2 in order.
- GE2.2 A node's position MUST NOT depend on the target token index (regression for `inference.py:254-262`).

Scenarios
- Given code and DFG fixtures, When positions are built by v2 and by the vendored logic, Then arrays are equal.
- Given two nodes aligned to different code positions, Then both have position id 0.

### GE3. Attention mask
- GE3.1 The builder MUST produce a 3D boolean mask `[L, L]` per example with exactly the `run.py` rules: code (including CLS and SEP) attends all code; CLS and SEP attend all nodes and nodes attend CLS and SEP; a node attends the code tokens aligned to it and the nodes listed in its `parent_idxs` (and each such parent attends its children, as in `run.py`); padding attends and is attended by nothing.
- GE3.2 The mask MUST equal the `run.py`-derived mask on the same `(code tokens, DFG)` input, including `ori2cur_pos`.
- GE3.3 A node with no aligned code token and no parent MUST still attend itself.

Scenarios
- Given the golden fixture, Then v2 mask equals the vendored mask elementwise.
- Given a padded example, Then every padding row and column is False.

### GE4. Embedding path
- GE4.1 Node input embedding MUST be the mean of the word embeddings of its aligned code subtokens (not including position or type embeddings), as in `run.py`.
- GE4.2 The forward pass MUST call the encoder with `inputs_embeds`, `position_ids` and the 3D mask, with eager attention, so that position and token_type embeddings are added by the model. Embeddings MUST NOT be assembled by hand without token_type.
- GE4.3 The mask MUST be honoured: for a tiny model with eager attention, perturbing the input embedding of a token masked out for a protected position MUST leave that position's output unchanged (within 1e-6), while perturbing an attended token MUST change it.
- GE4.4 If the loaded transformers version cannot honour a 3D mask, the builder MUST raise rather than silently attend everything.

Scenarios
- Given a node aligned to subtokens 3 and 4, Then its input embedding equals the mean of those two word embeddings.
- Given a masked-out token perturbed, Then the protected position output is unchanged; given an attended token perturbed, Then it changes.
- Given the same input twice (eval mode), Then outputs are identical.

### GE5. Sliding windows
- GE5.1 The DFG MUST be extracted once over the full file (never per window), and the full-file subtoken sequence MUST be windowed with configurable `window` and `stride`. Defaults follow the design: a file that fits the upstream budget gets exactly the single upstream input; longer files use windows of 382 code subtokens (384 with CLS/SEP), stride 191, at most 16 windows (`truncated` True if any subtoken is uncovered).
- GE5.2 Windows MUST start at `0, stride, 2*stride, ...`; the last window MUST end at the last subtoken (the final start is `max(0, n - window)` when the regular grid would overshoot or leave a tail). A file shorter than the window MUST give exactly one window.
- GE5.3 For each window the nodes MUST be restricted to those whose `idx` is inside the window, with parent indices outside dropped, then budget-limited per GE1.3.
- GE5.4 The file embedding MUST be the mean of window embeddings. The result MUST record `n_windows` and `truncated` (True only if some window dropped nodes or the window count hit a configured cap).
- GE5.5 Windowing MUST NOT split by lines.

Scenarios
- Given 1000 subtokens, window 382, stride 191, Then starts are 0, 191, 382, 573, 618 (the last window ends at 1000) and `n_windows == 5`.
- Given 100 subtokens, Then `n_windows == 1`.
- Given a node at token 600, Then it appears only in windows that contain it.

### GE6. Pooling
- GE6.1 The encoder MUST expose both poolings: `cls` (hidden state at position 0) and `mean_code` (mean over non-padding code tokens including CLS and SEP excluded; DFG nodes and padding excluded). Both MUST be computed from one forward pass.
- GE6.2 The pooling name MUST be a parameter, default `cls`, and be echoed in the result.

Scenarios
- Given a tiny model, Then `mean_code` equals the mean of last hidden states over code positions only and differs from `cls`.

### GE7. Adapter, config and facade
- GE7.1 `GraphCodeBERTConfig` MUST NOT default `adapter_path` to the shipped adapter. With no argument, the adapter MUST NOT be loaded and `is_lora_loaded` MUST be False.
- GE7.2 An explicit `adapter_path` MUST be ignored with a logged/raised-as-warning message; `is_lora_loaded` MUST remain False. `peft` MUST NOT be imported on the v2 path.
- GE7.3 `predict_code(code, language)` MUST keep keys `embedding`, `language`, `code_tokens_count`, `dfg_node_count`, `success`, `used_graph`, and MUST add `dfg_nodes_used`, `n_windows`, `input_version`, `pooling`, `adapter_loaded`, `truncated`, `parse_errors`.
- GE7.4 `dfg_node_count` is the number of nodes extracted from the full file; `dfg_nodes_used` is the number of distinct nodes placed in at least one window (unique count across windows). `used_graph` MUST be True iff `dfg_nodes_used >= 1`; `adapter_loaded` MUST be False; `input_version` MUST be 2 on the v2 path and `"legacy"` on the legacy path.
- GE7.5 The legacy pipeline (old 4D mask, line chunking, auto-adapter) MUST be frozen: its code unchanged apart from relocation. Amended by user decision (2026-10-11): until SDD-4 reindexes Chroma, the facade default (`input_version="legacy"`) MUST remain the legacy pipeline with the adapter OFF (GE7.1/GE7.2 still apply), so backend embeddings stay comparable; v2 MUST be selected explicitly (evaluation CLI, tests). The legacy-with-adapter variant MUST be reachable only through an explicitly named entry point and used only for the labelled baseline.
- GE7.6 `models/fusion.py` config fields MUST be preserved (same names and defaults), and the embedding dimension MUST remain 768.

Scenarios
- Given default config, Then `is_lora_loaded` is False; given `adapter_path='x'`, Then a warning is emitted and it is still False.
- Given code with no variables, Then `used_graph` is False and `dfg_nodes_used == 0`; given code with variables, Then `used_graph` is True.
- Given a long file, Then `n_windows > 1` and the embedding has the same shape as for a short file.
- Given a statically inspected `fusion.py`, Then config field names are unchanged.

## Capability: gcb-evaluation (new)

### GV1. Pairs and splits
- GV1.1 Pairs MUST come from `split_v1` `val` and `test` human entries through `models.evaluation.ground_truth.pairs`. Ambiguous pairs and unlabelled pairs MUST be excluded and counted in the manifest of the run. Expected scale: val about 1.60M pairs (174 positive), test about 1.91M (338 positive); tests use a fixture manifest.
- GV1.2 Pairs MUST be scored within assignment only; similarity is cosine over file embeddings.

Scenarios
- Given a fixture with one ambiguous and one unlabelled pair, Then neither is scored and counts are reported.

### GV2. Embedding cache
- GV2.1 Embeddings MUST be cached on disk keyed by `sha256(file bytes)`, `input_version` and `pooling`, plus a hash of the encoder and window configuration. A change in any key component MUST miss the cache.
- GV2.2 Pair scores MUST be computed from cached vectors; encoding MUST run at most once per distinct key.

Scenarios
- Given the same file encoded twice, Then the encoder is called once. Given `pooling` changed, Then it is called again.

### GV3. Metrics and selection
- GV3.1 Headline metrics MUST be PR-AUC (`average_precision`) and MAP@R within assignment; ROC-AUC MUST be reported as secondary. CI95 MUST use the grouped bootstrap (grouping as in `eval-foundation`) and MUST be reported for each headline metric.
- GV3.2 Pooling (`cls` vs `mean_code`) and thresholds MUST be chosen on `val` only. `test` MUST be evaluated exactly once with the frozen choice; a second evaluation call in the same run MUST raise.
- GV3.3 Undefined metrics (no positives) MUST be reported as null with a reason, not as zero.

Scenarios
- Given a run, Then selection inputs contain only val-split entries (assert on ids).
- Given a second test evaluation in the same run, Then an error is raised.

### GV4. Views
- GV4.1 View `all` MUST include all labelled non-ambiguous pairs. View `no_identical` MUST drop label-0 pairs whose two files have equal `norm_hash`; label-1 pairs MUST be kept. Both views MUST be reported for every method.
- GV4.2 The number of dropped pairs MUST be recorded.

Scenarios
- Given a label-0 pair with equal norm_hash and a label-1 pair with equal norm_hash, Then `no_identical` drops only the first.

### GV5. Baselines
- GV5.1 The run MUST include: token Jaccard on 5-token shingles; winnowing; v2 without DFG (nodes empty, same windows and pooling); the frozen legacy pipeline with its adapter, labelled `legacy` in all outputs. Legacy MUST be skipped with an explicit `skipped` entry, not an error, when weights are unavailable.
- GV5.2 All methods MUST be scored on identical pair sets per view.

Scenarios
- Given the fixture, Then every method key exists in both views with the same pair count.

### GV6. Outputs
- GV6.1 Outputs MUST be written only under `runs/graphcodebert/<timestamp>/`: `config.json` (including `transformers` and `tree_sitter` versions, input_version, window, stride, budgets, seed), a manifest with sha256 of split manifest and inputs, `metrics.json`, `report.md`, and per-view results. Files MUST be written atomically.
- GV6.2 The harness MUST NOT write to `models/`, `backend/chroma_data/`, or the repository root.
- GV6.3 `README` MUST gain a section reporting the results as measured, including negative results against Jaccard, the label-noise caveat, and that legacy numbers are not comparable.

Scenarios
- Given a run in a temp directory, Then all listed files exist and no other path was created outside `runs/`.

## Capability: test-hygiene (modified tests)

### TH1. Repaired tests
- TH1.1 The circular `test_graphcodebert_calibration` MUST be replaced by a test that fits and thresholds on split val only and evaluates on test via `eval-foundation` calibration (no scoring of the data it was fitted on).
- TH1.2 `test_lora_guard` MUST be rewritten to assert the adapter is never loaded, including with an explicit path (GE7.1, GE7.2).
- TH1.3 `test_dfg_parser` MUST cover every construct in GD3-GD6.

## Non-functional requirements

- NF1. `models/evaluation/*` APIs MUST remain unchanged.
- NF2. `backend/` (including `real_engine.py`) MUST remain unchanged; backend integration belongs to SDD-4.
- NF3. No model training. `contrastive_graphcodebert.py`, `fine_tune_graphcodebert.py`, `models/char_cnn/best_model.pth` and the shipped adapter MUST be untouched.
- NF4. Library versions (transformers 5.14.0, tree_sitter 0.26.0 as measured) MUST be recorded per run; no new runtime dependency may be added.
- NF5. Tests SHOULD run on CPU in under 60 seconds in total, excluding `[real-weights]` scenarios.
- NF6. Evaluation SHOULD be resumable via the cache after interruption.
