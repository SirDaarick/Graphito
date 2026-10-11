"""Inference readiness gate (spec AS6.2-AS6.3; design D5).

Scoring and indexing requests (`POST /analysis/run`, `POST /analysis/batch`,
`POST /problems/{id}/references`) get a 503 while the inference runtime is not ready. The gate
runs before routing, dependencies and handlers, so nothing is written to Postgres or the vector
store. `require_inference_ready` is the same check as a FastAPI dependency for routes that opt
in explicitly.
"""

import re
from typing import Any, Dict, Optional

from fastapi import HTTPException, status
from fastapi.responses import JSONResponse

from app.config import settings
from app.infrastructure.inference import runtime as inference_runtime

_API = re.escape(settings.API_V1_STR.rstrip("/"))
GATED_ROUTES = (
    ("POST", re.compile(rf"^{_API}/analysis/run/?$")),
    ("POST", re.compile(rf"^{_API}/analysis/batch/?$")),
    ("POST", re.compile(rf"^{_API}/problems/[^/]+/references/?$")),
)


def readiness_snapshot() -> Dict[str, Any]:
    """Path-free readiness; a runtime not started yet is ready only in STUB mode."""
    rt = inference_runtime.get_runtime()
    if rt is not None:
        return rt.health()
    stub = str(settings.INFERENCE_MODE).strip().upper() == "STUB"
    return {
        "engine": "stub" if stub else "real",
        "inference_ready": stub,
        "inference_error": None if stub else "not_started",
        "calibration_state": "stub" if stub else "unavailable",
        "artifacts": None,
    }


def not_ready_body(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "detail": "El motor de inferencia no está listo; no se analizó ni se guardó nada.",
        "inference_ready": False,
        "engine": snapshot.get("engine"),
        "reason": snapshot.get("inference_error") or "not_ready",
    }


def is_gated(method: str, path: str) -> bool:
    return any(method == m and pattern.match(path) for m, pattern in GATED_ROUTES)


def gate_response(method: str, path: str) -> Optional[JSONResponse]:
    """A 503 response when the request needs inference and the runtime is not ready."""
    if not is_gated(method, path):
        return None
    snapshot = readiness_snapshot()
    if snapshot["inference_ready"]:
        return None
    return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content=not_ready_body(snapshot))


def require_inference_ready() -> None:
    snapshot = readiness_snapshot()
    if not snapshot["inference_ready"]:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=not_ready_body(snapshot))
