"""Symmetric preprocessing v2 (`PREPROC_VERSION = 2`), encoding and the training leak guard.

`preprocess_v2` removes formatting artifacts that differ between human and AI files without
looking at the label: (1) newlines/controls, (2) Unicode fold, (3) comments via
`models.evaluation.normalize.strip_comments`, (4) course headers and markers, (5) line-preserving
canonical whitespace. The result is ASCII over `ALPHABET`, so `encode` never emits UNK for it.
"""

import re
import unicodedata
from typing import Iterable

import numpy as np

from models.char_cnn.v2.config import ALPHABET, PREPROC_VERSION, UNK_IDX, char_index
from models.evaluation.normalize import strip_comments

__all__ = [
    "PREPROC_VERSION",
    "LEAK_PATTERNS",
    "LeakGuardError",
    "clean_controls",
    "fold_unicode",
    "strip_course_markers",
    "canonical_whitespace",
    "preprocess_v2",
    "encode",
    "effective_length_v2",
    "leak_hits",
    "leak_guard",
]

# Course markers after folding: Zadaca, Zadatak, Tutorijal; zadaa(a) is U+FFFD/mojibake residue.
_MARKER = r"(?:zada(?:ca|tak|a{1,2})|tutorijal)"
_HEADER_PRINT_RE = re.compile(
    rf"^[ \t]*(?:std::)?(?:printf|puts|cout)\b[^\n]*\b{_MARKER}\b[^\n]*(?:\n|$)", re.I | re.M
)
# A course header line carries a marker followed by a number (e.g. "Zadaca 6", "Tutorijal 13").
_HEADER_LINE_RE = re.compile(rf"\b{_MARKER}\b[ \t]*(?:br\.?[ \t]*)?\d+", re.I)
_MARKER_TOKEN_RE = re.compile(rf"\b{_MARKER}\b(?:[ \t]*(?:br\.?[ \t]*)?\d+)?", re.I)

_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")  # \t and \n survive
_INVISIBLE = dict.fromkeys(map(ord, "​‌‍⁠﻿�"))

# Copied from the frozen legacy `models.char_cnn.preprocess._LITERAL` (single-line literals).
_LITERAL = re.compile(r"\x22(?:\\.|[^\x22\\\n])*\x22|\x27(?:\\.|[^\x27\\\n])*\x27")
_SPACE_RUN = re.compile(r" {2,}")

# C++14 digit separators (1'000, 0xDEAD'BEEF, 0b1010'1010) would open a char literal in
# `strip_comments` and hide a trailing `//` comment. A numeric literal token starts with a digit
# that does not continue an identifier (so `u8'a'` and `v1` are left alone); inside it, an
# apostrophe between two alphanumeric characters is a separator. Separators are swapped for NUL
# (removed in step 1, so it cannot occur in the text at that point) while comments, markers and
# whitespace are processed.
_NUMERIC_TOKEN_RE = re.compile(r"(?<![\w.])\.?\d(?:[\w.]|(?<=[0-9A-Za-z])'(?=[0-9A-Za-z]))*")
_SEPARATOR_PLACEHOLDER = "\x00"


def _shield_digit_separators(text: str) -> str:
    return _NUMERIC_TOKEN_RE.sub(lambda m: m.group(0).replace("'", _SEPARATOR_PLACEHOLDER), text)


def _build_fold_table() -> dict[int, str]:
    table: dict[int, str] = {}
    for cp in range(0x2018, 0x201C):
        table[cp] = "'"
    for cp in range(0x201C, 0x2020):
        table[cp] = '"'
    for cp in [*range(0x2010, 0x2016), 0x2212]:
        table[cp] = "-"
    for cp in [0x00A0, *range(0x2000, 0x200B), 0x202F, 0x205F, 0x3000]:
        table[cp] = " "
    table[ord("đ")] = "d"  # NFKD does not decompose d-stroke
    table[ord("Đ")] = "D"
    return table


_FOLD_TABLE = _build_fold_table()
_KEEP = frozenset(ALPHABET) | {"\t"}

_LUT = np.full(256, UNK_IDX, dtype=np.uint8)
for _ch in ALPHABET:
    _LUT[ord(_ch)] = char_index(_ch)

LEAK_PATTERNS: dict[str, str] = {
    # Anything outside LF + printable ASCII: non-ASCII, CR, C0 controls, DEL and tabs.
    "non_alphabet": r"[^\n\x20-\x7e]",
    # Course markers; `autotest` is detected here but not stripped (decision D-B).
    "course_marker": rf"(?i)(?:\b{_MARKER}\b|\bautotest\w*)",
}
_LEAK_RES = {name: re.compile(pattern) for name, pattern in LEAK_PATTERNS.items()}


class LeakGuardError(RuntimeError):
    """Raised when a leak pattern survives preprocessing in more than `threshold` of the texts."""

    def __init__(self, shares: dict[str, float], offending: dict[str, list[int]], threshold: float):
        self.shares = shares
        self.offending = offending
        self.threshold = threshold
        over = {k: v for k, v in shares.items() if v > threshold}
        super().__init__(f"leak guard failed (threshold {threshold}): {over}")


def clean_controls(text: str) -> str:
    """Step 1: CRLF/CR -> LF; drop C0 controls (except TAB/LF), DEL, zero-width chars, BOM, U+FFFD."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return _CONTROL_RE.sub("", text).translate(_INVISIBLE)


def fold_unicode(text: str) -> str:
    """Step 2: fold quotes/dashes/spaces and diacritics to ASCII, then drop every other non-ASCII char."""
    text = unicodedata.normalize("NFKD", text.translate(_FOLD_TABLE))
    return "".join(ch for ch in text if ch in _KEEP)


def strip_course_markers(text: str) -> str:
    """Step 4: drop print lines and leading header lines carrying a course marker, then leftover markers."""
    text = _HEADER_PRINT_RE.sub("", text)
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if not line.strip():
            continue
        if not _HEADER_LINE_RE.search(line):
            break
        lines[i] = ""
    return _MARKER_TOKEN_RE.sub("", "\n".join(lines))


def _collapse_spaces(line: str) -> str:
    parts, last = [], 0
    for m in _LITERAL.finditer(line):
        parts.append(_SPACE_RUN.sub(" ", line[last:m.start()]))
        parts.append(m.group(0))
        last = m.end()
    parts.append(_SPACE_RUN.sub(" ", line[last:]))
    return "".join(parts)


def canonical_whitespace(text: str) -> str:
    """Step 5: tabs -> spaces, collapse space runs outside literals, strip lines, drop empty lines."""
    lines = (_collapse_spaces(line).strip(" ") for line in text.replace("\t", " ").split("\n"))
    return "\n".join(line for line in lines if line)


def preprocess_v2(text: str) -> str:
    """Normalize source text symmetrically for both classes (pure and idempotent)."""
    text = fold_unicode(clean_controls(text))
    text = _shield_digit_separators(text)
    text = canonical_whitespace(strip_course_markers(strip_comments(text)))
    return text.replace(_SEPARATOR_PLACEHOLDER, "'")


def encode(text: str) -> np.ndarray:
    """Map text to uint8 indices (PAD=0 never emitted, UNK=1 for chars outside `ALPHABET`).

    An empty text becomes `[UNK]` so the model always receives at least one position.
    """
    if not text:
        return np.array([UNK_IDX], dtype=np.uint8)
    codes = np.frombuffer(text.encode("utf-32-le"), dtype=np.uint32)
    return _LUT[np.minimum(codes, 255)]


def effective_length_v2(text: str) -> int:
    """Characters of normalized text that are neither spaces nor newlines."""
    return len(text) - text.count(" ") - text.count("\n")


def leak_hits(text: str) -> set[str]:
    """Names of the `LEAK_PATTERNS` matching `text`."""
    return {name for name, rx in _LEAK_RES.items() if rx.search(text)}


def leak_guard(texts: Iterable[str], threshold: float = 0.001, max_offending: int = 20) -> dict[str, float]:
    """Return the share of `texts` matching each leak pattern; raise if any share exceeds `threshold`.

    The comparison is strict (`share > threshold`). `LeakGuardError.offending` keeps the first
    `max_offending` indices per pattern so callers can map them back to sample ids.
    """
    counts = dict.fromkeys(LEAK_PATTERNS, 0)
    offending: dict[str, list[int]] = {name: [] for name in LEAK_PATTERNS}
    n = 0
    for i, text in enumerate(texts):
        n += 1
        for name in leak_hits(text):
            counts[name] += 1
            if len(offending[name]) < max_offending:
                offending[name].append(i)
    shares = {name: (c / n if n else 0.0) for name, c in counts.items()}
    if any(share > threshold for share in shares.values()):
        raise LeakGuardError(shares, offending, threshold)
    return shares
