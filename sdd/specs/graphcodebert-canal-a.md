# GraphCodeBERT Canal A — Delta Specs

## DFG Extractor (`dfg-extractor`)

**What**: Extracts Data Flow Graph (def-use chains) from C/C++ source via tree-sitter AST.

**Input**: `.c`/`.cpp` file path or raw source string.

**Output**: DFG edges `[(from_idx, to_idx)]`, token strings `["int","x",...]`, and `parse_status: "ok"|"fallback"`.

### Scenarios

- **Scenario**: Variable declaration and assignment
  - **Given**: `int x = 5;\nint y = x + 3;`
  - **When**: DFG extraction runs
  - **Then**: Edges: `(decl_x, init_x)`, `(decl_y, x→y)`; tokens: all identifiers and literals indexed; parse_status=`ok`

- **Scenario**: Function parameters and return
  - **Given**: `int add(int a, int b) {\n  return a + b;\n}`
  - **When**: DFG extraction runs
  - **Then**: Edges connect `a` and `b` to return expression; parse_status=`ok`

- **Scenario**: For-loop with update
  - **Given**: `for (int i = 0; i < n; i++) {\n  sum += i;\n}`
  - **When**: DFG extraction runs
  - **Then**: Edges: `(decl_i, init_0)`, `(decl_i, use_i<n)`, `(decl_i, use_i++)`, `(decl_i, use_sum+=i)`; parse_status=`ok`

- **Scenario**: If-else branches
  - **Given**: `if (x > 0) {\n  y = x;\n} else {\n  y = -x;\n}`
  - **When**: DFG extraction runs with `x` in outer scope
  - **Then**: Edges connect `x` use to both branches; `y` in each branch has edge from its RHS expression

- **Scenario**: Malformed code fallback
  - **Given**: `int x = ;` (invalid syntax)
  - **When**: DFG extraction runs
  - **Then**: parse_status=`fallback`, DFG edges=`[]`, tokens contain whatever could be lexed; MUST NOT raise

## GraphCodeBERT Inference (`graphcodebert-inference`)

**What**: Produces 768-dim semantic embedding via `microsoft/graphcodebert-base` in feature-extraction mode.

**Input**: `predict(file: Path)` or `predict_text(code: str)`.

**Output**: `{"embedding": [768 floats], "parse_status": "ok"|"fallback"}`.

### Scenarios

- **Scenario**: Valid file produces 768-dim embedding
  - **Given**: `example.c` = `int main() { return 0; }`, DFG succeeds
  - **When**: `predict(Path("example.c"))`
  - **Then**: `embedding` len=768; all values in [-1, 1]; parse_status=`ok`

- **Scenario**: Deterministic output
  - **Given**: `code = "int x = 42;"` with successful DFG
  - **When**: `predict_text(code)` called twice
  - **Then**: Both calls return bit-exact same `embedding` vector

- **Scenario**: DFG fallback produces text-only embedding
  - **Given**: Unparseable code string
  - **When**: `predict_text(code)`
  - **Then**: `embedding` len=768; parse_status=`fallback`; attention mask has no DFG edges, token type ids all zero

- **Scenario**: Truncation at 514 token limit
  - **Given**: `.c` file with 800+ tokens
  - **When**: `predict(file)`
  - **Then**: Tokens truncated to 512 (+[CLS]/[SEP]=514); DFG runs on full input first; warning logged

- **Scenario**: Interface matches CharCNNInference
  - **Given**: Loaded checkpoint
  - **When**: `GraphCodeBERTInference.__init__(checkpoint_path, config, device)` is called
  - **Then**: Constructor signature mirrors `CharCNNInference`; exposes `predict(Path)` and `predict_text(str)` returning dict

## Bimodal Fusion (`bimodal-fusion`)

**What**: Concatenates Canal A (semantic 768-dim) + Canal B (style 1024-dim) and computes asymmetric cosine similarity.

**Input**: Two tuples `(sem: [float], sty: [float]|None)`. Second tuple `sty` may be `None` (reference code).

**Output**: `{"similarity": float, "semantic_sim": float, "style_sim": float|null}`.

### Scenarios

- **Scenario**: Student-to-reference with zero-padded reference
  - **Given**: Student `([s1..s768], [t1..t1024])`, reference `([r1..r768], None)`
  - **When**: `compute_similarity(student, reference)`
  - **Then**: `similarity` = dot(sem_s, sem_r) / (||full_s|| * ||sem_r||); `semantic_sim` = cos(sem_s, sem_r); `style_sim` = null

- **Scenario**: Student-to-student symmetric fusion
  - **Given**: Two students with full 1792-dim vectors
  - **When**: `compute_similarity(A, B)`
  - **Then**: `similarity` = cos(full_A, full_B); `semantic_sim` = cos(sem_A, sem_B); `style_sim` = cos(sty_A, sty_B); all in [0, 1]

- **Scenario**: Reference-to-reference
  - **Given**: Two references, both `style=None`
  - **When**: `compute_similarity(A, B)`
  - **Then**: `similarity` = `semantic_sim` = cos(sem_A, sem_B); `style_sim` = null; denominators use semantic magnitude only

- **Scenario**: Identity check
  - **Given**: Two identical 1792-dim vectors
  - **When**: `compute_similarity(vec, vec)`
  - **Then**: All similarity scores = 1.0 within 1e-6 tolerance
