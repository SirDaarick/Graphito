from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

from models.graphcodebert.inference import GraphCodeBERTInference


@dataclass
class FusionResult:
    semantic_embedding: list[float] = field(default_factory=list)
    style_embedding: list[float] = field(default_factory=list)
    fused_vector: list[float] = field(default_factory=list)
    prob_sintetico: float = 0.0
    is_synthetic: bool = False


@dataclass
class ComparisonResult:
    reference_path: str = ""
    similarity: float = 0.0
    semantic_similarity: float = 0.0


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


class BimodalFusion:

    def __init__(
        self,
        graphcodebert: GraphCodeBERTInference,
        charcnn_inference=None,
    ):
        self._gcb = graphcodebert
        self._charcnn = charcnn_inference
        self.sem_dim = graphcodebert.config.embedding_dim
        self.style_dim = graphcodebert.config.charcnn_embedding_dim
        self.fused_dim = graphcodebert.config.fused_dim

    def fuse(self, code_path: Path) -> FusionResult:

        gcb_result = self._gcb.predict(code_path)
        semantic = np.array(gcb_result["embedding"], dtype=np.float64)

        if self._charcnn is not None:
            ccnn_result = self._charcnn.predict(code_path)
            style = np.array(ccnn_result["embedding"], dtype=np.float64)
            prob = ccnn_result["prob_sintetico"]
            is_synth = ccnn_result["prediction"] == "sintético"
        else:
            style = np.zeros(self.style_dim, dtype=np.float64)
            prob = 0.0
            is_synth = False

        fused = np.concatenate([semantic, style])

        return FusionResult(
            semantic_embedding=semantic.tolist(),
            style_embedding=style.tolist(),
            fused_vector=fused.tolist(),
            prob_sintetico=prob,
            is_synthetic=is_synth,
        )

    def build_reference_vector(self, code_path: Path) -> np.ndarray:
        gcb_result = self._gcb.predict(code_path)
        semantic = np.array(gcb_result["embedding"], dtype=np.float64)
        style_pad = np.zeros(self.style_dim, dtype=np.float64)
        return np.concatenate([semantic, style_pad])

    def similarity(self, student_vector: np.ndarray, reference_vector: np.ndarray) -> float:
        sem_student = student_vector[:self.sem_dim]
        sem_ref = reference_vector[:self.sem_dim]

        numerator = np.dot(sem_student, sem_ref)
        denom = np.linalg.norm(student_vector) * np.linalg.norm(reference_vector)

        if denom == 0.0:
            return 0.0
        return float(numerator / denom)

    def compare(
        self,
        student_path: Path,
        reference_paths: list[Path],
    ) -> list[ComparisonResult]:

        student_result = self.fuse(student_path)
        student_vec = np.array(student_result.fused_vector, dtype=np.float64)

        results: list[ComparisonResult] = []
        for ref_path in reference_paths:
            ref_vec = self.build_reference_vector(ref_path)
            sim = self.similarity(student_vec, ref_vec)

            sem_student = student_vec[:self.sem_dim]
            sem_ref = ref_vec[:self.sem_dim]
            sem_sim = _cosine(sem_student, sem_ref)

            results.append(ComparisonResult(
                reference_path=str(ref_path),
                similarity=sim,
                semantic_similarity=sem_sim,
            ))

        results.sort(key=lambda r: r.similarity, reverse=True)
        return results
