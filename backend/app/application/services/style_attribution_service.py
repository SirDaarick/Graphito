"""Which lines most influence the CharCNN style score (an approximation, not a verdict).

Occlusion: each non-empty line is removed in turn and the file re-scored by the engine; the service keeps
the lines whose removal LOWERS the score (positive `aporte`), the top `TOP_N`, sorted by line number.
Computed on demand and kept in a small in-process LRU keyed by submission, content and loaded model.
"""

import hashlib
from collections import OrderedDict
from typing import Dict, Hashable, Optional

from app.domain.ports.inference_port import InferencePort
from app.presentation.schemas.analysis import LineaEstiloResponse, StyleAttributionResponse


class StyleAttributionService:
    TOP_N = 8
    MAX_LINES = 300
    CACHE_SIZE = 128

    _cache: "OrderedDict[Hashable, StyleAttributionResponse]" = OrderedDict()

    def __init__(self, engine: InferencePort, model_id: str = ""):
        self.engine = engine
        self.model_id = model_id

    async def compute(self, submission_id: object, code: str) -> StyleAttributionResponse:
        key = (str(submission_id), hashlib.sha256(code.encode("utf-8")).hexdigest(), self.engine.engine, self.model_id)
        cached = self._cache.get(key)
        if cached is not None:
            self._cache.move_to_end(key)
            return cached
        result = await self.engine.attribute_stylometry_by_line(code, max_lines=self.MAX_LINES)
        positives: Dict[int, float] = {n: d for n, d in result.deltas.items() if d > 0}
        top = sorted(positives.items(), key=lambda item: (-item[1], item[0]))[: self.TOP_N]
        response = StyleAttributionResponse(
            probabilidad=None if result.base_score is None else float(result.base_score),
            lineas=[LineaEstiloResponse(numero_linea=n, aporte=round(d, 6)) for n, d in sorted(top)],
        )
        self._cache[key] = response
        while len(self._cache) > self.CACHE_SIZE:
            self._cache.popitem(last=False)
        return response
