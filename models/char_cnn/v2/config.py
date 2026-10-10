"""Side-effect-free configuration and version constants for CharCNN v2.

Unlike the legacy `CharCNNConfig`, constructing `CharCNNV2Config` never touches the filesystem.
The alphabet and index layout are fixed by `PREPROC_VERSION`; `to_dict` records them so a
checkpoint can be validated and rebuilt from its own config only.
"""

from dataclasses import asdict, dataclass, fields
from typing import Any, Mapping

from models.char_cnn.preprocess import MIN_NON_WS_CHARS

PREPROC_VERSION = 2
ARCH_VERSION = 2

# LF plus printable ASCII 0x20-0x7E. PAD=0, UNK=1, ALPHABET[i] -> i + ALPHABET_OFFSET.
ALPHABET = "\n" + "".join(chr(c) for c in range(0x20, 0x7F))
PAD_IDX = 0
UNK_IDX = 1
ALPHABET_OFFSET = 2  # indices reserved before the alphabet: PAD and UNK
VOCAB_SIZE = len(ALPHABET) + ALPHABET_OFFSET
NORM = "layernorm_channels"


def char_index(ch: str) -> int:
    """Encoded index of an `ALPHABET` character (`ValueError` for anything else)."""
    return ALPHABET.index(ch) + ALPHABET_OFFSET

# Fixed by the preprocessing/architecture version: written by `to_dict`, checked by `from_dict`.
_FIXED_FIELDS: dict[str, Any] = {
    "arch_version": ARCH_VERSION,
    "preproc_version": PREPROC_VERSION,
    "alphabet": ALPHABET,
    "pad_idx": PAD_IDX,
    "unk_idx": UNK_IDX,
    "vocab_size": VOCAB_SIZE,
    "norm": NORM,
}
# A payload without these cannot be proven to be a v2 config, so `from_dict` fails closed.
_REQUIRED_FIELDS = ("arch_version", "preproc_version", "alphabet")


@dataclass(frozen=True)
class CharCNNV2Config:
    """Architecture and windowing hyperparameters of CharCNN v2."""

    embedding_dim: int = 128
    conv_kernel_sizes: tuple[int, ...] = (3, 5, 7, 9)
    conv_filters: tuple[int, ...] = (64, 64, 64, 64)
    fc_units: int = 1024
    num_classes: int = 2
    dropout: float = 0.4
    window: int = 4096
    stride: int = 2048
    max_windows: int = 8
    min_non_ws_chars: int = MIN_NON_WS_CHARS

    def __post_init__(self) -> None:
        # Normalize sequences (e.g. JSON lists) to tuples so equality and hashing work.
        object.__setattr__(self, "conv_kernel_sizes", tuple(int(k) for k in self.conv_kernel_sizes))
        object.__setattr__(self, "conv_filters", tuple(int(f) for f in self.conv_filters))
        if not self.conv_kernel_sizes or len(self.conv_kernel_sizes) != len(self.conv_filters):
            raise ValueError("conv_kernel_sizes and conv_filters must be non-empty and equally long")
        if any(k < 1 or k % 2 == 0 for k in self.conv_kernel_sizes):
            raise ValueError("conv_kernel_sizes must be odd and positive (length-preserving padding)")
        for name in ("embedding_dim", "fc_units", "num_classes", "window", "stride", "max_windows"):
            if getattr(self, name) < 1:
                raise ValueError(f"{name} must be >= 1")
        if self.stride > self.window:
            raise ValueError("stride must be <= window (windows must cover the whole input)")
        if any(f < 1 for f in self.conv_filters):
            raise ValueError("conv_filters must be >= 1")
        if not 0.0 <= self.dropout < 1.0:
            raise ValueError("dropout must be in [0, 1)")

    @property
    def vocab_size(self) -> int:
        return VOCAB_SIZE

    def to_dict(self) -> dict[str, Any]:
        """JSON-friendly dict with the fixed version/alphabet fields included."""
        d = asdict(self)
        d["conv_kernel_sizes"] = list(self.conv_kernel_sizes)
        d["conv_filters"] = list(self.conv_filters)
        d.update(_FIXED_FIELDS)
        return d

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "CharCNNV2Config":
        """Rebuild from a `to_dict` payload; unknown keys (run metadata) are ignored.

        Raises `ValueError` when a required field (`_REQUIRED_FIELDS`) is missing or when a fixed
        field present in `data` disagrees with this version.
        """
        missing = [key for key in _REQUIRED_FIELDS if key not in data]
        if missing:
            raise ValueError(f"v2 config lacks required fields {missing}")
        for key, expected in _FIXED_FIELDS.items():
            if key in data and data[key] != expected:
                raise ValueError(f"incompatible {key}: {data[key]!r} (expected {expected!r})")
        names = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in names})
