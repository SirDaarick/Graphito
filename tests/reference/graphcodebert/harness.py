"""Test-only helpers around the vendored upstream GraphCodeBERT reference (local, not upstream).

The vendored files are never imported as modules: `run.py` loads tree-sitter grammars and other
modules at import time, and `DFG.py` uses a relative import. Instead, the functions the golden
tests need are extracted from the source with `ast` and executed in an injected namespace.

`JavaView` lets the vendored `DFG_java` walk a tree-sitter C/C++ tree: it renames the node types
and fields that differ between the grammars, flattens `else_clause`, and makes literals atomic.
"""

import ast
import hashlib
import importlib.util
import re
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Iterable

REF_DIR = Path(__file__).resolve().parent
VENDORED_FILES = ("parser/DFG.py", "parser/utils.py", "clonedetection/run.py", "clonedetection/model.py", "LICENSE")

_COMMIT_RE = re.compile(r"Commit:\s*([0-9a-f]{40})\b")
_HASH_ROW_RE = re.compile(r"^\|\s*`([^`]+)`\s*\|[^|]*\|\s*`([0-9a-f]{64})`\s*\|", re.MULTILINE)
_TRUNCATION_RE = re.compile(r"\[:512-(\d+)\]")


# --- integrity ----------------------------------------------------------------------------


def pinned_commit(ref_dir: Path = REF_DIR) -> str | None:
    """40-hex upstream commit recorded in `SOURCE.md`, or None."""
    source = Path(ref_dir) / "SOURCE.md"
    if not source.is_file():
        return None
    match = _COMMIT_RE.search(source.read_text(encoding="utf-8"))
    return match.group(1) if match else None


def recorded_hashes(ref_dir: Path = REF_DIR) -> dict[str, str]:
    """`{local path: sha256}` from the `SOURCE.md` table."""
    source = Path(ref_dir) / "SOURCE.md"
    if not source.is_file():
        return {}
    return dict(_HASH_ROW_RE.findall(source.read_text(encoding="utf-8")))


def check_reference(ref_dir: Path = REF_DIR) -> list[str]:
    """Problems with the vendored reference (empty when intact): missing files, LICENSE, commit or
    a sha256 mismatch against `SOURCE.md`."""
    ref_dir = Path(ref_dir)
    problems = []
    if not (ref_dir / "SOURCE.md").is_file():
        problems.append("SOURCE.md is missing")
    elif pinned_commit(ref_dir) is None:
        problems.append("SOURCE.md lacks a 40-hex upstream commit")
    hashes = recorded_hashes(ref_dir)
    for rel in VENDORED_FILES:
        path = ref_dir / rel
        if not path.is_file():
            problems.append(f"{rel} is missing")
        elif rel not in hashes:
            problems.append(f"{rel} has no sha256 recorded in SOURCE.md")
        elif hashlib.sha256(path.read_bytes()).hexdigest() != hashes[rel]:
            problems.append(f"{rel} differs from the recorded upstream sha256")
    return problems


def truncation_constant(ref_dir: Path = REF_DIR) -> int:
    """The `k` in run.py's `[:512-k]` code truncation."""
    match = _TRUNCATION_RE.search((Path(ref_dir) / "clonedetection" / "run.py").read_text(encoding="utf-8"))
    if match is None:
        raise ValueError("truncation constant not found in run.py")
    return int(match.group(1))


# --- AST extraction -----------------------------------------------------------------------


def _extract(rel: str, names: Iterable[str], namespace: dict[str, Any]) -> dict[str, Any]:
    """Execute the named top-level definitions (or `Class.method`) of a vendored file in
    `namespace` and return the namespace. Methods are bound to their bare method name."""
    path = REF_DIR / rel
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    top = {node.name: node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.ClassDef))}
    body = []
    for name in names:
        owner, _, method = name.partition(".")
        node = top[owner]
        if method:
            node = next(n for n in node.body if isinstance(n, ast.FunctionDef) and n.name == method)
        body.append(node)
    module = ast.Module(body=body, type_ignores=[])
    exec(compile(module, filename=str(path), mode="exec"), namespace)
    return namespace


def load_utils():
    """`parser/utils.py` as a module (it only imports `re`, `io` and `tokenize`)."""
    path = REF_DIR / "parser" / "utils.py"
    spec = importlib.util.spec_from_file_location("gcb_reference_utils", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_dfg_java() -> Callable:
    """Upstream `DFG_java(root_node, index_to_code, states)`."""
    utils = load_utils()
    ns = _extract("parser/DFG.py", ["DFG_java"], {"tree_to_variable_index": utils.tree_to_variable_index})
    return ns["DFG_java"]


def load_extract_dataflow() -> Callable:
    """Upstream `extract_dataflow(code, parser, lang)` from run.py (comment removal, tokens,
    walker call, sort and post-filter)."""
    utils = load_utils()
    ns = {
        "remove_comments_and_docstrings": utils.remove_comments_and_docstrings,
        "tree_to_token_index": utils.tree_to_token_index,
        "index_to_code_token": utils.index_to_code_token,
        "tree_to_variable_index": utils.tree_to_variable_index,
    }
    return _extract("clonedetection/run.py", ["extract_dataflow"], ns)["extract_dataflow"]


def load_run_reference(extract_dataflow: Callable) -> SimpleNamespace:
    """Upstream feature builder and mask with `extract_dataflow` injected.

    Returns `convert_examples_to_features(item)`, `getitem(dataset, i)` (the body of
    `TextDataset.__getitem__`, called with any object exposing `examples` and `args`) and
    `InputFeatures`.
    """
    import numpy as np
    import torch

    ns = {"np": np, "torch": torch, "parsers": {"java": None}, "extract_dataflow": extract_dataflow}
    _extract("clonedetection/run.py", ["InputFeatures", "convert_examples_to_features", "TextDataset.__getitem__"], ns)
    return SimpleNamespace(
        convert_examples_to_features=ns["convert_examples_to_features"],
        getitem=ns["__getitem__"],
        InputFeatures=ns["InputFeatures"],
    )


def load_upstream_model_class() -> type:
    """Upstream clone-detection `Model` (`clonedetection/model.py`): node embeddings as the mean
    of aligned code word embeddings, then `encoder.roberta(inputs_embeds, attention_mask,
    position_ids, token_type_ids)`, then a pair classifier."""
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    from torch.nn import CrossEntropyLoss

    ns = {"torch": torch, "nn": nn, "F": F, "CrossEntropyLoss": CrossEntropyLoss}
    return _extract("clonedetection/model.py", ["RobertaClassificationHead", "Model"], ns)["Model"]


# --- JavaView -----------------------------------------------------------------------------

# Literals that upstream treats as one token (Java `string` is a leaf there).
ATOMIC_TYPES = frozenset({"string_literal", "char_literal", "raw_string_literal", "system_lib_string"})
_TYPE_RENAMES = {"init_declarator": "variable_declarator", "for_range_loop": "enhanced_for_statement"}
_FIELD_RENAMES = {
    "variable_declarator": {"name": "declarator"},
    "enhanced_for_statement": {"name": "declarator", "value": "right"},
}


class JavaView:
    """Read-only proxy that presents a tree-sitter C/C++ node with Java grammar names.

    - `init_declarator` -> `variable_declarator` (`name` <- `declarator`),
    - `for_range_loop` -> `enhanced_for_statement` (`name` <- `declarator`, `value` <- `right`),
    - a `declaration` initializer of a `for_statement` -> `local_variable_declaration`,
    - `else_clause` is flattened into the `else` keyword plus its statement,
    - `primitive_type` reads as its keyword text (Java `int` is a keyword leaf),
    - string/char literals are atomic leaves.
    """

    __slots__ = ("node", "_type")

    def __init__(self, node, type_override: str | None = None):
        self.node = node
        self._type = type_override

    @property
    def type(self) -> str:
        if self._type is not None:
            return self._type
        if self.node.type == "primitive_type":
            return self.node.text.decode("utf-8")
        return _TYPE_RENAMES.get(self.node.type, self.node.type)

    @property
    def start_point(self) -> tuple[int, int]:
        return tuple(self.node.start_point)

    @property
    def end_point(self) -> tuple[int, int]:
        return tuple(self.node.end_point)

    @property
    def children(self) -> list["JavaView"]:
        if self.node.type in ATOMIC_TYPES:
            return []
        out = []
        for child in self.node.children:
            if child.type == "else_clause":
                out.extend(JavaView(c) for c in child.children)
            elif self.node.type == "for_statement" and child.type == "declaration":
                out.append(JavaView(child, "local_variable_declaration"))
            else:
                out.append(JavaView(child))
        return out

    def child_by_field_name(self, name: str):
        field = _FIELD_RENAMES.get(self.type, {}).get(name, name)
        child = self.node.child_by_field_name(field)
        return None if child is None else JavaView(child)


class _JavaViewParser:
    """Stands in for upstream's tree-sitter Java parser: parses C/C++ and returns a JavaView root."""

    def __init__(self, lang: str):
        import tree_sitter as ts

        if lang == "c":
            import tree_sitter_c as grammar
        else:
            import tree_sitter_cpp as grammar
        self._parser = ts.Parser(ts.Language(grammar.language()))

    def parse(self, source: bytes):
        tree = self._parser.parse(source)
        return SimpleNamespace(root_node=JavaView(tree.root_node))


def upstream_dataflow(code: str, lang: str = "c") -> tuple[list[str], list[tuple]]:
    """Upstream `extract_dataflow(code, [parser, DFG_java], 'java')` on a C/C++ snippet via
    `JavaView` (post-filtered nodes). Comment-free snippets only."""
    extract = load_extract_dataflow()
    return extract(code, [_JavaViewParser(lang), load_dfg_java()], "java")


def upstream_raw_dfg(code: str, lang: str = "c") -> tuple[list[str], list[tuple]]:
    """Upstream tokens and raw (unfiltered) `DFG_java` output on the same JavaView tree."""
    utils = load_utils()
    root = _JavaViewParser(lang).parse(bytes(code, "utf8")).root_node
    tokens_index = utils.tree_to_token_index(root)
    lines = code.split("\n")
    code_tokens = [utils.index_to_code_token(x, lines) for x in tokens_index]
    index_to_code = {index: (idx, tok) for idx, (index, tok) in enumerate(zip(tokens_index, code_tokens))}
    dfg, _ = load_dfg_java()(root, index_to_code, {})
    return code_tokens, dfg
