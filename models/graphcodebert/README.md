# GraphCodeBERT — Graphito semantic channel (Channel A)

`microsoft/graphcodebert-base` (RoBERTa-base, 125M parameters, frozen) turns a C/C++ submission
into a 768-d semantic embedding guided by its data-flow graph (DFG). The bimodal fusion
(`models/fusion.py`) combines it with the CharCNN style embedding; Channel A compares submissions
against references by cosine similarity. The teacher makes the final call.

Two input pipelines coexist behind one facade. The deployed default is still the **legacy**
encoding; the **v2** pipeline in `models/graphcodebert/v2/` is the upstream-faithful replacement.
Switching the default is a decision for SDD-4, because every vector stored in Chroma must be
re-encoded with the new pipeline.

## Pipelines

| | legacy (frozen) | v2 (`INPUT_VERSION = "v2"`) |
|---|---|---|
| Code | `legacy_inference.py` (`LegacyGraphCodeBERTInference`), `parser.py` | `v2/` (`dfg.py`, `encode.py`, `windows.py`, `model.py`, `embed.py`) |
| DFG | hand-written C/C++ extractor | port of upstream `DFG_java` to the tree-sitter C/C++ grammars (`WALKER_VERSION = "c-cpp-2"`), extracted once per file |
| Input | hand-built embeddings, line chunking, legacy DFG mask | upstream `convert_examples_to_features` and graph-guided attention mask, statement for statement |
| Long files | chunks; `code[:2000]` fallback | sliding windows over subtokens (below) |
| Pooling | `[CLS]` | `cls` or `mean`, per window, then averaged over windows |
| Adapter | MLM LoRA only for the labelled baseline | never |

The legacy code moved verbatim from the pre-v2 `GraphCodeBERTInference`; it only serves the
frozen backend default and the labelled `legacy` baseline and is not edited.

## v2 input and masking

Sequence layout (length `code_length + data_flow_length` = 384 + 128 = 512):

```
[CLS] code subtokens [SEP] | DFG nodes (id unk, position 0) | padding (id pad, position 1)
```

- Code positions start at `pad_token_id + 1` (2 for RoBERTa). A node's input embedding is the
  mean of the word embeddings of its aligned code subtokens.
- The attention mask is upstream's graph-guided mask: code subtokens attend to each other,
  CLS/SEP attend to everything, a node and its aligned code subtokens attend to each other, and a
  node attends to its DFG parents. It is applied as a 4D additive mask with eager
  attention in fp32 (the only verified combination).
- Node budget: `code_length + data_flow_length - len(CLS + code + SEP)`, so a short file can carry
  more than 128 nodes, as upstream does.
- Comments are stripped before parsing. Files with tree-sitter error nodes are still encoded; the
  DFG is extracted from the valid parts and the result is flagged `parse_errors`.
- C/C++ deviations from the Java walker are listed in the `v2/dfg.py` docstring (per-function
  state reset, `do` and `switch` handling, compound assignments, `primitive_type` leaves, ...).

## Windows

- A file whose subtokens fit the upstream dynamic budget gets exactly one upstream input,
  bit-identical to `run.py`.
- Otherwise windows of 382 code subtokens (384 with CLS/SEP) start every 191 subtokens; the last
  window ends at the last subtoken. Windowing never splits by lines.
- More than 16 windows are replaced by 16 evenly spaced starts and the file is marked `truncated`.
- Each window keeps the nodes whose code span lies fully inside it (cut to the node budget);
  parents outside the window are dropped.
- The `v2_nodfg` ablation plans the same windows and then drops every node, so both variants see
  the same code.

## Pooling

Per window, `cls` is the hidden state at position 0 and `mean` averages the code subtoken positions
only (no CLS, SEP, nodes or padding). The file embedding is the unweighted mean of the window
poolings. The evaluation chooses the pooling per method on val PR-AUC (ties by MAP@R, then `cls`);
in the committed run it picked `mean` for v2 and `v2_nodfg`. The facade default
(`GraphCodeBERTConfig.pooling`) is still `cls`; set it explicitly when using v2.

## Inference facade

```python
from models.graphcodebert.config import GraphCodeBERTConfig
from models.graphcodebert.inference import GraphCodeBERTInference

gcb = GraphCodeBERTInference()                                            # legacy (default)
gcb_v2 = GraphCodeBERTInference(GraphCodeBERTConfig(input_version="v2", pooling="mean"))
result = gcb_v2.predict_code("int main() { ... }", language="c")
```

`GraphCodeBERTConfig.input_version` selects the pipeline: `"legacy"` (default until SDD-4) or
`"v2"`. The v2 fields (`pooling`, `use_dfg`, `code_length`, `data_flow_length`, `max_windows`,
`attn_implementation`) are validated at construction.

Every result has the legacy keys (`embedding`, `language`, `code_tokens_count`, `dfg_node_count`,
`success`, `used_graph`) plus `dfg_nodes_used`, `n_windows`, `input_version`, `pooling`,
`adapter_loaded` (always `False`), `truncated` and `parse_errors`. On v2, `used_graph` is true only
if at least one DFG node was placed, and a failure gives `success=False` with `embedding=[]`. On
legacy, `truncated` may be `None` (a loss cannot be ruled out for chunked files).

**Adapter policy.** The facade never loads the LoRA adapter and never imports `peft`:
`adapter_path` has no default, and an explicit path is ignored with a `WARNING`. Only
`LegacyGraphCodeBERTInference(load_adapter=True)` loads it (the configured path, or the shipped
`adaptador-lora-20k`), and only the evaluation's labelled `legacy` baseline uses that entry point.

## Integration with Channel B

```python
from models.graphcodebert.inference import GraphCodeBERTInference
from models.fusion import BimodalFusion

gcb = GraphCodeBERTInference()
fusion = BimodalFusion(gcb, charcnn_engine)

# Fuse a student submission
result = fusion.fuse(Path("entrega.c"))
# -> FusionResult with a 1792-d fused_vector = [sem(768) | style(1024)]

# Compare against references
results = fusion.compare(student_path, reference_paths)
# -> asymmetric similarity: penalizes synthetic code in the denominator
```

`models/fusion.py` is unchanged; it uses whatever pipeline the facade's config selects (legacy by
default).

## Evaluation CLI

```
python -m models.graphcodebert.v2.evaluate --manifest data/splits/split_v1.json.gz \
    --expected-sha256 <sha> --device cuda --local-files-only --n-boot 1000
```

Run from the repository root. It scores labelled human pairs of `val` and `test` (within
assignment only; ambiguous and unlabeled entries excluded and counted) with five methods: `v2`,
`v2_nodfg`, `jaccard` (5-token shingles), `winnowing` (k=5, w=4) and `legacy` (frozen pipeline
with its MLM adapter; `skipped` with a reason when it cannot be built). Stages run in order and
test is touched once: val scoring, selection (pooling, val thresholds at the default FPR targets on
raw scores, an isotonic `calibration.json` of the selected v2 cosine for SDD-4 only), test scoring
and metrics (bootstrap by assignment), report. Views: `all` and `no_identical` (label-0 pairs whose
normalized code is identical dropped).

| Flag | Default |
|---|---|
| `--manifest` | `data/splits/split_v1.json.gz` |
| `--expected-sha256` | none (checked when given) |
| `--root` | `.` (file bytes must match the manifest sha256) |
| `--runs-root` | `runs` |
| `--device` | auto |
| `--batch-size` | 16 |
| `--seed` | 42 |
| `--n-boot` | 1000 |
| `--methods` | `v2,v2_nodfg,jaccard,winnowing,legacy` |
| `--model` | `microsoft/graphcodebert-base` |
| `--cache-dir` | `<runs-root>/graphcodebert/_cache` |
| `--no-cache` | off (memory-only cache) |
| `--local-files-only` | off (refuse if the model is not in the local HF cache) |
| `--limit-assignments N` | off (debug: first N assignments per split) |

| Exit code | Meaning |
|---|---|
| 0 | complete |
| 1 | refused; nothing written (manifest or file sha mismatch, unknown method, model not loadable) |
| 2 | argparse usage error |
| 3 | run failed; `config.json` status `failed` with stage and reason |

## Run layout

```
runs/graphcodebert/<ts>/
  config.json          provenance (git sha, manifest sha256, package versions, model revision, device), status
  selection.json       val candidates and chosen pooling per method
  thresholds_val.json  val thresholds per method and FPR target (raw scores)
  calibration.json     isotonic fit of the selected v2 cosine on val (for SDD-4; no metric uses it)
  <method>__<view>/    metrics.json, report.md, roc/pr plots, roc.csv.gz / pr.csv.gz (thinned to <= 2000 points)
  summary.json         test headline per method and view
  data_summary.json    pair counts, exclusions, parse-error/truncation rates, cache stats
  report.md            root report
runs/graphcodebert/_cache/<cache_key>/<sha[:2]>/<sha256>.npz
```

**Cache.** `cache_key` is the sha256 of the embedder's key fields (`input_version`,
`walker_version`, `variant`, `model_revision`, budgets, `max_windows`, `dtype`, ...); any change
gives a new key directory. Entries are keyed by the sha256 of the file bytes (duplicates share one
entry), store every pooling (`cls` and `mean` for v2), are written atomically, and failed
embeddings are cached too. `runs/` is gitignored; selected reports are committed explicitly.

## Results

Committed reports: `runs/graphcodebert/20261011-082155/` (JSON, Markdown and plots; no curve CSVs,
caches or embeddings). Run: `split_v1` (manifest sha256 `e835362d…`), seed 42, CUDA (RTX 2060
SUPER), transformers 5.14, tree_sitter 0.26, model revision `2b0488a7`, 1,000 bootstrap resamples
of assignments, 0 embedding failures. Zero-shot: no weights were trained.

| Split | Files | Assignments | Pairs | Positives |
|---|---|---|---|---|
| val | 5,089 | 9 | 1,595,275 | 174 |
| test | 6,797 | 14 | 1,908,545 | 338 |

Excluded test entries: 147 ambiguous and 2,374 unlabeled files. Chance PR-AUC on test is about
0.00018. The `no_identical` view drops 62,487 test negatives. Pooling selected on val: v2 `mean`
(val PR-AUC 0.00073 vs `cls` 0.00057), `v2_nodfg` `mean`, legacy `cls`.

Test, view `all`:

| Method | ROC-AUC [CI95] | PR-AUC [CI95] | MAP@R [CI95] |
|---|---|---|---|
| Jaccard (5-token shingles) | 0.945 [0.930, 0.964] | 0.0019 [0.0008, 0.0048] | 0.374 [0.195, 0.533] |
| Winnowing | 0.944 [0.930, 0.962] | 0.0019 [0.0008, 0.0048] | 0.385 [0.200, 0.548] |
| GraphCodeBERT v2 (mean) | 0.856 [0.796, 0.893] | 0.0015 [0.0003, 0.0051] | 0.295 [0.145, 0.413] |
| v2 without DFG (mean) | 0.851 [0.788, 0.889] | 0.0009 [0.0003, 0.0025] | 0.291 [0.145, 0.412] |
| Legacy (CLS, MLM adapter) | 0.741 [0.653, 0.800] | 0.0004 [0.0002, 0.0010] | 0.168 [0.075, 0.250] |

Test, view `no_identical`:

| Method | ROC-AUC [CI95] | PR-AUC [CI95] | MAP@R [CI95] |
|---|---|---|---|
| Jaccard | 0.975 [0.967, 0.983] | 0.047 [0.021, 0.303] | 0.549 [0.416, 0.686] |
| Winnowing | 0.974 [0.966, 0.982] | 0.044 [0.021, 0.269] | 0.557 [0.421, 0.694] |
| GraphCodeBERT v2 (mean) | 0.883 [0.822, 0.917] | 0.128 [0.043, 0.217] | 0.432 [0.319, 0.546] |
| v2 without DFG (mean) | 0.879 [0.817, 0.915] | 0.130 [0.043, 0.219] | 0.436 [0.329, 0.554] |
| Legacy | 0.765 [0.666, 0.830] | 0.037 [0.018, 0.076] | 0.256 [0.165, 0.340] |

Operating points (thresholds fitted on val raw similarity, applied once to test, view `all`): at
the 5% FPR target Jaccard reaches recall 0.61 at FPR 3.6%, while v2 reaches recall 0.25 at FPR 3.3%
with a threshold of 0.998, because zero-shot cosines are saturated near 1. The 1% FPR target is
unachievable or gives recall about 0 for every method.

Embedding statistics (val + test): v2 parse-error rate 25% (tree-sitter error nodes; the DFG is
still extracted from the valid parts), truncation 11% with DFG and 3.6% without, 4.7 windows per
file on average.

**How to read these numbers.**

- **Negative result.** Zero-shot GraphCodeBERT does not beat simple lexical baselines on ROC-AUC or
  MAP@R. It has a higher PR-AUC only in the `no_identical` view, and the CIs overlap widely. Its
  cosines are saturated, so usable thresholds barely separate the classes.
- The faithfully implemented DFG adds no measurable benefit zero-shot: v2 and `v2_nodfg` are within
  each other's CIs on every metric.
- The correct implementation clearly improves on the legacy pipeline (ROC-AUC 0.741 -> 0.856).
  Legacy is a labelled baseline with its MLM adapter; it is not comparable with earlier reports.
- Label noise: ground-truth negatives include identical and near-identical code (hence the
  `no_identical` view). Positives are extremely rare and there are only 14 test assignments, so
  the CIs are wide.
- Implication: plagiarism similarity needs task-specific training (Phase 2: contrastive fine-tuning
  on plagiarism clusters) or lexical features. SDD-4 should decide the operational Channel A score.

## Vendored reference

`tests/reference/graphcodebert/` holds byte-identical, read-only copies of upstream
`GraphCodeBERT/clonedetection` (`parser/DFG.py`, `parser/utils.py`, `run.py`, `model.py`, MIT
license) from microsoft/CodeBERT commit `c0de43d`. They are the oracle of the golden tests;
production code never imports them. Provenance and hashes are in its `SOURCE.md`.

## Deprecations

- `contrastive_graphcodebert.py` and `fine_tune_graphcodebert.py` still use the legacy encoding.
  The shipped MLM LoRA adapter they produced was shown to hurt (AUC 0.646 -> 0.630 in the old
  benchmark), which is why the facade no longer loads it. Phase 2 replaces both with contrastive
  fine-tuning on the v2 input.
- `parser.py` (`DFGExtractor`) only serves the legacy pipeline; v2 uses `v2/dfg.py`.

## Dependencies

```
tree-sitter
tree-sitter-c
tree-sitter-cpp
transformers
torch
```

`peft` is needed only for the labelled legacy baseline. The model (~500 MB) is downloaded on first
use into the Hugging Face cache (or `GraphCodeBERTConfig.cache_dir`); the evaluation can run with
`--local-files-only`.

## Limitations

- GraphCodeBERT was pre-trained on Python, Java, JavaScript, Go, Ruby and PHP, not C/C++; the
  embeddings are cross-lingual zero-shot. Upstream has no C/C++ DFG walker; v2 ports the Java one.
- The DFG is syntactic: no pointer aliasing; `switch` cases are over-approximated (each case starts
  from the post-condition states and fallthrough is not modelled).
- Only eager attention in fp32 is supported (fp16 needs a parity test first).
- Files longer than 16 windows are sampled, not fully encoded (`truncated`).
- Labels are noisy and test has only 14 assignments; see Results.
- The default facade path is still legacy; switching to v2 requires reindexing Chroma (SDD-4).
