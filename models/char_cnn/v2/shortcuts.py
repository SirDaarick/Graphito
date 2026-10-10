"""Shortcut audit for CharCNN v2: which formatting artifacts still separate the classes.

`ShortcutAudit` is an `on_text(sample, raw, normalized)` sink fed by the same data pass that
encodes the corpus. For each configured set (by default train and test representatives) and class
it records the share of files whose raw and normalized text match each pattern, plus the
normalized-length bucket shares. It is report-only: it never changes texts, arrays or labels.
"""

import re
from collections import Counter
from typing import Any, Dict, Iterable, Mapping, Optional

from models.char_cnn.v2.data import label_of
from models.evaluation.manifest import Sample

__all__ = [
    "SCHEMA",
    "PATTERNS",
    "PATTERN_KEYS",
    "LENGTH_BUCKETS",
    "length_bucket",
    "hits",
    "ShortcutAudit",
    "render_markdown",
]

SCHEMA = "graphito.charcnn_shortcuts/v1"
CLASSES = ("human", "ai")

# Raw text is not folded, so the course marker also accepts the diacritic spelling.
PATTERNS: Dict[str, str] = {
    "non_ascii": r"[^\x00-\x7f]",
    "course_marker": r"(?i)\b(?:zada(?:ca|ća|tak|a{1,2})|tutorijal)\b",
    "autotest": r"(?i)autotest\w*",
    "control": r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]",
    "cr": r"\r",
    "tab": r"\t",
    "std_prefix": r"\bstd::",
    "using_namespace": r"\busing\s+namespace\b",
    "bits_include": r"#\s*include\s*<bits/",
}
NON_CODE_FIRST_LINE = "non_code_first_line"
NON_CODE_FIRST_LINE_RULE = "first non-empty line does not start with '#' and has none of ;{}()"
PATTERN_KEYS = (*PATTERNS, NON_CODE_FIRST_LINE)
_REGEXES = {name: re.compile(pattern) for name, pattern in PATTERNS.items()}
_CODE_CHARS = frozenset(";{}()")

# Normalized-length buckets (chars); `>=4096` inputs are scored with several windows.
LENGTH_BUCKETS = ("<512", "512-1023", "1024-2047", "2048-4095", ">=4096")
_BUCKET_EDGES = (512, 1024, 2048, 4096)


def length_bucket(n: int) -> str:
    """Bucket label of a normalized length `n`."""
    for edge, label in zip(_BUCKET_EDGES, LENGTH_BUCKETS):
        if n < edge:
            return label
    return LENGTH_BUCKETS[-1]


def _non_code_first_line(text: str) -> bool:
    for line in text.splitlines():
        line = line.strip()
        if line:
            return not line.startswith("#") and not (_CODE_CHARS & set(line))
    return False


def hits(text: str) -> set:
    """Names of the `PATTERN_KEYS` present in `text`."""
    found = {name for name, rx in _REGEXES.items() if rx.search(text)}
    if _non_code_first_line(text):
        found.add(NON_CODE_FIRST_LINE)
    return found


class _Tally:
    def __init__(self) -> None:
        self.n = 0
        self.raw: Counter = Counter()
        self.normalized: Counter = Counter()
        self.buckets: Counter = Counter()

    def add(self, raw: str, normalized: str) -> None:
        self.n += 1
        self.raw.update(hits(raw))
        self.normalized.update(hits(normalized))
        self.buckets[length_bucket(len(normalized))] += 1

    def _shares(self, counts: Counter, keys: Iterable[str]) -> Dict[str, Optional[float]]:
        return {key: (counts[key] / self.n if self.n else None) for key in keys}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "n": self.n,
            "raw": self._shares(self.raw, PATTERN_KEYS),
            "normalized": self._shares(self.normalized, PATTERN_KEYS),
            "length_buckets": self._shares(self.buckets, LENGTH_BUCKETS),
        }


class ShortcutAudit:
    """`on_text` accumulator over named sets of sample ids (a sample may belong to several)."""

    def __init__(self, sets: Mapping[str, Iterable[str]]):
        self._sets = list(sets)
        self._membership: Dict[str, list] = {}
        for name, ids in sets.items():
            for sample_id in ids:
                self._membership.setdefault(sample_id, []).append(name)
        self._tallies = {name: {cls: _Tally() for cls in CLASSES} for name in self._sets}

    def __call__(self, sample: Sample, raw: str, normalized: str) -> None:
        cls = CLASSES[label_of(sample)]
        for name in self._membership.get(sample.id, ()):
            self._tallies[name][cls].add(raw, normalized)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema": SCHEMA,
            "note": "report-only: shares of files per class; never used for training or scoring",
            "patterns": {**PATTERNS, NON_CODE_FIRST_LINE: NON_CODE_FIRST_LINE_RULE},
            "length_buckets": list(LENGTH_BUCKETS),
            "sets": {
                name: {cls: tally.to_dict() for cls, tally in self._tallies[name].items()} for name in self._sets
            },
        }


def _fmt(value: Optional[float]) -> str:
    return "n/a" if value is None else f"{value:.3f}"


def render_markdown(doc: Mapping[str, Any]) -> str:
    """The "Shortcut audit" report section for a `shortcuts.json` document."""
    lines = [
        "## Shortcut audit",
        "",
        "Share of files per class whose raw / normalized text still contains each artifact "
        "(report-only; it does not change training or scores). A pattern that remains "
        "unbalanced after normalization is a residual shortcut.",
    ]
    for name, classes in doc["sets"].items():
        human, ai = classes["human"], classes["ai"]
        lines += [
            "",
            f"### {name} (human n={human['n']}, ai n={ai['n']})",
            "",
            "| Pattern | human raw | human normalized | ai raw | ai normalized |",
            "|---|---|---|---|---|",
        ]
        for key in human["raw"]:
            lines.append(
                f"| {key} | {_fmt(human['raw'][key])} | {_fmt(human['normalized'][key])} "
                f"| {_fmt(ai['raw'][key])} | {_fmt(ai['normalized'][key])} |"
            )
        lines += ["", "| Length bucket (normalized chars) | human | ai |", "|---|---|---|"]
        for bucket in human["length_buckets"]:
            lines.append(
                f"| {bucket} | {_fmt(human['length_buckets'][bucket])} | {_fmt(ai['length_buckets'][bucket])} |"
            )
    return "\n".join(lines) + "\n"
