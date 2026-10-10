"""C/C++ normalization for dedup: comment stripping, regex lexer, hashes and shingle tokens.

Deliberately independent of `models.char_cnn.preprocess` and the tree-sitter parser, which later
work packages rewrite. Known limits (affect dedup recall only): raw strings, digit separators
and backslash continuations inside `//` comments are not handled.
"""

import hashlib
import re
from typing import List

KEYWORDS = frozenset(
    """
    alignas alignof and and_eq asm auto bitand bitor bool break case catch char class compl
    concept const const_cast constexpr continue decltype default delete do double dynamic_cast
    else enum explicit export extern false final float for friend goto if inline int long
    mutable namespace new noexcept not not_eq nullptr operator or or_eq override private
    protected public register reinterpret_cast restrict return short signed sizeof static
    static_assert static_cast struct switch template this thread_local throw true try typedef
    typeid typename union unsigned using virtual void volatile wchar_t while xor xor_eq
    _Bool _Complex
    """.split()
)

_TOKEN_RE = re.compile(
    r"""
    "(?:\\.|[^"\\\n])*"?                                  # string literal (unterminated ends at EOL)
    | '(?:\\.|[^'\\\n])*'?                                # char literal
    | 0[xX][0-9a-fA-F]+[uUlL]*                            # hex number
    | (?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?[uUlLfF]*       # decimal / float number
    | [A-Za-z_]\w*                                        # identifier or keyword
    | <<=|>>=|\.\.\.|->\*|<=>                             # 3-char operators
    | \+\+|--|->|::|<<|>>|<=|>=|==|!=|&&|\|\||[-+*/%&|^]=|\#\#   # 2-char operators
    | \S                                                  # any other punctuation
    """,
    re.VERBOSE,
)


def strip_comments(code: str) -> str:
    """Remove C/C++ comments, keeping string/char literals and the original line count."""
    out = []
    i, n = 0, len(code)
    while i < n:
        ch = code[i]
        nxt = code[i + 1] if i + 1 < n else ""
        if ch in ('"', "'"):
            quote = ch
            out.append(ch)
            i += 1
            while i < n:
                c = code[i]
                out.append(c)
                i += 1
                if c == "\\" and i < n:
                    out.append(code[i])
                    i += 1
                elif c == quote or c == "\n":
                    break
        elif ch == "/" and nxt == "/":
            while i < n and code[i] != "\n":
                i += 1
        elif ch == "/" and nxt == "*":
            end = code.find("*/", i + 2)
            end = n if end == -1 else end + 2
            out.append(" " + "\n" * code.count("\n", i, end))
            i = end
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def tokenize(code: str) -> List[str]:
    """Lex comment-stripped C/C++ into string/char literals, numbers, identifiers and operators."""
    return _TOKEN_RE.findall(strip_comments(code))


def effective_length(code: str) -> int:
    """Number of UTF-8 bytes left after removing comments and all whitespace."""
    return len("".join(strip_comments(code).split()).encode("utf-8", errors="ignore"))


def norm_hash(code: str) -> str:
    """sha256[:16] of the space-joined token stream (identifiers kept, comments/whitespace gone)."""
    return hashlib.sha256(" ".join(tokenize(code)).encode("utf-8")).hexdigest()[:16]


def _abstract(token: str) -> str:
    first = token[0]
    if first == '"':
        return "STR"
    if first == "'":
        return "CHR"
    if first.isdigit() or (first == "." and len(token) > 1 and token[1].isdigit()):
        return "NUM"
    if (first.isalpha() or first == "_") and token not in KEYWORDS:
        return "ID"
    return token


def shingle_tokens(code: str) -> List[str]:
    """Token stream for near-dup detection: identifiers -> ID, literals -> NUM/STR/CHR, keywords kept."""
    return [_abstract(t) for t in tokenize(code)]
