"""Inference port (design D4): models produce measurements, never decisions.

The decision lives in `app.domain.scoring.decide`; `compute_decision` and the hybrid 769-dim
embedding are gone from the port. Engines run torch off the event loop (AS9.1) and raise
`InferenceError` instead of falling back to fake values (AS6.1).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Mapping, Optional


@dataclass(frozen=True)
class Readiness:
    """Whether the engine (and its artifacts) can score. `reason` is a path-free code."""

    ready: bool
    reason: Optional[str] = None
    details: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class StylometryResult:
    """Channel B raw measurement: the CharCNN v2 `score` (uncalibrated probability) or an abstention.

    `raw_score` is None exactly when `abstained` is True; legacy probability keys are never used.
    """

    raw_score: Optional[float]
    abstained: bool
    reason: Optional[str] = None

    def __post_init__(self) -> None:
        if self.abstained and self.raw_score is not None:
            raise ValueError("an abstained result carries no score")
        if not self.abstained and self.raw_score is None:
            raise ValueError("a non-abstained result needs a score")


class InferencePort(ABC):
    """Bimodal inference engine: GraphCodeBERT v2 embeddings (secondary) and CharCNN v2 (Channel B)."""

    #: "real" | "stub"
    engine: str = ""
    #: sha256 of the canonical embedding configuration (design D12); selects the Chroma collection.
    embedding_fingerprint: str = ""

    @abstractmethod
    def readiness(self) -> Readiness:
        """Current readiness; never raises."""

    @abstractmethod
    async def extract_semantic_embedding(self, code: str, lang: str = "c") -> List[float]:
        """GraphCodeBERT v2 embedding (768 dims). Raises `InferenceError` on failure."""

    @abstractmethod
    async def predict_stylometry(self, code: str) -> StylometryResult:
        """CharCNN v2 raw score or abstention. Raises `InferenceError` on failure."""
