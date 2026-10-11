"""File embeddings with GraphCodeBERT v2: DFG once, sliding windows, one forward, two poolings.

Pipeline for one file (GE5, GE6, design D7-D9):

1. `extract_dfg_v2` on the full file (comments stripped, parse errors tolerated);
2. `build_windows` (single upstream input when the file fits, else 382/191 windows, cap 16);
3. one batched `GraphCodeBERTV2Encoder.encode` call for all windows;
4. per window `cls` (hidden state at position 0) and `mean` (mean over the code subtoken
   positions, CLS/SEP/nodes/padding excluded), both from that one forward pass;
5. file embedding = unweighted mean of the window poolings, for both poolings.

`embed` never raises for bad input: empty code (after comment stripping) or any exception gives
`success=False` with `error` set and no embedding. Parse errors still embed (`parse_errors=True`).
"""

from dataclasses import dataclass, field
from typing import Any, Sequence

import numpy as np
import torch

from models.graphcodebert.v2.config import INPUT_VERSION, GCBV2Config
from models.graphcodebert.v2.dfg import extract_dfg_v2
from models.graphcodebert.v2.encode import EncodedInput, Tokenizer
from models.graphcodebert.v2.model import DEFAULT_MODEL, GraphCodeBERTV2Encoder
from models.graphcodebert.v2.windows import build_windows

_CPP_ALIASES = {"cpp", "c++", "cc", "cxx", "hpp", "hxx"}


def normalize_language(language: str | None) -> str:
    """`"cpp"` for C++ spellings, `"c"` otherwise."""
    return "cpp" if (language or "c").strip().lower() in _CPP_ALIASES else "c"


def pool_hidden(hidden: torch.Tensor, inputs: Sequence[EncodedInput]) -> tuple[torch.Tensor, torch.Tensor]:
    """`[N, L, H]` hidden states -> (`cls` `[N, H]`, `mean` `[N, H]`).

    `mean` averages the code subtoken positions `1 .. n_code_kept` only (no CLS, SEP, DFG nodes or
    padding)."""
    cls = hidden[:, 0, :]
    means = []
    for i, enc in enumerate(inputs):
        n = enc.n_code_kept
        means.append(hidden[i, 1 : 1 + n, :].mean(0) if n > 0 else torch.zeros(hidden.shape[-1], dtype=hidden.dtype))
    return cls, torch.stack(means)


@dataclass(frozen=True)
class EmbedResult:
    """File-level v2 embedding and honest bookkeeping. `cls`/`mean` are `[H]` float32 arrays,
    or None when `success` is False."""

    success: bool
    cls: np.ndarray | None = field(default=None, repr=False)
    mean: np.ndarray | None = field(default=None, repr=False)
    pooling: str = "cls"
    use_dfg: bool = True
    n_windows: int = 0
    truncated: bool = False
    dfg_nodes_used: int = 0
    dfg_node_count: int = 0
    code_tokens_count: int = 0
    parse_errors: bool = False
    dfg_error: str | None = None
    error: str | None = None
    input_version: str = INPUT_VERSION

    @property
    def embedding(self) -> np.ndarray | None:
        """The embedding of the configured pooling."""
        return self.cls if self.pooling == "cls" else self.mean

    def to_dict(self) -> dict[str, Any]:
        d = {k: getattr(self, k) for k in self.__dataclass_fields__}
        d["cls"] = None if self.cls is None else self.cls.tolist()
        d["mean"] = None if self.mean is None else self.mean.tolist()
        return d


class GraphCodeBERTV2Embedder:
    """Zero-shot GraphCodeBERT v2 file embedder (no adapter, fp32, eager)."""

    def __init__(
        self,
        tokenizer: Tokenizer,
        encoder: GraphCodeBERTV2Encoder,
        config: GCBV2Config | None = None,
        model_revision: str | None = None,
    ):
        self.tokenizer = tokenizer
        self.encoder = encoder
        self.config = config or GCBV2Config()
        self.model_revision = model_revision

    @classmethod
    def from_pretrained(
        cls,
        name: str = DEFAULT_MODEL,
        config: GCBV2Config | None = None,
        local_files_only: bool = False,
        device: str | torch.device = "cpu",
        batch_size: int = 16,
    ) -> "GraphCodeBERTV2Embedder":
        """Load tokenizer and eager encoder; `model_revision` is the HF snapshot commit when known."""
        from transformers import RobertaTokenizer

        tokenizer = RobertaTokenizer.from_pretrained(name, local_files_only=local_files_only)
        encoder = GraphCodeBERTV2Encoder.from_pretrained(
            name, local_files_only=local_files_only, device=device, batch_size=batch_size
        )
        revision = getattr(encoder.roberta.config, "_commit_hash", None)
        return cls(tokenizer, encoder, config, model_revision=revision)

    def embed(self, code: str | bytes, language: str = "c", use_dfg: bool | None = None) -> EmbedResult:
        """Embed one file. `use_dfg` overrides `config.use_dfg` (ablation, D8)."""
        use_dfg = self.config.use_dfg if use_dfg is None else use_dfg
        base = dict(pooling=self.config.pooling, use_dfg=use_dfg)
        try:
            df = extract_dfg_v2(code, normalize_language(language))
        except Exception as exc:  # pragma: no cover - the walker itself does not raise
            return EmbedResult(success=False, error=f"dfg: {exc}", **base)
        counts = dict(
            dfg_node_count=len(df.dfg),
            code_tokens_count=len(df.code_tokens),
            parse_errors=df.parse_errors,
            dfg_error=df.dfg_error,
        )
        if not df.code_tokens:
            return EmbedResult(success=False, error="empty", **base, **counts)
        try:
            win = build_windows(df.code_tokens, df.dfg, self.tokenizer, self.config, use_dfg=use_dfg)
            hidden = self.encoder.encode(win.inputs)
            cls, mean = pool_hidden(hidden, win.inputs)
        except Exception as exc:
            return EmbedResult(success=False, error=f"{type(exc).__name__}: {exc}", **base, **counts)
        return EmbedResult(
            success=True,
            cls=cls.mean(0).numpy().astype(np.float32),
            mean=mean.mean(0).numpy().astype(np.float32),
            n_windows=win.n_windows,
            truncated=win.truncated,
            dfg_nodes_used=win.dfg_nodes_used,
            **base,
            **counts,
        )
