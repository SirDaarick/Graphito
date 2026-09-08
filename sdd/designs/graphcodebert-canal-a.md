# Design: GraphCodeBERT Canal A — Semantic Embeddings

## Technical Approach

Three-layer pipeline that mirrors the existing Canal B (`CharCNNInference`) conventions:
**tree-sitter DFG extraction → graph-aware GraphCodeBERT embedding → asymmetric bimodal fusion**.
DFG rules are ported from Guo et al. (2021) to C/C++ tree-sitter grammars. Parse failures
degrade gracefully to text-only `[CLS]` embeddings so Canal B is never blocked.

Reference: proposal `sdd/proposals/graphcodebert-canal-a.md`.

## Architecture Decisions

### Decision: DFG extraction as pure function + facade class

| Option | Tradeoff | Decision |
|--------|----------|----------|
| A) `DFGExtractor` class only | Encapsulation, but hides DFG algorithm | No |
| B) `DFG_c_cpp()` standalone + `DFGExtractor` facade | Testable function + clean API; matches upstream GraphCodeBERT | **Yes** |

**Rationale**: `DFG_c_cpp` must be unit-testable in isolation (the recursion logic is complex). The facade class handles tree-sitter lifecycle and language detection. This mirrors upstream code structure, easing future porting of Guo et al. fixes.

### Decision: tree-sitter 0.23+ Language API

| Option | Tradeoff | Decision |
|--------|----------|----------|
| A) `Language(lib_path, name)` (0.21) | Older but widespread | No |
| B) `Language(lang_obj)` (0.23+) | Uses grammar PyPI packages directly | **Yes** |

**Rationale**: `tree-sitter-c` and `tree-sitter-cpp` ship grammar objects compatible with 0.23+. The project is greenfield for tree-sitter; adopt current API.

### Decision: Graceful degradation on parse failure

**Choice**: Return `DFGResult(success=False)` with empty edges; `GraphCodeBERTInference` falls back to text-only `[CLS]` embedding with zero position indices.
**Rationale**: Student code may not parse. The proposal mandates no crashes; Canal B must still produce results independently.

### Decision: Fusion asymmetric cosine via zero-padding

**Choice**: Reference vectors are `sem_ref (768) || zeros(1024)` → their norm equals `||sem_ref||` alone. Student vectors are full `sem (768) || style (1024)` → inflated norm penalizes synthetic style.
**Rationale**: Matches proposal exactly. Simpler than learned fusion; no training data needed for Canal A.

### Decision: GraphCodeBERT loaded via HuggingFace transformers

| Option | Tradeoff | Decision |
|--------|----------|----------|
| A) Manual model download to `modelos/weights/` | Offline-first, but complex | Defer |
| B) `AutoModel.from_pretrained("microsoft/graphcodebert-base")` | Auto-caches in `~/.cache`; simplest | **Yes** |

**Rationale**: `CharCNNInference` loads from local checkpoint. For GraphCodeBERT, HuggingFace cache is standard; we can add local-path override later if needed.

## Data Flow

```
                          models/graphcodebert/           models/
                    ┌─────────────────────────┐    ┌──────────────┐
  source.c ────────▶│  DFGExtractor           │    │              │
  source.cpp        │   ├─ parse_file()       │    │              │
                    │   │   └─ tree-sitter    │    │              │
                    │   ├─ parse_code()       │    │              │
                    │   └─ DFG_c_cpp()  ◀─────┼────┤  (upstream   │
                    │       (recursive walk)   │    │   Guo et al. │
                    │       └─ DFGResult       │    │   DFG rules) │
                    ├─────────────────────────┤    │              │
                    │  GraphCodeBERTInference  │    │              │
                    │   ├─ predict(file)      │    │              │
                    │   ├─ predict_code(str)  │    │              │
                    │   ├─ _build_graph_input │    │              │
                    │   └─ _extract_embedding  │    │              │
                    │       └─ 768-dim vec    │    │              │
                    └──────────┬──────────────┘    │              │
                               │                   │              │
                               ▼                   ▼              │
                    ┌──────────────────────────────────────┐      │
                    │  BimodalFusion                        │      │
                    │   ├─ fuse() → 1792-dim vector        │      │
                    │   ├─ similarity() → asymmetric cos   │      │
                    │   └─ compare() → ranked results      │      │
                    └──────────────────────────────────────┘      │
                                                                  │
  CharCNN ─── 1024-dim style embedding ───────────────────────────┘
```

## Sequence: predict(file) end-to-end

```
Caller          DFGExtractor        GraphCodeBERTInf     HuggingFace
  │                │                      │                    │
  │─predict(path)──▶                      │                    │
  │               │─parse_file(path)─▶    │                    │
  │               │  tree-sitter AST      │                    │
  │               │─DFG_c_cpp()─────▶    │                    │
  │               │  recursive walk       │                    │
  │               │◀─DFGResult────────    │                    │
  │               │                      │                    │
  │               │─code_tokens,dfg──────▶                    │
  │               │                      │─tokenize(BPE)──────▶
  │               │                      │◀─input_ids──────────
  │               │                      │─build positions/attn│
  │               │                      │─forward pass────────▶
  │               │                      │◀─[CLS] 768-dim──────
  │◀─{embedding, dfg_node_count, success}│                    │
```

## Sequence: fuse() + similarity()

```
Caller         BimodalFusion       GCBI              CharCNNI
  │                │                  │                  │
  │─fuse(path)────▶                  │                  │
  │               │─predict(path)────▶                  │
  │               │◀─768-dim sem─────│                  │
  │               │─predict(path)───────────────────────▶│
  │               │◀─1024-dim style──────────────────────│
  │               │ concat: [sem|style] → 1792-dim      │
  │◀─FusionResult─│                  │                  │
  │                │                  │                  │
  │─similarity(student, ref)──▶       │                  │
  │  student = [sem_s(768) | style_s(1024)]              │
  │  ref     = [sem_r(768) | zeros(1024)]               │
  │  cos = (sem_s · sem_r) / (||student|| × ||ref||)    │
  │◀─float─────────│                  │                  │
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `models/graphcodebert/__init__.py` | Create | Public API exports: `DFGExtractor`, `GraphCodeBERTInference`, `GraphCodeBERTConfig` |
| `models/graphcodebert/config.py` | Create | `GraphCodeBERTConfig` dataclass (model_name, max_tokens, device) |
| `models/graphcodebert/parser.py` | Create | `DFGExtractor` class + `DFG_c_cpp()` function + dataclasses (`DFGEdge`, `DFGResult`) |
| `models/graphcodebert/inference.py` | Create | `GraphCodeBERTInference` class mirroring `CharCNNInference.predict()` interface |
| `models/fusion.py` | Create | `BimodalFusion` class + dataclasses (`FusionResult`, `ComparisonResult`) |
| `data/requirements.txt` | Modify | Add: `tree-sitter`, `tree-sitter-c`, `tree-sitter-cpp`, `transformers` |

## Interfaces / Contracts

### Data Structures

```python
@dataclass
class DFGEdge:
    source_indices: list[int]   # token positions of RHS vars
    target_index: int           # token position of LHS var
    relation: str               # "computedFrom" | "lastUse" | "lastWrite" | "comesFrom"

@dataclass
class DFGResult:
    code_tokens: list[str]
    dfg_edges: list[DFGEdge]
    index_to_code: dict[int, tuple[str, str]]  # idx → (token, node_type)
    success: bool

@dataclass
class FusionResult:
    semantic_embedding: list[float]    # 768-dim
    style_embedding: list[float]       # 1024-dim
    fused_vector: list[float]          # 1792-dim = [sem | style]
    prob_sintetico: float
    is_synthetic: bool

@dataclass
class ComparisonResult:
    reference_path: Path
    similarity: float                  # asymmetric cosine
    semantic_similarity: float         # cos(sem_s, sem_r)
    style_penalty: float               # ||fused_student|| / ||sem_student||
```

### Public Interfaces

```python
class DFGExtractor:
    def __init__(self) -> None
    def parse_file(self, file_path: Path) -> DFGResult
    def parse_code(self, code: str, language: str = "c") -> DFGResult

class GraphCodeBERTInference:
    def __init__(self, model_name: str = "microsoft/graphcodebert-base",
                 device: torch.device | None = None) -> None
    def predict(self, file_path: Path) -> dict
        # Returns: {"embedding": list[float], "language": str,
        #           "dfg_node_count": int, "success": bool}
    def predict_code(self, code: str, language: str = "c") -> dict

class BimodalFusion:
    def __init__(self, graphcodebert: GraphCodeBERTInference,
                 charcnn: CharCNNInference) -> None
    def fuse(self, code_path: Path) -> FusionResult
    def similarity(self, student_fused: FusionResult,
                   reference_fused: FusionResult) -> float
    def compare(self, student_path: Path,
                reference_paths: list[Path]) -> list[ComparisonResult]
```

### Config

```python
@dataclass
class GraphCodeBERTConfig:
    model_name: str = "microsoft/graphcodebert-base"
    max_tokens: int = 512          # BPE max input length
    embedding_dim: int = 768       # [CLS] output dimension
    device: str | None = None      # None = auto-detect CUDA/CPU
```

### DFG_c_cpp: Tree-sitter node types handled

| Node type (C) | Node type (C++) | DFG action |
|---|---|---|
| `declaration` | `declaration` | Record var definition |
| `init_declarator` | `init_declarator` | Emit `computedFrom` from RHS → LHS |
| `assignment_expression` | `assignment_expression` | Emit `computedFrom` RHS → LHS |
| `update_expression` | `update_expression` | Self-loop `computedFrom` |
| `for_statement` | `for_statement` | Walk body twice (loop-carried deps) |
| `while_statement` | `while_statement` | Walk body twice |
| `if_statement` | `if_statement` | Copy states per branch, merge |
| `parameter_declaration` | `parameter_declaration` | Record as definition |
| `call_expression` | `call_expression` | Arguments are uses |
| `return_statement` | `return_statement` | Returned var is a use |
| `identifier` | `identifier` | Leaf token extraction |

## Graph-Aware Input Construction (`_build_graph_aware_input`)

```
Step 1: BPE tokenize code_tokens
        code_tokens: ["int", "x", "=", "y", "+", "1", ";"]
        subtoken_ids: [[321],[1294],[45],[9823],[67],[22],[5]]
        subtoken_map: {0→[0], 1→[1], 2→[2], 3→[3], 4→[4], 5→[5], 6→[6]}

Step 2: Build position_ids (code=2..n+1, DFG=0)
        input_ids = [CLS] + subtoken_ids + [SEP] + [UNK]*dfg_nodes
        position_ids = [1, 2, 3, ..., n+1, 2, 3, ..., n+1, 0, 0, ..., 0]

Step 3: DFG→code mapping (which subtokens each DFG node maps to)
        dfg_to_code: {dfg_0: [sub_1, sub_3], dfg_1: [sub_5], ...}

Step 4: Attention mask
        - Code tokens: attend to ALL code tokens
        - DFG nodes: attend to their source code tokens + connected DFG nodes
        - Build from adjacency: attn_mask[i][j] = 1 if connected

Step 5: Forward pass
        - DFG node embeddings replaced with avg(code_token_embeddings)
        - Take [CLS] output as 768-dim semantic embedding
```

## Asymmetric Cosine Algorithm

```
fused_student = [sem_student(768) | style_student(1024)]
fused_ref     = [sem_reference(768) | zeros(1024)]

numerator   = sem_student · sem_reference
||fused_student|| = sqrt(sum(sem²) + sum(style²))   ← inflated by style
||fused_ref||   = sqrt(sum(sem_ref²))                ← style contributes nothing

similarity = numerator / (||fused_student|| × ||fused_ref||)

style_penalty = ||fused_student|| / ||sem_student||
  → > 1.0 when style is non-zero (synthetic code has distinctive style patterns)
  → Penalizes denominator without helping numerator
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | `DFG_c_cpp` recursion: declarations, assignments, loops, branches | pytest with inline C snippets, assert edge count/targets |
| Unit | `DFGExtractor` language detection from `.c`/`.cpp` extensions | pytest with temp files |
| Unit | `_build_graph_aware_input` position_ids and attn_mask shape | pytest with known DFG edges |
| Unit | Asymmetric cosine math | pytest with hand-computed vectors |
| Integration | `GraphCodeBERTInference.predict()` returns 768-dim vector | pytest with small C file |
| Integration | `BimodalFusion.fuse()` returns 1792-dim vector | pytest mocking both inferences |
| Integration | Parse failure → graceful degradation (no crash) | pytest with invalid C code |
| E2E | `compare()` ranks original above paraphrased | pytest with fixture files |

## Migration / Rollout

No migration required. All code is additive:
1. Install deps: `pip install tree-sitter tree-sitter-c tree-sitter-cpp transformers`
2. New modules in `models/graphcodebert/` and `models/fusion.py`
3. Canal B (`models/char_cnn/`) untouched
4. Rollback: delete new files + revert `requirements.txt`

## Open Questions

- [ ] Should `GraphCodeBERTInference` support loading from a local path (e.g., `modelos/weights/graphcodebert/`) for offline environments, or is HuggingFace cache sufficient for v1?
- [ ] Should `BimodalFusion.compare()` sort results by similarity descending, or return raw order?
