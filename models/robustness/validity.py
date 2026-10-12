"""Validity checking and edit magnitude metrics for code transformations."""

import shutil
import subprocess
from typing import Optional, Sequence
import tree_sitter as ts

from models.evaluation.normalize import shingle_tokens, tokenize


def count_error_nodes(tree_or_node: ts.Tree | ts.Node) -> int:
    """Count AST nodes marked as ERROR or MISSING by tree-sitter."""
    root = tree_or_node.root_node if isinstance(tree_or_node, ts.Tree) else tree_or_node
    count = 0
    stack = [root]
    while stack:
        node = stack.pop()
        if node.type in ("ERROR", "MISSING") or getattr(node, "is_missing", False):
            count += 1
        stack.extend(node.children)
    return count


def syntax_check(code: str | bytes, lang: str, timeout: float = 10.0) -> Optional[bool]:
    """Check syntax using system gcc/g++ if available.
    
    Returns:
        True: syntax check passed with 0 exit code.
        False: compilation failed or timed out.
        None: no suitable compiler installed.
    """
    compiler = "g++" if lang == "cpp" else "gcc"
    compiler_path = shutil.which(compiler)
    if compiler_path is None:
        return None

    lang_arg = "c++" if lang == "cpp" else "c"
    data = code.encode("utf-8", errors="replace") if isinstance(code, str) else code
    try:
        proc = subprocess.run(
            [compiler_path, "-fsyntax-only", "-x", lang_arg, "-"],
            input=data,
            capture_output=True,
            timeout=timeout,
        )
        return proc.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False


def token_levenshtein(s1: Sequence[str], s2: Sequence[str]) -> int:
    """Compute Levenshtein distance between two token sequences with O(min(m, n)) memory."""
    if len(s1) < len(s2):
        s1, s2 = s2, s1
    if len(s2) == 0:
        return len(s1)

    previous = list(range(len(s2) + 1))
    for i, t1 in enumerate(s1):
        current = [i + 1] * (len(s2) + 1)
        for j, t2 in enumerate(s2):
            cost = 0 if t1 == t2 else 1
            current[j + 1] = min(
                current[j] + 1,       # insertion
                previous[j + 1] + 1,   # deletion
                previous[j] + cost,    # substitution
            )
        previous = current
    return previous[len(s2)]


def token_edit_ratio(orig: str, trans: str) -> float:
    """Levenshtein distance between tokenize(orig) and tokenize(trans) divided by len(orig)."""
    t1 = tokenize(orig)
    t2 = tokenize(trans)
    if not t1:
        return 0.0 if not t2 else 1.0
    return token_levenshtein(t1, t2) / float(len(t1))


def abstract_edit_ratio(orig: str, trans: str) -> float:
    """Levenshtein distance between shingle_tokens(orig) and shingle_tokens(trans) divided by len(orig)."""
    t1 = shingle_tokens(orig)
    t2 = shingle_tokens(trans)
    if not t1:
        return 0.0 if not t2 else 1.0
    return token_levenshtein(t1, t2) / float(len(t1))
