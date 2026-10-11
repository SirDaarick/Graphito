"""Typed domain errors. Each carries a stable `reason` code that is safe to expose (for example in
`/health`), while `str(error)` holds details meant for logs (it may name files, never secrets)."""


class GraphitoError(Exception):
    """Base error with a stable, path-free `reason` code."""

    def __init__(self, reason: str, message: str = ""):
        super().__init__(f"{reason}: {message}" if message else reason)
        self.reason = reason


class ArtifactError(GraphitoError):
    """A deploy artifact is missing, tampered with or inconsistent with the configuration."""


class InferenceError(GraphitoError):
    """A model failed to load or to run (no stub fallback exists in REAL mode)."""


class VectorStoreError(GraphitoError):
    """The vector store failed or returned a malformed result (never an empty result instead)."""


class NotReadyError(GraphitoError):
    """The inference engine or its artifacts are not ready; scoring and indexing must not run."""
