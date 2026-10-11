# Proposal: Fix GraphCodeBERT DFG Input (fix-graphcodebert-dfg-input)

## Intent

Channel A (GraphCodeBERT similarity, `models/graphcodebert/`) does not feed the model the input it was pre-trained on, so its scores cannot be measured honestly. The exploration found:
- **Broken input encoding.** Subtokens are misaligned (`inference.py:210` vs `:245`). Embeddings are hand-built without token_type and the encoder gets a custom 4D additive mask (`:169-184`). DFG node positions come from the target token instead of 0 (`:254-262`). CLS/SEP never attend DFG nodes (`:268`). Nodes are edges, not variable occurrences, with symmetric links. Line chunking at 480 tokens breaks parsing (`:95-120`). `used_graph` is hardcoded True (`:151`).
- **Weak DFG extraction.** Any parse error drops the whole DFG (`parser.py:596`). No def-use chains, `int b = a;` yields no edge, braceless `if` is dropped, loops produce 21% duplicate edges, and several C/C++ constructs (for-range, do, switch, struct fields, pointer-return params) are missed. Comments stay in the token stream.
- **Silent adapter.** `config.py:24-27` auto-loads the shipped MLM LoRA adapter even when `adapter_path` is None; it lowered AUC (0.646 to 0.630 in the old benchmark) and `peft` is not in requirements.

This change is SDD-3 of Phase 1. It makes the implementation faithful to the original GraphCodeBERT and measures the zero-shot base model on `split_v1`. It does **not** try to improve the model.

## Scope

### In Scope
- Vendored, read-only reference (`parser/DFG.py`, `clonedetection/run.py` from microsoft/CodeBERT, MIT license + source commit) under `tests/reference/graphcodebert/` for golden tests.
- A v2 DFG walker for C/C++ in the reference style, error-tolerant, with comments removed.
- A v2 input builder faithful to `clonedetection/run.py`, with sliding windows for long files.
- Zero-shot base model only: the adapter is never loaded.
- Backward-compatible `predict_code` facade with honest flags; current pipeline frozen as a labelled legacy path.
- Honest evaluation on `split_v1` with baselines, both data views, an embedding cache, and outputs under `runs/graphcodebert/<ts>/` only; README section.
- Test repair: replace the circular calibration test, rewrite `test_lora_guard`, strengthen `test_dfg_parser`.

### Out of Scope
- Contrastive or LoRA training; `contrastive_graphcodebert.py` / `fine_tune_graphcodebert.py` stay untouched (Phase 2).
- Backend integration, fusion, thresholds and sigmoid mapping (SDD-4). `real_engine.py` is not edited.
- Fixing label noise in the dataset; changes to `models/evaluation` APIs (consumed only).
- Any change to the shipped adapter weights or `models/char_cnn/best_model.pth`.

## Capabilities

### New Capabilities
- `gcb-dfg-extraction`: v2 C/C++ DFG walker (variable-occurrence nodes, comesFrom/computedFrom, states, branch union, deduplicated loops), comment removal, error tolerance with a `parse_errors` flag, golden parity against the vendored reference.
- `gcb-input-encoding`: v2 input builder (alignment, budgets, position ids, 3D attention mask, node embeddings), sliding windows, pooling, adapter never loaded, backward-compatible result contract and frozen legacy path.
- `gcb-evaluation`: zero-shot evaluation on `split_v1` with val-only selection and thresholds, baselines, `all`/`no_identical` views, grouped CI95, embedding cache and versioned run artifacts.

### Modified Capabilities
- None. `eval-foundation` is consumed unchanged.

## Approach

1. **Reference.** Vendor the two upstream files read-only with license and commit hash; golden tests compare the v2 walker's output shape and semantics on shared constructs.
2. **DFG v2.** Nodes are `(code, idx, comesFrom|computedFrom, parent codes, parent idxs)`; a states dict tracks last definitions; branches take the union; loops are walked twice with dedup. Covers declarations with initializers, assignments (RHS recursion), update expressions, braceless if, for / for-range / while / do / switch, field writes, struct/enum, pointer-return function params. Walks the tree even with parse errors.
3. **Input v2.** `tokenize('@ ' + x)[1:]`, `ori2cur_pos`, budgets such as 384 code + 128 DFG ≤ 512. Position ids: DFG = 0, pad = 1, code from 2. Mask: code↔code, CLS/SEP↔nodes, node↔aligned code, node↔DFG parents. Node embedding = mean of aligned code word embeddings. Forward via `model(inputs_embeds=..., attention_mask=<3D>, position_ids=...)` with eager attention so HF adds token_type and position embeddings. A test proves the 3D mask is honoured.
4. **Long files.** Parse the DFG once on the full file; slide windows over subtokens, restrict nodes to each window, average window embeddings; record `n_windows` and `truncated`.
5. **Adapter.** Config default removed; an explicit adapter path is ignored with a warning; `is_lora_loaded` stays False.
6. **Pooling.** Compute CLS and mean over code tokens; select on val only; report both.
7. **Facade.** Keep `embedding`, `language`, `code_tokens_count`, `dfg_node_count`, `success`, `used_graph` with honest values; add `dfg_nodes_used`, `n_windows`, `input_version`, `pooling`, `adapter_loaded=False`, `truncated`, `parse_errors`.
8. **Evaluation.** Val + test human entries of the labelled pairs (ambiguous excluded). Pair ROC-AUC and PR-AUC, MAP@R within assignment, CI95 by grouped bootstrap, thresholds fitted on val only. Views: `all` and `no_identical` (drops label-0 pairs with identical `norm_hash`). Baselines: token Jaccard / winnowing, v2 without DFG (ablation), frozen legacy pipeline with adapter (labelled legacy). Disk cache keyed by sha256 + `input_version`. Run records transformers and tree-sitter versions.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `models/graphcodebert/parser.py` | Modified | Legacy walker frozen; v2 walker added (module layout in design) |
| `models/graphcodebert/inference.py` | Modified | v2 builder, windows, pooling, facade; legacy path frozen |
| `models/graphcodebert/config.py` | Modified | Adapter auto-load removed |
| `models/graphcodebert/` (eval CLI, cache; names in design) | New | Evaluation harness writing to `runs/graphcodebert/<ts>/` |
| `tests/reference/graphcodebert/` | New | Vendored upstream files + LICENSE + commit note |
| `tests/test_lora_guard.py`, `tests/test_dfg_parser.py`, `tests/test_calibration_experiment.py` | Modified | Adapter never loaded; stronger DFG cases; split-based val-only test |
| `tests/` | New | Golden parity, mask honoured, windows, contract tests |
| `backend/.../real_engine.py`, `models/fusion.py`, `scripts/benchmark_*.py` | Unchanged (verify in design) | Rely on legacy keys and embedding dims |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Zero-shot v2 loses to token Jaccard | Med | Negative result reported as is; it motivates Phase 2 |
| Label noise (364k GT-negatives identical after normalization) | High | `no_identical` view reported alongside `all` |
| Extreme imbalance (~1 positive per 5,600 pairs) | High | PR-AUC and MAP@R as headline; grouped CI95 |
| Unpinned transformers 5.14 / tree-sitter 0.26 drift (eager attn, mask API) | Med | Versions recorded per run; mask-honoured test fails on drift |
| DFG extraction and encoding time on ~3.5M pairs' files | Med | Per-file embedding cache; pairs scored from cached vectors |
| Backend still passes an adapter path until SDD-4 | Med | Ignored with warning; documented |
| Old benchmark numbers not comparable | High | Report states split, input and adapter differences; legacy baseline labelled |

## Rollback Plan

All work lands as work-unit commits on `feat/fix-graphcodebert-dfg-input`; revert them. The legacy path stays callable and the backend contract keys are unchanged, so runtime impact is limited to the adapter no longer loading, which is restored by reverting the `config.py` commit. `runs/` output is gitignored apart from selected reports.

## Dependencies

- SDD-1 `eval-foundation`: `load_split`, labelled pairs with ambiguous mask, metrics (incl. `map_at_r`), val-only calibration, `RunContext`, `strip_comments`, Jaccard/winnowing helpers; `split_v1` (manifest `e835362d`).
- transformers, tree_sitter, torch (present). No new runtime dependencies; `peft` no longer needed on the v2 path.

## Success Criteria

- [ ] Golden tests pass: v2 walker matches the vendored reference on shared constructs, and the v2 input builder matches `run.py` positions and mask layout.
- [ ] A test proves the 3D attention mask is honoured (masked-out tokens do not change outputs).
- [ ] Tests prove the adapter is never loaded, including when a path is passed.
- [ ] `used_graph`, `parse_errors`, `truncated`, `n_windows` reflect actual behaviour on fixtures.
- [ ] Pooling and thresholds are selected on val only; test is evaluated once.
- [ ] `runs/graphcodebert/<ts>/` holds metrics with CI95 for v2, v2-no-DFG, Jaccard/winnowing and legacy, in both views, plus recorded library versions.
- [ ] Existing consumer tests and the new tests pass under `pytest`.

## Open Questions

- Golden parity scope: upstream has no C/C++ walker, so parity is checked on constructs shared with the reference languages (assumed: port the reference logic to C/C++ node types and compare on equivalent snippets). Confirm in design.
