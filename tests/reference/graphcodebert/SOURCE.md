# Upstream GraphCodeBERT reference (read-only)

Read-only copies of the upstream GraphCodeBERT clone-detection code, used only as an oracle by
the golden tests. Production code never imports them, and pytest never collects or imports them
as test modules: `harness.py` (local, not upstream) reads their source and extracts the few
functions the tests need.

- Repository: https://github.com/microsoft/CodeBERT
- Commit: c0de43d3aaf38e89290f1efb771f8de845e7a489 (head of `master`, committed 2023-07-09)
- Retrieved: 2026-10-10
- License: MIT (`LICENSE`, copied from the repository root). Copyright (c) Microsoft Corporation.

## Vendored files

Byte-identical to upstream at the commit above. Do not edit them; `.gitattributes` disables
line-ending conversion so the hashes hold on every checkout.

| Local path | Upstream path | sha256 |
|---|---|---|
| `parser/DFG.py` | `GraphCodeBERT/clonedetection/parser/DFG.py` | `39a71a0be6d481443b13ca25709393a650b1b00c741d7187dd559a353489eb31` |
| `parser/utils.py` | `GraphCodeBERT/clonedetection/parser/utils.py` | `4a97a56b26787b0c38d7aae4a945369838cb7c7897db99a225dd68630d61e4e4` |
| `clonedetection/run.py` | `GraphCodeBERT/clonedetection/run.py` | `55b66f9aee9215c1699f02f4ae22086584f3616d4cd0dd32a83a68c5906b051c` |
| `clonedetection/model.py` | `GraphCodeBERT/clonedetection/model.py` | `a03b0d6efefc0ea2ec275f1a1f3f0848592cfadb4742c29fb57d20a0b12e63fe` |
| `LICENSE` | `LICENSE` | `7c77a44a8acd9b41fdc209864a8016b3d430b5d0e09309818d5b7444336df744` |

Raw URLs: `https://raw.githubusercontent.com/microsoft/CodeBERT/<commit>/<upstream path>`.

`clonedetection/model.py` was retrieved on 2026-10-11 from the same commit (encoder-forward
golden test).

- `model.py` passes the 3D boolean mask straight to `encoder.roberta`; transformers 4.x
  expanded it to a 4D additive mask (`0` / `finfo.min`). transformers 5.14 raises on a 3D
  mask, so the golden test wraps `.roberta` with that 4.x conversion.

## Facts the v2 port relies on

- Truncation constant `k = 3`: `convert_examples_to_features` truncates code subtokens to
  `code_length + data_flow_length - 3 - min(len(dfg), data_flow_length)`, then to `[:512 - 3]`.
- Comments are removed by `remove_comments_and_docstrings`; `extract_dataflow` sorts the walker
  output by token index and keeps only nodes that have parents or are someone's parent.
- Upstream has no C/C++ walker. The golden tests run `DFG_java` on tree-sitter C/C++ trees
  through the `JavaView` proxy in `harness.py`.

## Local (non-upstream) files

- `SOURCE.md`, `.gitattributes`: this provenance record.
- `harness.py`: test helpers (integrity check, AST extraction, `JavaView`).
