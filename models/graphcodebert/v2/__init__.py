"""GraphCodeBERT v2: upstream-faithful DFG input for C/C++ (zero-shot, no adapter).

A port of the upstream GraphCodeBERT data-flow walker, feature builder, attention mask and model
forward (microsoft/CodeBERT, vendored under `tests/reference/graphcodebert/`) to tree-sitter
C/C++. The legacy pipeline in `models.graphcodebert` stays frozen. Submodules are imported
explicitly (no re-exports) so importing the package stays cheap and side-effect free.
"""
