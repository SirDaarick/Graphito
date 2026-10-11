"""Channel A lexical similarity: 5-token shingle Jaccard (spec AS2.1; design D3, D4).

Computed with the SDD-3 evaluation helpers, unchanged (`models.evaluation.normalize.shingle_tokens`,
`dedup.token_ids`, `dedup.shingle_hashes`, `dedup.jaccard`), so the backend score is the same number
the deployed Jaccard calibration was fitted on (parity test). numpy only; no torch.
"""

import importlib
from typing import Optional

import numpy as np

from app.domain.ports.lexical_similarity_port import LexicalSimilarityPort
from app.infrastructure.artifacts.models_path import ensure_on_path


class JaccardSimilarity(LexicalSimilarityPort):
    method = "jaccard"

    def __init__(self) -> None:
        ensure_on_path()
        self._dedup = importlib.import_module("models.evaluation.dedup")
        self._normalize = importlib.import_module("models.evaluation.normalize")
        self.shingle_k = int(self._dedup.SHINGLE_K)

    def shingles(self, code: str) -> np.ndarray:
        """Sorted unique shingle hashes of the abstracted token stream (`jaccard_set` in SDD-3)."""
        tokens = self._normalize.shingle_tokens(code)
        return self._dedup.shingle_hashes(self._dedup.token_ids(tokens), self.shingle_k)

    def similarity(self, code_a: str, code_b: str) -> Optional[float]:
        a = self.shingles(code_a)
        if a.size == 0:
            return None  # empty submission stream: Channel A state VACIO, never an invented 0
        return float(self._dedup.jaccard(a, self.shingles(code_b)))
