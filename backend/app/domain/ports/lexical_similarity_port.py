"""Lexical similarity port for Channel A (spec AS2.1): 5-token shingle Jaccard after `normalize`."""

from abc import ABC, abstractmethod
from typing import Optional


class LexicalSimilarityPort(ABC):
    method: str = "jaccard"

    @abstractmethod
    def similarity(self, code_a: str, code_b: str) -> Optional[float]:
        """Jaccard in [0, 1]; None when the submission has no shingles (state `VACIO`)."""
