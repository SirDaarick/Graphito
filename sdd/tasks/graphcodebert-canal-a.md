# Tasks: GraphCodeBERT Canal A — Semantic Embeddings

> Canal B (CharCNN) shipped; Canal A is greenfield. Order: P1 DFG → P2 inference → P3 fusion.

## Review Workload Forecast

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

| Field | Value |
|-------|-------|
| Lines | 800–1000 |
| Delivery | ask-on-risk |
| Split | PR 1 (DFG) → PR 2 (Inference) → PR 3 (Fusion + E2E) |

| Unit | Goal | PR |
|------|------|-----|
| 1 | DFG + tests | PR 1 → main |
| 2 | Inference + tests | PR 2 → main |
| 3 | Fusion + E2E + README | PR 3 → main |

## Phase 0: Foundation

- [ ] **0.1** Add `tree-sitter`, `tree-sitter-c`, `tree-sitter-cpp`, `transformers` to `data/requirements.txt`. **V**: `pip install -r` ok; `import tree_sitter, tree_sitter_c, tree_sitter_cpp, transformers` exits 0.

## Phase 1: P1 DFG (PR 1) — files: `models/graphcodebert/{__init__,config,parser}.py`, `tests/test_parser.py`

- [ ] **1.1** `__init__.py` (empty) + `config.py` with `@dataclass GraphCodeBERTConfig(model_name="microsoft/graphcodebert-base", max_tokens=512, embedding_dim=768, device=None)`. **V**: `GraphCodeBERTConfig()` instantiates.

- [ ] **1.2** `parser.py` defines `DFGEdge(source_indices, target_index, relation)`, `DFGResult(code_tokens, dfg_edges, index_to_code, success)`, `RELATIONS={"computedFrom","lastUse","lastWrite","comesFrom"}`. **V**: import works.

- [ ] **1.3** `DFG_c_cpp(code, lang)`: AST walk; handle `declaration`/`init_declarator`/`assignment_expression` (`computedFrom` RHS→LHS), `update_expression` (self-loop). **V**: `int x=5; int y=x+3;` → edge to `y`.

- [ ] **1.4** Control flow: `for`/`while` walk body twice (loop-carried); `if` copies state per branch then merges (`comesFrom` from branch RHS). **V**: `for(int i=0;i<n;i++){sum+=i;}` → edges for `i<n`, `i++`, `sum+=i`.

- [ ] **1.5** `parameter_declaration` → `lastWrite`; `call_expression` args → `lastUse`; `return_statement` var → `lastUse`. **V**: `int add(int a,int b){return a+b;}` → `lastUse` for `a`,`b` into return.

- [ ] **1.6** `DFGExtractor` facade: `parse_file(path)` dispatches by ext → `parse_code(text, lang)`; on parse error return `DFGResult([],[],{},success=False)`, NEVER raise. **V**: `DFGExtractor().parse_code("int x = ;", "c")` returns `success=False` no raise.

- [ ] **1.7** `tests/test_parser.py` covers 5 DFG spec scenarios (decl+assign, params+return, for-loop, if-else, malformed). **V**: `pytest models/graphcodebert/tests/test_parser.py -v` → 5 passed.

- [ ] **1.8** Re-export `DFGExtractor`, `DFG_c_cpp`, `DFGResult`, `DFGEdge`, `GraphCodeBERTConfig` from `__init__.py`. **V**: import succeeds.

## Phase 2: P2 Inference (PR 2) — files: `inference.py`, `tests/test_inference.py`

- [ ] **2.1** `GraphCodeBERTInference.__init__(model_name="microsoft/graphcodebert-base", device=None)`: load `AutoTokenizer` + `AutoModel` via `from_pretrained`, move to device, `eval()`. **V**: construct ok; `engine.tokenizer`/`engine.model` truthy.

- [ ] **2.2** `_build_graph_aware_input(code_tokens, dfg_edges, index_to_code)`: BPE-tokenize, `subtoken_map`, prepend `[CLS]`/append `[SEP]`, `position_ids` (code=2..n+1, DFG=0), `dfg_to_code` (DFG→subtokens). **V**: shape `[1, 7+]` for `"int x = 5;"`; DFG positions `position_id=0`.

- [ ] **2.3** Attention mask: code↔code fully connected; DFG→source code subtokens + connected DFG nodes. Shape `[seq_len, seq_len]`. **V**: unit test asserts specific `(i,j)=1` and non-connected `=0`.

- [ ] **2.4** `_extract_embedding(input_ids, position_ids, attn_mask, dfg_node_indices)`: forward pass; replace DFG embeddings with mean of source code subtoken embeddings; take `[CLS]` index 0 → 768-dim `list[float]`. **V**: length 768, values in `[-1,1]`.

- [ ] **2.5** `predict(file_path) -> dict` and `predict_code(code, language="c") -> dict` return `{"embedding", "language", "dfg_node_count", "success", "parse_status":"ok"|"fallback"}` (mirrors `CharCNNInference.predict()`). **V**: 768-dim `embedding` key present.

- [ ] **2.6** DFG fallback: `success=False` builds input with empty `dfg_to_code`, all-ones code attention, `token_type_ids` all zeros; `parse_status="fallback"`. **V**: `predict_code("int x = ;")` returns `parse_status="fallback"`, length-768, no raise.

- [ ] **2.7** 514-token truncation: BPE `len > 514` ⇒ truncate `code_tokens` to 512 BEFORE DFG re-index, `logger.warning("Truncated to 512 BPE tokens")`. **V**: 800-token file → `input_ids` ≤ 514; warning logged.

- [ ] **2.8** Add `GraphCodeBERTInference` to `__init__.py`. `tests/test_inference.py` covers spec scenarios; gate with `pytest.mark.skipif` for CI without HF cache. **V**: `pytest models/graphcodebert/tests/ -v` all green.

## Phase 3: P3 Fusion (PR 3) — files: `models/fusion.py`, `tests/test_fusion.py`

- [ ] **3.1** Define `FusionResult(semantic_embedding, style_embedding, fused_vector, prob_sintetico, is_synthetic)` and `ComparisonResult(reference_path, similarity, semantic_similarity, style_penalty)`. **V**: import works.

- [ ] **3.2** `BimodalFusion.__init__(graphcodebert, charcnn)`: store both, do NOT trigger loads. **V**: construct succeeds without double-loading.

- [ ] **3.3** `fuse(code_path) -> FusionResult`: `graphcodebert.predict()` (768-dim sem) + `charcnn.predict()` (1024-dim style); `fused_vector = sem + style` (1792-dim); pull `prob_sintetico` from CharCNN dict. **V**: real `.c` file → `len(fused_vector) == 1792`.

- [ ] **3.4** Asymmetric cosine `similarity(student, reference) -> float`: `reference.style_embedding is None` ⇒ `zeros(1024)`; `num = dot(sem_s, sem_r)`; `den = ||fused_s|| * ||sem_r||`; `style_penalty = ||fused_s|| / ||sem_s||`. **V**: identity → 1.0 ± 1e-6; zero-pad path non-NaN.

- [ ] **3.5** `compare(student_path, reference_paths) -> list[ComparisonResult]`: `fuse()` each, compute `similarity` per pair, sort DESC. **V**: 3 refs → 3 results DESC-ordered; deterministic on rerun.

- [ ] **3.6** `tests/test_fusion.py` covers 4 spec scenarios (zero-pad student→ref, symmetric student→student, ref→ref, identity) using `unittest.mock`. **V**: 4 passed.

## Phase 4: Verification & Docs (PR 3 end) — files: `tests/fixtures/`, `test_e2e.py`, `README.md`

- [ ] **4.1** E2E: `compare()` ranks original above paraphrased. Add `tests/fixtures/{original.c,paraphrase.c}` + `test_e2e.py` marked `pytest.mark.slow`. **V**: `pytest -m slow` → original above paraphrase.

- [ ] **4.2** `models/graphcodebert/README.md`: install, quickstart (load → `predict` → `fuse` → `compare`), API reference, fallback, Canal B link. **V**: copy-paste quickstart runs.

- [ ] **4.3** Canal B non-regression: `python models/char_cnn/inference.py ... best.pth examples/hello.c` still emits 1024-dim embedding. **V**: CLI runs no ImportError; skip+log if checkpoint missing.

## Implementation Order

1. **PR 1**: Phase 0 → 1. Standalone DFG; no model weights.
2. **PR 2**: Phase 2 (gated PR 1). First PR downloading `microsoft/graphcodebert-base`.
3. **PR 3**: Phase 3 → 4 (gated PR 2). Ties Canal A + B; closes change.

Each PR independently mergeable. Rollback: delete `models/graphcodebert/` + `models/fusion.py` + revert `requirements.txt`.

## Out of Scope (deferred)

P4 ChromaDB, P5 FastAPI; GraphCodeBERT fine-tuning; pointer/array aliasing; local `modelos/weights/` (HF cache only v1).
