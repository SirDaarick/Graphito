"""REAL inference engine: CharCNN v2 (Channel B) and zero-shot GraphCodeBERT v2 (secondary).

Fail closed (spec AS6.1): any load or configuration problem raises `InferenceError` with a stable
reason code; there is no fallback to fake values. Models load from the verified deploy bundle
(the CharCNN checkpoint listed in the manifest) and GraphCodeBERT is built as v2 with mean
pooling, zero-shot, never with a fine-tuned add-on.

Torch never runs on the event loop (AS9.1, D10): loading and every prediction go through a
dedicated `ThreadPoolExecutor(max_workers=INFERENCE_WORKERS, thread_name_prefix="inference")`.

The embedding fingerprint (D12) is the sha256 of the canonical JSON of the embedding pipeline
fields from the manifest; it must equal the manifest's own fingerprint and selects the Chroma
collection, so embeddings from different pipelines never mix.
"""

import asyncio
import hashlib
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional

from app.domain.errors import InferenceError
from app.domain.ports.inference_port import InferencePort, Readiness, StylometryResult
from app.infrastructure.artifacts.models_path import ensure_on_path

logger = logging.getLogger(__name__)

CHARCNN_ARCH_VERSION = 2
EMBEDDING_DIM = 768
FINGERPRINT_FIELDS = (
    "model_name", "model_revision", "input_version", "walker_version", "pooling", "use_dfg",
    "code_length", "data_flow_length", "max_windows", "dtype",
)
# Manifest fields handed to `GraphCodeBERTConfig` (the rest only enter the fingerprint).
GCB_CONFIG_FIELDS = ("model_name", "input_version", "pooling", "use_dfg", "code_length", "data_flow_length", "max_windows")


def embedding_fingerprint(fields: Mapping[str, Any]) -> str:
    """sha256 of the canonical JSON of the embedding pipeline fields (design D12)."""
    canonical = json.dumps({k: fields.get(k) for k in FINGERPRINT_FIELDS}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def load_charcnn(checkpoint_path: Path):
    """CharCNN v2 from the verified deploy checkpoint (runs on an inference thread)."""
    ensure_on_path()
    from models.char_cnn.inference import CharCNNInference

    return CharCNNInference(checkpoint_path=checkpoint_path)


def load_gcb(config_kwargs: Dict[str, Any]):
    """Zero-shot GraphCodeBERT v2 facade (runs on an inference thread)."""
    ensure_on_path()
    from models.graphcodebert.config import GraphCodeBERTConfig
    from models.graphcodebert.inference import GraphCodeBERTInference

    return GraphCodeBERTInference(config=GraphCodeBERTConfig(**config_kwargs))


class RealBimodalInferenceEngine(InferencePort):
    engine = "real"

    def __init__(
        self,
        bundle,
        settings,
        *,
        charcnn_factory: Optional[Callable[[Path], Any]] = None,
        gcb_factory: Optional[Callable[[Dict[str, Any]], Any]] = None,
    ):
        self.workers = int(settings.INFERENCE_WORKERS)
        self.gcb_enabled = bool(settings.GCB_SECONDARY_ENABLED)
        self.gcb_fields = self._gcb_fields(bundle.gcb, settings)
        self.embedding_fingerprint = embedding_fingerprint(self.gcb_fields)
        if bundle.gcb.get("fingerprint") != self.embedding_fingerprint:
            raise InferenceError("gcb_fingerprint_mismatch", "manifest gcb fingerprint differs from its fields")
        self._executor = ThreadPoolExecutor(max_workers=self.workers, thread_name_prefix="inference")
        try:
            self.charcnn = self._executor.submit(
                self._load, "charcnn_load_failed", charcnn_factory or load_charcnn, bundle.checkpoint_path
            ).result()
            if getattr(self.charcnn, "arch_version", None) != CHARCNN_ARCH_VERSION:
                raise InferenceError("charcnn_not_v2", f"CharCNN arch_version {getattr(self.charcnn, 'arch_version', None)!r}")
            self.gcb = None
            if self.gcb_enabled:
                kwargs = {k: self.gcb_fields[k] for k in GCB_CONFIG_FIELDS}
                self.gcb = self._executor.submit(self._load, "gcb_load_failed", gcb_factory or load_gcb, kwargs).result()
                self._check_revision()
        except BaseException:
            self._executor.shutdown(wait=False)
            raise
        logger.info(
            "Real engine ready: CharCNN v%s, GraphCodeBERT %s (fingerprint %s), %d inference worker(s).",
            CHARCNN_ARCH_VERSION, "v2/mean" if self.gcb_enabled else "disabled", self.embedding_fingerprint[:12], self.workers,
        )

    @staticmethod
    def _gcb_fields(gcb: Mapping[str, Any], settings) -> Dict[str, Any]:
        fields = {k: gcb.get(k) for k in FINGERPRINT_FIELDS}
        missing = [k for k, v in fields.items() if v is None]
        if missing:
            raise InferenceError("gcb_config_missing", f"manifest gcb section lacks {missing}")
        if fields["input_version"] != settings.GCB_INPUT_VERSION or fields["pooling"] != settings.GCB_POOLING:
            raise InferenceError(
                "gcb_config_mismatch",
                f"settings {settings.GCB_INPUT_VERSION}/{settings.GCB_POOLING} != manifest "
                f"{fields['input_version']}/{fields['pooling']}",
            )
        return fields

    @staticmethod
    def _load(reason: str, factory: Callable, arg):
        try:
            return factory(arg)
        except InferenceError:
            raise
        except Exception as exc:
            raise InferenceError(reason, f"{type(exc).__name__}: {exc}") from exc

    def _check_revision(self) -> None:
        encoder = getattr(self.gcb, "encoder", None)
        loaded = getattr(getattr(encoder, "config", None), "_commit_hash", None)
        if isinstance(loaded, str) and loaded and loaded != self.gcb_fields["model_revision"]:
            raise InferenceError("gcb_revision_mismatch", f"loaded {loaded[:12]} != manifest revision")

    @property
    def model_versions(self) -> Dict[str, Any]:
        return {
            "charcnn_arch_version": getattr(self.charcnn, "arch_version", None),
            "charcnn_preproc_version": getattr(self.charcnn, "preproc_version", None),
            "gcb_input_version": self.gcb_fields["input_version"] if self.gcb_enabled else None,
            "gcb_pooling": self.gcb_fields["pooling"] if self.gcb_enabled else None,
        }

    def readiness(self) -> Readiness:
        return Readiness(ready=True, details={"gcb_enabled": self.gcb_enabled, **self.model_versions})

    async def _run(self, fn, *args):
        return await asyncio.get_running_loop().run_in_executor(self._executor, fn, *args)

    async def extract_semantic_embedding(self, code: str, lang: str = "c") -> List[float]:
        if self.gcb is None:
            raise InferenceError("gcb_disabled", "GraphCodeBERT secondary signal is disabled")
        try:
            res = await self._run(self.gcb.predict_code, code, lang)
        except Exception as exc:
            raise InferenceError("gcb_failed", f"{type(exc).__name__}: {exc}") from exc
        embedding = res.get("embedding") if isinstance(res, dict) else None
        if not (isinstance(res, dict) and res.get("success") and isinstance(embedding, list)):
            raise InferenceError("gcb_embedding_failed", "GraphCodeBERT returned no embedding")
        if len(embedding) != EMBEDDING_DIM:
            raise InferenceError("gcb_embedding_failed", f"embedding has {len(embedding)} dims")
        if res.get("input_version") != self.gcb_fields["input_version"] or res.get("pooling") != self.gcb_fields["pooling"]:
            raise InferenceError("gcb_config_mismatch", "embedding came from another input version or pooling")
        return [float(v) for v in embedding]

    async def predict_stylometry(self, code: str) -> StylometryResult:
        try:
            res = await self._run(self.charcnn.predict_text, code)
        except Exception as exc:
            raise InferenceError("charcnn_failed", f"{type(exc).__name__}: {exc}") from exc
        # CI8.1: only the v2 keys `score`/`abstained`; legacy probability keys are never read.
        if not isinstance(res, dict) or not isinstance(res.get("abstained"), bool):
            raise InferenceError("charcnn_result_invalid", "CharCNN result lacks `abstained`")
        if res["abstained"]:
            return StylometryResult(raw_score=None, abstained=True)
        score = res.get("score")
        if isinstance(score, bool) or not isinstance(score, (int, float)):
            raise InferenceError("charcnn_result_invalid", "CharCNN result lacks a numeric `score`")
        return StylometryResult(raw_score=float(score), abstained=False)

    def close(self) -> None:
        self._executor.shutdown(wait=False)


def create_real_engine(settings, bundle) -> RealBimodalInferenceEngine:
    """Runtime engine factory (`build_runtime`)."""
    return RealBimodalInferenceEngine(bundle, settings)
