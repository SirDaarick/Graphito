import re
from collections import Counter
from pathlib import Path
from typing import Optional

from models.char_cnn.config import CharCNNConfig

# Minimum non-whitespace, non-comment characters for the CharCNN to be trusted.
MIN_NON_WS_CHARS = 60

WHITESPACE_MODES = ("trim", "canonical")

# String/char literals on a single line; an unterminated quote is treated as plain code.
_LITERAL = re.compile(r"\x22(?:\\.|[^\x22\\\n])*\x22|\x27(?:\\.|[^\x27\\\n])*\x27")
_IDENT_CHAR = re.compile(r"[A-Za-z0-9_]")


class CharPreprocessor:

    def __init__(self, config: Optional[CharCNNConfig] = None):
        self.config = config or CharCNNConfig()
        if self.config.whitespace_mode not in WHITESPACE_MODES:
            raise ValueError(
                f"whitespace_mode must be one of {WHITESPACE_MODES}, got {self.config.whitespace_mode!r}"
            )
        self._comment_pattern = re.compile(
            r"//.*?$|/\*.*?\*/|\x27(?:\\.|[^\x27\\])*\x27|\x22(?:\\.|[^\x22\\])*\x22",
            re.DOTALL | re.MULTILINE,
        )
        self._build_maps()

    def _build_maps(self) -> None:
        chars = sorted(set(self.config.alphabet))
        self._char_to_idx = {c: i + 1 for i, c in enumerate(chars)}
        self._unknown_idx = 0
        self._idx_to_char = {0: self.config.unknown_char}
        self._idx_to_char.update({i + 1: c for i, c in enumerate(chars)})
        self.vocab_size = len(self._char_to_idx) + 1

    def strip_c_comments(self, code: str) -> str:
        """Removes C/C++ comments without corrupting string or character literals."""
        def replacer(match: re.Match) -> str:
            s = match.group(0)
            if s.startswith("/"):
                return " "
            return s
        return self._comment_pattern.sub(replacer, code)

    def effective_length(self, text: str) -> int:
        """Non-whitespace characters left after stripping C/C++ comments.

        Always strips comments (independent of `config.strip_comments`) and is used only
        for the length guard; the text fed to the model is not modified.
        Known limits: C++ raw strings, digit separators (1'000), `//` with `\\` continuation.
        """
        return len("".join(self.strip_c_comments(text).split()))

    @staticmethod
    def _drop_layout_whitespace(segment: str) -> str:
        def repl(m: re.Match) -> str:
            before = segment[m.start() - 1] if m.start() > 0 else ""
            after = segment[m.end()] if m.end() < len(segment) else ""
            # Keep one space only where removing it would fuse two identifiers/keywords.
            if before and after and _IDENT_CHAR.match(before) and _IDENT_CHAR.match(after):
                return " "
            return ""

        return re.sub(r"\s+", repl, segment)

    def canonicalize_whitespace(self, text: str) -> str:
        """Remove layout whitespace outside string/char literals so reformatting is invisible.

        `int a` keeps its space (identifier boundary); everything else collapses, so a
        clang-format'd program and its compact original canonicalize to the same string.
        """
        out, last = [], 0
        for m in _LITERAL.finditer(text):
            out.append(self._drop_layout_whitespace(text[last:m.start()]))
            out.append(m.group(0))
            last = m.end()
        out.append(self._drop_layout_whitespace(text[last:]))
        return "".join(out)

    def normalize(self, text: str) -> str:
        if self.config.strip_comments:
            text = self.strip_c_comments(text)
        if self.config.whitespace_mode == "canonical":
            return self.canonicalize_whitespace(text)
        if self.config.normalize_whitespace:
            # Collapse runs of blank lines and strip trailing spaces per line
            text = re.sub(r"[ \t]+$", "", text, flags=re.MULTILINE)
            text = re.sub(r"\n{3,}", "\n\n", text)
        return text

    def char_to_idx(self, char: str) -> int:
        return self._char_to_idx.get(char, self._unknown_idx)

    def idx_to_char(self, idx: int) -> str:
        return self._idx_to_char.get(idx, self.config.unknown_char)

    def encode(self, text: str, pad: bool = True) -> list[int]:
        text = self.normalize(text)
        seq_len = self.config.seq_length

        if len(text) > seq_len:
            # Preserve header (includes/macros, ~1024 chars) + algorithm body
            head_len = min(1024, seq_len // 4)
            tail_len = seq_len - head_len
            text = text[:head_len] + text[-tail_len:]

        encoded = [self.char_to_idx(c) for c in text]
        length = len(encoded)
        if not pad:
            # Ensure minimum 10 characters for conv kernel sizes up to 9
            if length < 10:
                return encoded + [0] * (10 - length)
            return encoded[:seq_len]

        if length >= seq_len:
            return encoded[:seq_len]
        return encoded + [0] * (seq_len - length)

    def decode(self, indices: list[int]) -> str:
        return "".join(self.idx_to_char(i) for i in indices)

    @classmethod
    def build_alphabet_from_files(cls, file_paths: list[Path], top_n: int = 96) -> str:
        counter: Counter = Counter()
        for fp in file_paths:
            try:
                text = fp.read_text(encoding="utf-8", errors="replace")
                counter.update(text)
            except (OSError, UnicodeDecodeError):
                continue
        most_common = "".join(c for c, _ in counter.most_common(top_n))
        return "".join(sorted(set(most_common)))

