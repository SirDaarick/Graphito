"""Upstream-faithful GraphCodeBERT data-flow graph (DFG) for C/C++ (`WALKER_VERSION = "c-cpp-2"`).

A port of upstream `DFG_java` (microsoft/CodeBERT `GraphCodeBERT/clonedetection/parser/DFG.py`,
vendored in `tests/reference/graphcodebert/`) to the tree-sitter C and C++ grammars, plus the
`extract_dataflow` tokenization and post-filter of `run.py`.

Each node is `(code, idx, relation, parent_codes, parent_idxs)`: the variable occurrence at
`code_tokens[idx]` comes from (`comesFrom`) or is computed from (`computedFrom`) the occurrences at
`parent_idxs`. `states` maps a variable name to the indices of its last definitions.

On constructs shared with the Java walker (declarations, assignment, update, if/else, `for` with
a declaration initializer, while, range-for, return, calls) the output equals upstream
`DFG_java` on the same tree (golden test). Deliberate C/C++ deviations:

a. an `init_declarator` defines only its innermost identifier (`a[10]` does not define `10`);
b. states reset at each `function_definition` (globals declared before it persist);
c. the `for` second pass starts after the initializer of any kind (upstream: declarations only);
d. `do` (two passes, like `while`) and `switch` (each case from the post-condition states, union
   of all cases plus the post-condition) are handled;
e. zero-width (MISSING) nodes and comments are skipped; tokens are sliced by byte offsets;
f. an `else_clause` unions only the branch states (upstream also keeps the pre-if states);
g. a compound assignment (`x += y`) also reads the LHS: `x computedFrom` its previous
   definitions (itself when it has none) and the RHS variables (spec GD3.3);
h. `primitive_type` leaves (`int`, `char`, ...) are keywords, not variables;
i. parent code lists are aligned one-to-one with parent indices (upstream merges them with
   `list(set(...))` and repeats a single code for several leaf parents).
"""

import sys
from contextlib import contextmanager
from dataclasses import dataclass
from functools import lru_cache
from typing import Iterator

import tree_sitter as ts
import tree_sitter_c
import tree_sitter_cpp

from models.evaluation.normalize import strip_comments

WALKER_VERSION = "c-cpp-2"
LANGUAGES = ("c", "cpp")

# Literals kept as one token (upstream treats its `string` node as a leaf).
ATOMIC_TYPES = frozenset({"string_literal", "char_literal", "raw_string_literal", "system_lib_string"})
# Leaves that are keywords although their node type differs from their text.
KEYWORD_LIKE_TYPES = frozenset({"primitive_type"})
# Raised inside `extract_dfg_v2` only; deep expressions recurse once per tree level.
RECURSION_LIMIT = 20000

DfgNode = tuple  # (code: str, idx: int, relation: str, parent_codes: list[str], parent_idxs: list[int])
Key = tuple[int, int]  # (start_byte, end_byte) of a token leaf
IndexToCode = dict[Key, tuple[int, str]]


@dataclass(frozen=True)
class Dataflow:
    """DFG of one file. `dfg` is post-filtered (nodes with parents or that are someone's parent),
    sorted by `idx`; `n_nodes_raw` counts nodes before the filter. A walker failure leaves
    `dfg == []` with `dfg_error` set and the tokens intact."""

    code_tokens: list[str]
    dfg: list[DfgNode]
    parse_errors: bool
    dfg_error: str | None = None
    n_nodes_raw: int = 0

    @property
    def nodes(self) -> list[DfgNode]:
        return self.dfg


@lru_cache(maxsize=None)
def _parser(lang: str) -> ts.Parser:
    grammar = tree_sitter_c if lang == "c" else tree_sitter_cpp
    return ts.Parser(ts.Language(grammar.language()))


def prepare_source(code: str | bytes) -> bytes:
    """Decode (UTF-8, invalid bytes replaced), strip comments (string-aware), re-encode."""
    if isinstance(code, bytes):
        code = code.decode("utf-8", errors="replace")
    return strip_comments(code).encode("utf-8")


def parse_source(source: bytes, lang: str) -> ts.Tree:
    if lang not in LANGUAGES:
        raise ValueError(f"unsupported language {lang!r}; expected one of {LANGUAGES}")
    return _parser(lang).parse(source)


def _key(node: ts.Node) -> Key:
    return (node.start_byte, node.end_byte)


def _is_leaf(node: ts.Node) -> bool:
    return node.child_count == 0 or node.type in ATOMIC_TYPES


def _is_keyword(node: ts.Node, text: str) -> bool:
    return node.type == text or node.type in KEYWORD_LIKE_TYPES


def _same(a: ts.Node, b: ts.Node) -> bool:
    return _key(a) == _key(b) and a.type == b.type


def index_tokens(root: ts.Node, source: bytes) -> tuple[list[str], IndexToCode]:
    """Upstream `tree_to_token_index` (iterative): non-empty leaves and atomic literals in source
    order, without comments. Returns the token texts and `{(start_byte, end_byte): (idx, text)}`."""
    leaves = []
    stack = [root]
    while stack:
        node = stack.pop()
        if node.type == "comment":
            continue
        if _is_leaf(node):
            if node.end_byte > node.start_byte:
                leaves.append(node)
            continue
        stack.extend(reversed(node.children))
    tokens = [source[n.start_byte : n.end_byte].decode("utf-8", errors="replace") for n in leaves]
    index = {_key(n): (i, tok) for i, (n, tok) in enumerate(zip(leaves, tokens))}
    return tokens, index


def _by_idx(dfg: list[DfgNode]) -> list[DfgNode]:
    return sorted(dfg, key=lambda x: x[1])


class _Walker:
    """`DFG_java` ported to tree-sitter C/C++ (see the module docstring for deviations)."""

    def __init__(self, index: IndexToCode):
        self.index = index
        self.code_of = {idx: code for idx, code in index.values()}
        self.handlers = {
            "init_declarator": self._declarator,
            "enumerator": self._enumerator,
            "assignment_expression": self._assignment,
            "update_expression": self._update,
            "if_statement": self._if,
            "for_statement": self._for,
            "for_range_loop": self._range_for,
            "while_statement": self._loop,
            "do_statement": self._loop,
            "switch_statement": self._switch,
            "function_definition": self._function,
        }

    # -- helpers ------------------------------------------------------------------------------

    def variables(self, node: ts.Node) -> list[Key]:
        """Upstream `tree_to_variable_index`: non-keyword token leaves under `node`."""
        if node.type == "comment":
            return []
        if _is_leaf(node):
            entry = self.index.get(_key(node))
            if entry is None or _is_keyword(node, entry[1]):
                return []
            return [_key(node)]
        out = []
        for child in node.children:
            out += self.variables(child)
        return out

    def declared(self, declarator: ts.Node) -> list[Key]:
        """Innermost declared identifier (deviation a); upstream variables as a fallback."""
        node = declarator
        while node is not None:
            if node.type in ("identifier", "field_identifier"):
                return [_key(node)] if _key(node) in self.index else []
            nxt = node.child_by_field_name("declarator")
            if nxt is None:
                nxt = node.child_by_field_name("name")
            if nxt is None:
                named = node.named_children
                nxt = named[0] if named else None
            node = nxt
        return self.variables(declarator)

    def _merge(self, dfg: list[DfgNode]) -> list[DfgNode]:
        """Upstream loop merge: one node per `(code, idx, relation)`, parent indices unioned."""
        merged: dict[tuple, list[int]] = {}
        for code, idx, rel, _, idxs in dfg:
            key = (code, idx, rel)
            if key not in merged:
                merged[key] = list(idxs)
            else:
                merged[key] = sorted(set(merged[key] + idxs))
        out = [(c, i, r, [self.code_of[p] for p in idxs], idxs) for (c, i, r), idxs in merged.items()]
        return _by_idx(_by_idx(out))

    @staticmethod
    def _union(all_states: list[dict]) -> dict:
        new_states: dict[str, list[int]] = {}
        for dic in all_states:
            for key in dic:
                if key not in new_states:
                    new_states[key] = dic[key].copy()
                else:
                    new_states[key] += dic[key]
        return {key: sorted(set(value)) for key, value in new_states.items()}

    def _link(self, dfg, states, name_keys, value_keys, relation):
        for k1 in name_keys:
            idx1, code1 = self.index[k1]
            for k2 in value_keys:
                idx2, code2 = self.index[k2]
                dfg.append((code1, idx1, relation, [code2], [idx2]))
            states[code1] = [idx1]

    # -- walk ---------------------------------------------------------------------------------

    def walk(self, node: ts.Node, states: dict) -> tuple[list[DfgNode], dict]:
        states = states.copy()
        if node.type == "comment":
            return [], states
        if _is_leaf(node):
            entry = self.index.get(_key(node))
            if entry is None:  # zero-width (MISSING) node
                return [], states
            idx, code = entry
            if _is_keyword(node, code):
                return [], states
            if code in states:
                prev = states[code].copy()
                return [(code, idx, "comesFrom", [code] * len(prev), prev)], states
            if node.type == "identifier":
                states[code] = [idx]
            return [(code, idx, "comesFrom", [], [])], states
        handler = self.handlers.get(node.type)
        return handler(node, states) if handler else self._default(node, states)

    def _default(self, node, states):
        dfg = []
        for child in node.children:
            temp, states = self.walk(child, states)
            dfg += temp
        return _by_idx(dfg), states

    def _define(self, node, states, name, value):
        if name is None:
            return self._default(node, states)
        dfg = []
        if value is None:
            for key in self.declared(name):
                idx, code = self.index[key]
                dfg.append((code, idx, "comesFrom", [], []))
                states[code] = [idx]
            return _by_idx(dfg), states
        name_keys = self.declared(name)
        value_keys = self.variables(value)
        temp, states = self.walk(value, states)
        dfg += temp
        self._link(dfg, states, name_keys, value_keys, "comesFrom")
        return _by_idx(dfg), states

    def _declarator(self, node, states):
        return self._define(node, states, node.child_by_field_name("declarator"), node.child_by_field_name("value"))

    def _enumerator(self, node, states):
        value = node.child_by_field_name("value")
        if value is None:
            return self._default(node, states)
        return self._define(node, states, node.child_by_field_name("name"), value)

    def _assignment(self, node, states):
        left, right = node.child_by_field_name("left"), node.child_by_field_name("right")
        if left is None or right is None:
            return self._default(node, states)
        operator = node.child_by_field_name("operator")
        compound = operator is not None and operator.type != "="
        before = states
        dfg = []
        temp, states = self.walk(right, states)
        dfg += temp
        name_keys, value_keys = self.variables(left), self.variables(right)
        if compound:  # deviation g: the LHS is read as well as written
            for key in name_keys:
                idx, code = self.index[key]
                reads = list(before.get(code, [idx]))
                dfg.append((code, idx, "computedFrom", [code] * len(reads), reads))
        self._link(dfg, states, name_keys, value_keys, "computedFrom")
        return _by_idx(dfg), states

    def _update(self, node, states):
        dfg = []
        keys = self.variables(node)
        self._link(dfg, states, keys, keys, "computedFrom")
        return _by_idx(dfg), states

    def _if(self, node, states):
        dfg = []
        current = states.copy()
        others = []
        has_else = False
        for child in node.children:
            if child.type == "else_clause":
                has_else = True
                temp, new_states = self.walk(child, states)
                dfg += temp
                others.append(new_states)
            else:
                temp, current = self.walk(child, current)
                dfg += temp
        others.append(current)
        if not has_else:
            others.append(states)
        return _by_idx(dfg), self._union(others)

    def _for(self, node, states):
        dfg = []
        children = node.children
        for child in children:
            temp, states = self.walk(child, states)
            dfg += temp
        init = node.child_by_field_name("initializer")
        if init is not None:
            start = next(i for i, c in enumerate(children) if _same(c, init)) + 1
        else:
            start = next((i + 1 for i, c in enumerate(children) if c.type == "("), 0)
        for child in children[start:]:
            temp, states = self.walk(child, states)
            dfg += temp
        return self._merge(dfg), states

    def _range_for(self, node, states):
        name = node.child_by_field_name("declarator")
        value = node.child_by_field_name("right")
        body = node.child_by_field_name("body")
        if name is None or value is None or body is None:
            return self._loop(node, states)
        dfg = []
        for _ in range(2):
            temp, states = self.walk(value, states)
            dfg += temp
            self._link(dfg, states, self.declared(name), self.variables(value), "computedFrom")
            temp, states = self.walk(body, states)
            dfg += temp
        return self._merge(dfg), states

    def _loop(self, node, states):
        dfg = []
        for _ in range(2):
            for child in node.children:
                temp, states = self.walk(child, states)
                dfg += temp
        return self._merge(dfg), states

    def _switch(self, node, states):
        body = node.child_by_field_name("body")
        dfg = []
        for child in node.children:
            if body is not None and _same(child, body):
                continue
            temp, states = self.walk(child, states)
            dfg += temp
        others = [states]
        for child in body.children if body is not None else []:
            temp, branch_states = self.walk(child, states)
            dfg += temp
            others.append(branch_states)
        return _by_idx(dfg), self._union(others)

    def _function(self, node, states):
        dfg, _ = self._default(node, states)  # deviation b: definitions do not leak out
        return dfg, states


def walk_dfg(root: ts.Node, index: IndexToCode) -> list[DfgNode]:
    """Raw walker output (before the upstream post-filter), sorted by `idx`."""
    dfg, _ = _Walker(index).walk(root, {})
    return _by_idx(dfg)


def filter_dfg(dfg: list[DfgNode]) -> list[DfgNode]:
    """Upstream `extract_dataflow` filter: sort by idx, keep nodes with parents or that are a
    parent of another node."""
    dfg = _by_idx(dfg)
    keep = set()
    for d in dfg:
        if d[-1]:
            keep.add(d[1])
        keep.update(d[-1])
    return [d for d in dfg if d[1] in keep]


@contextmanager
def _recursion_limit(limit: int) -> Iterator[None]:
    old = sys.getrecursionlimit()
    if limit > old:
        sys.setrecursionlimit(limit)
    try:
        yield
    finally:
        sys.setrecursionlimit(old)


def extract_dfg_v2(code: str | bytes, lang: str = "c") -> Dataflow:
    """Tokens and post-filtered DFG of a C/C++ file. Parse errors do not drop the DFG
    (`parse_errors=True`); a walker failure gives `dfg=[]` with `dfg_error` and keeps tokens."""
    source = prepare_source(code)
    root = parse_source(source, lang).root_node
    tokens, index = index_tokens(root, source)
    try:
        with _recursion_limit(RECURSION_LIMIT):
            raw = walk_dfg(root, index)
    except Exception as exc:  # RecursionError included
        return Dataflow(tokens, [], root.has_error, f"{type(exc).__name__}: {exc}", 0)
    return Dataflow(tokens, filter_dfg(raw), root.has_error, None, len(raw))
