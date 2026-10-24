"""REAL inference engine: CharCNN v2 (Channel B) and GraphCodeBERT v2_norm (secondary).

Fail closed (spec AS6.1): any load or configuration problem raises `InferenceError` with a stable
reason code; there is no fallback to fake values. Models load from the verified deploy bundle
(the CharCNN checkpoint listed in the manifest) and GraphCodeBERT is built as v2 with mean pooling.
When the bundle lists a trained LoRA adapter (`gcb.adapter`, installed by
`scripts/add_gcb_adapter_to_deploy.py`) and `GCB_ADAPTER_ENABLED` is true, the adapter is merged into the
encoder (`models.graphcodebert.v2.finetuned`) and its identity enters the engine fingerprint; otherwise the
zero-shot facade is used, which never loads an adapter. Code is canonicalized (user identifiers renamed,
`models/logic_eval/canonical.py`) right before embedding, in `extract_semantic_embedding` only, so
single, async, batch, reference creation and the reindex script all inherit it. If canonicalization
raises, the file is embedded raw and `CANONICALIZATION_FALLBACK` is set for the caller.

Torch never runs on the event loop (AS9.1, D10): loading and every prediction go through a
dedicated `ThreadPoolExecutor(max_workers=INFERENCE_WORKERS, thread_name_prefix="inference")`.

The embedding fingerprint (D12) is the sha256 of the canonical JSON of the embedding pipeline
fields from the manifest; it must equal the manifest's own fingerprint and selects the Chroma
collection, so embeddings from different pipelines never mix. The manifest fingerprint covers the
model pipeline; the engine fingerprint (collection name) also folds in the canonicalization version.
"""

import asyncio
import hashlib
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional

from app.domain.errors import InferenceError
from app.domain.ports.inference_port import CANONICALIZATION_FALLBACK, InferencePort, Readiness, StylometryResult
from app.infrastructure.artifacts.models_path import ensure_on_path

logger = logging.getLogger(__name__)

CHARCNN_ARCH_VERSION = 2
# Version of the identifier canonicalization applied before embedding (GraphCodeBERT `v2_norm`).
CANONICALIZATION_VERSION = "identifiers_v1"
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


def pipeline_fingerprint(manifest_fingerprint: str, canonicalization: str, adapter_sha256: Optional[str] = None) -> str:
    """Engine fingerprint: the manifest pipeline fingerprint plus the canonicalization version and, when the
    trained adapter is used, its identity. Without an adapter the value is the one computed before adapters
    existed, so the zero-shot Chroma collection keeps its name."""
    fields = {"canonicalization": canonicalization, "pipeline": manifest_fingerprint}
    if adapter_sha256 is not None:
        fields["adapter"] = adapter_sha256
    return hashlib.sha256(json.dumps(fields, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def load_canonicalizer() -> Callable[[str, str], str]:
    """`canonicalize_code(code, lang)` (runs on an inference thread)."""
    ensure_on_path()
    from models.logic_eval.canonical import canonicalize_code

    return canonicalize_code


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


def load_gcb_adapter(args: Dict[str, Any]):
    """GraphCodeBERT v2 with the trained LoRA adapter merged in (runs on an inference thread).
    `args` is `{"config": <GraphCodeBERTConfig kwargs>, "adapter_dir": <verified adapter directory>}`."""
    ensure_on_path()
    from models.graphcodebert.config import GraphCodeBERTConfig
    from models.graphcodebert.v2.finetuned import FineTunedGraphCodeBERT

    return FineTunedGraphCodeBERT(args["adapter_dir"], config=GraphCodeBERTConfig(**args["config"]))


class RealBimodalInferenceEngine(InferencePort):
    engine = "real"

    def __init__(
        self,
        bundle,
        settings,
        *,
        charcnn_factory: Optional[Callable[[Path], Any]] = None,
        gcb_factory: Optional[Callable[[Dict[str, Any]], Any]] = None,
        gcb_adapter_factory: Optional[Callable[[Dict[str, Any]], Any]] = None,
        canonicalizer: Optional[Callable[[str, str], str]] = None,
    ):
        self.workers = int(settings.INFERENCE_WORKERS)
        self.gcb_enabled = bool(settings.GCB_SECONDARY_ENABLED)
        self.gcb_fields = self._gcb_fields(bundle.gcb, settings)
        manifest_fingerprint = embedding_fingerprint(self.gcb_fields)
        if bundle.gcb.get("fingerprint") != manifest_fingerprint:
            raise InferenceError("gcb_fingerprint_mismatch", "manifest gcb fingerprint differs from its fields")
        self.canonicalization = CANONICALIZATION_VERSION
        # The trained adapter is used when the verified bundle lists it and the setting allows it.
        use_adapter = self.gcb_enabled and bool(getattr(settings, "GCB_ADAPTER_ENABLED", True)) and getattr(bundle, "gcb_adapter_dir", None) is not None
        self.adapter_name = bundle.gcb_adapter_name if use_adapter else None
        self.adapter_sha256 = bundle.gcb_adapter_sha256 if use_adapter else None
        self.embedding_fingerprint = pipeline_fingerprint(manifest_fingerprint, self.canonicalization, self.adapter_sha256)
        self._canonicalize = canonicalizer
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
                if use_adapter:
                    adapter_args = {"config": kwargs, "adapter_dir": bundle.gcb_adapter_dir}
                    self.gcb = self._executor.submit(
                        self._load, "gcb_adapter_load_failed", gcb_adapter_factory or load_gcb_adapter, adapter_args
                    ).result()
                else:
                    self.gcb = self._executor.submit(self._load, "gcb_load_failed", gcb_factory or load_gcb, kwargs).result()
                self._check_revision()
                if self._canonicalize is None:
                    self._canonicalize = self._executor.submit(
                        self._load, "canonicalizer_load_failed", lambda _: load_canonicalizer(), None
                    ).result()
        except BaseException:
            self._executor.shutdown(wait=False)
            raise
        logger.info(
            "Real engine ready: CharCNN v%s, GraphCodeBERT %s+%s%s (fingerprint %s), %d inference worker(s).",
            CHARCNN_ARCH_VERSION, "v2/mean" if self.gcb_enabled else "disabled", self.canonicalization,
            f"+adapter {self.adapter_name}" if self.adapter_name else "", self.embedding_fingerprint[:12], self.workers,
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
        versions = {
            "charcnn_arch_version": getattr(self.charcnn, "arch_version", None),
            "charcnn_preproc_version": getattr(self.charcnn, "preproc_version", None),
            "gcb_input_version": self.gcb_fields["input_version"] if self.gcb_enabled else None,
            "gcb_pooling": self.gcb_fields["pooling"] if self.gcb_enabled else None,
            "gcb_canonicalization": self.canonicalization if self.gcb_enabled else None,
        }
        if self.adapter_sha256 is not None:  # absent (not null) without the adapter: older reports keep their shape
            versions["gcb_adapter"] = self.adapter_name
            versions["gcb_adapter_sha256"] = self.adapter_sha256
        return versions

    def readiness(self) -> Readiness:
        return Readiness(ready=True, details={"gcb_enabled": self.gcb_enabled, **self.model_versions})

    async def _run(self, fn, *args):
        return await asyncio.get_running_loop().run_in_executor(self._executor, fn, *args)

    def _canonical_predict(self, code: str, lang: str):
        """Canonicalize then embed (inference thread). Returns `(result, fell_back_to_raw)`."""
        fell_back = False
        try:
            canonical = self._canonicalize(code, lang)
            if not isinstance(canonical, str):
                raise TypeError("canonicalizer returned a non-string")
        except Exception as exc:
            logger.warning("Identifier canonicalization failed (%s); embedding raw code.", type(exc).__name__)
            canonical, fell_back = code, True
        return self.gcb.predict_code(canonical, lang), fell_back

    async def extract_semantic_embedding(self, code: str, lang: str = "c") -> List[float]:
        if self.gcb is None:
            raise InferenceError("gcb_disabled", "GraphCodeBERT secondary signal is disabled")
        try:
            res, fell_back = await self._run(self._canonical_predict, code, lang)
        except Exception as exc:
            raise InferenceError("gcb_failed", f"{type(exc).__name__}: {exc}") from exc
        CANONICALIZATION_FALLBACK.set(fell_back)
        embedding = res.get("embedding") if isinstance(res, dict) else None
        if not (isinstance(res, dict) and res.get("success") and isinstance(embedding, list)):
            raise InferenceError("gcb_embedding_failed", "GraphCodeBERT returned no embedding")
        if len(embedding) != EMBEDDING_DIM:
            raise InferenceError("gcb_embedding_failed", f"embedding has {len(embedding)} dims")
        if res.get("input_version") != self.gcb_fields["input_version"] or res.get("pooling") != self.gcb_fields["pooling"]:
            raise InferenceError("gcb_config_mismatch", "embedding came from another input version or pooling")
        if self.adapter_sha256 is not None and res.get("adapter_loaded") is not True:
            raise InferenceError("gcb_config_mismatch", "embedding was not produced with the deployed adapter")
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
