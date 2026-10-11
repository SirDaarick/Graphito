"""Side-effect-free configuration and version constants for GraphCodeBERT v2.

Constructing `GCBV2Config` never touches the filesystem or loads a model. `to_dict` is the
config record used by run directories and embedding cache keys.
"""

from dataclasses import asdict, dataclass
from typing import Any

from models.graphcodebert.v2.dfg import WALKER_VERSION

INPUT_VERSION = "v2"

# RoBERTa position capacity: 514 embeddings minus the padding index and the pad position, as in
# upstream (`position_idx = i + pad_token_id + 1`). Code tokens (incl. CLS/SEP) + DFG nodes.
MAX_SEQUENCE_LENGTH = 512

POOLINGS = ("cls", "mean")
ATTN_IMPLEMENTATIONS = ("eager",)  # the 4D additive mask is verified for eager only (design D5)
DTYPES = ("float32",)  # fp16 deferred until a parity test exists (design D6)


@dataclass(frozen=True)
class GCBV2Config:
    """Input budgets, windowing and encoder options of the v2 pipeline.

    `code_length` counts the CLS and SEP tokens, as upstream `args.code_length` does; the code
    plus DFG sequence (`code_length + data_flow_length`) must fit `MAX_SEQUENCE_LENGTH`.
    """

    code_length: int = 384
    data_flow_length: int = 128
    max_windows: int = 16
    pooling: str = "cls"
    use_dfg: bool = True
    attn_implementation: str = "eager"
    dtype: str = "float32"

    def __post_init__(self) -> None:
        if self.code_length < 3:
            raise ValueError("code_length must be >= 3 (CLS, SEP and at least one code token)")
        if self.data_flow_length < 0:
            raise ValueError("data_flow_length must be >= 0")
        if self.code_length + self.data_flow_length > MAX_SEQUENCE_LENGTH:
            raise ValueError(
                f"code_length + data_flow_length = {self.code_length + self.data_flow_length} "
                f"exceeds the model position capacity {MAX_SEQUENCE_LENGTH}"
            )
        if self.max_windows < 1:
            raise ValueError("max_windows must be >= 1")
        if self.pooling not in POOLINGS:
            raise ValueError(f"pooling must be one of {POOLINGS}")
        if self.attn_implementation not in ATTN_IMPLEMENTATIONS:
            raise ValueError(f"attn_implementation must be one of {ATTN_IMPLEMENTATIONS}")
        if self.dtype not in DTYPES:
            raise ValueError(f"dtype must be one of {DTYPES}")

    @property
    def window_code_tokens(self) -> int:
        """Code subtokens per sliding window (`code_length` minus CLS and SEP)."""
        return self.code_length - 2

    @property
    def window_stride(self) -> int:
        """Stride between window starts: half a window (design D7)."""
        return max(1, self.window_code_tokens // 2)

    def to_dict(self) -> dict[str, Any]:
        """JSON-friendly record including the input/walker versions and the derived windows."""
        d = asdict(self)
        d.update(
            input_version=INPUT_VERSION,
            walker_version=WALKER_VERSION,
            window_code_tokens=self.window_code_tokens,
            window_stride=self.window_stride,
        )
        return d
