# Proposal: GraphCodeBERT Canal A — Semantic Embeddings

## Intent

Canal B (CharCNN) works but Canal A (semantic embeddings) is missing. Without Canal A, the system cannot detect paraphrased or semantically-equivalent code. This proposal adds DFG parsing, GraphCodeBERT feature extraction, and bimodal fusion.

## Scope

### In Scope
- **P1 — DFG Parser**: `tree-sitter-c` + `tree-sitter-cpp` def-use chain extractor
- **P2 — GraphCodeBERT Wrapper**: `microsoft/graphcodebert-base` feature-extraction mode, graph-aware attention, 768-dim `[CLS]` output
- **P3 — Fusion**: 768-dim semantic + 1024-dim style = 1792-dim fused vector; asymmetric cosine with zero-padded references

### Out of Scope
- P4 — ChromaDB persistence, P5 — FastAPI backend (future changes)
- GraphCodeBERT fine-tuning, pointer/array aliasing in DFG

## Capabilities

### New Capabilities
- `dfg-extractor`: C/C++ Data Flow Graph via tree-sitter (def-use chains for declarations, assignments, updates, loops, conditionals)
- `graphcodebert-inference`: Graph-aware feature extraction, 768-dim semantic embeddings
- `bimodal-fusion`: Concatenation + asymmetric cosine between Canal A and Canal B

### Modified Capabilities
None.

## Approach

```
Source (.c/.cpp)
  ├─▶ DFG Parser → graph-aware tokens → GraphCodeBERT → 768-dim
  └─▶ CharCNN → 1024-dim ──▶ [768|1024] = 1792-dim fused vector
```

- DFG rules ported from Guo et al. to C/C++ tree-sitter grammars
- `GraphCodeBERTInference` mirrors `CharCNNInference.predict()` interface
- References zero-pad 1024 style dims for asymmetric cosine penalty
- Parse failures fall back to text-only `[CLS]` embedding

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `models/graphcodebert/` | New | DFG parser, tokenizer wrapper, inference |
| `models/fusion.py` | New | Bimodal fusion + asymmetric cosine |
| `requirements.txt` | Modified | +tree-sitter, +transformers |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| C/C++ not in pretraining | High | Validate with equivalence set; text-only fallback |
| Parse failures on student code | Medium | Error-tolerant parser; graceful degradation |
| C++ STL complexity | Medium | v1 scope: introductory constructs only |

## Rollback Plan

All Canal A code is isolated in `models/graphcodebert/` and `models/fusion.py`. Remove these + revert `requirements.txt`. Canal B unaffected.

## Dependencies

- `tree-sitter`, `tree-sitter-c`, `tree-sitter-cpp`
- `transformers` (HuggingFace)
- `models/char_cnn/` (read-only, for fusion)
- `modelos/weights/` (cached GraphCodeBERT files)

## Success Criteria

- [ ] DFG parser extracts correct def-use chains for 10+ `.c`/`.cpp` samples
- [ ] `predict()` returns 768-dim vector for valid C/C++ input
- [ ] Fusion produces 1792-dim vector from both channels
- [ ] Zero-padded references rank correctly via asymmetric cosine
- [ ] Parse failure degrades gracefully (no crash)
- [ ] No regression in CharCNN inference
