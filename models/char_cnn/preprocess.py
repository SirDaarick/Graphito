import re
from collections import Counter
from pathlib import Path
from typing import Optional

from models.char_cnn.config import CharCNNConfig


class CharPreprocessor:

    def __init__(self, config: Optional[CharCNNConfig] = None):
        self.config = config or CharCNNConfig()
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

    def normalize(self, text: str) -> str:
        if self.config.strip_comments:
            text = self.strip_c_comments(text)
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

