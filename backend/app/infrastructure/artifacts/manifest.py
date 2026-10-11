"""Reading and integrity checks of the deploy manifest (`graphito.deploy-manifest/v1`, design D6).

Every failure raises `ArtifactError` with a stable `reason` code. The code is safe to expose in
`/health`, while `str(error)` is meant for logs. Paths in the manifest must be relative POSIX
paths that stay inside the manifest's directory, and every listed file must exist and match its
sha256.
"""

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Dict, Mapping, Union

SCHEMA = "graphito.deploy-manifest/v1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_CHUNK = 1 << 20


class ArtifactError(Exception):
    """A deploy artifact is missing, tampered with or inconsistent with the configuration."""

    def __init__(self, reason: str, message: str):
        super().__init__(f"{reason}: {message}")
        self.reason = reason


@dataclass(frozen=True)
class DeployManifest:
    path: Path
    sha256: str
    doc: Dict[str, Any] = field(repr=False)

    @property
    def root(self) -> Path:
        return self.path.parent

    @property
    def files(self) -> Dict[str, str]:
        return self.doc["files"]

    def channel(self, name: str) -> Dict[str, Any]:
        section = self.doc.get(name)
        if not isinstance(section, Mapping):
            raise ArtifactError("manifest_invalid", f"manifest lacks the {name!r} section")
        return dict(section)

    def resolve(self, rel: str) -> Path:
        return resolve_relative(self.root, rel)


def file_sha256(path: Union[str, Path]) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_relative(root: Path, rel: Any) -> Path:
    """`root / rel` for a relative POSIX path that cannot leave `root`."""
    if not isinstance(rel, str) or not rel or "\\" in rel or ":" in rel:
        raise ArtifactError("path_escapes", f"manifest path {rel!r} is not a relative POSIX path")
    posix = PurePosixPath(rel)
    if posix.is_absolute() or ".." in posix.parts:
        raise ArtifactError("path_escapes", f"manifest path {rel!r} escapes the deploy directory")
    path = (root / Path(*posix.parts)).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ArtifactError("path_escapes", f"manifest path {rel!r} escapes the deploy directory")
    return path


def read_manifest(path: Union[str, Path]) -> DeployManifest:
    """Parse and structurally validate the manifest (no artifact file is read here)."""
    path = Path(path)
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        raise ArtifactError("manifest_missing", f"deploy manifest not found: {path.name}") from None
    except OSError as exc:
        raise ArtifactError("manifest_missing", f"deploy manifest unreadable: {type(exc).__name__}") from None
    try:
        doc = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ArtifactError("manifest_invalid", f"deploy manifest is not UTF-8 JSON ({exc})") from None
    if not isinstance(doc, Mapping):
        raise ArtifactError("manifest_invalid", "deploy manifest must be a JSON object")
    if doc.get("schema") != SCHEMA:
        raise ArtifactError("unknown_schema", f"unknown deploy manifest schema {doc.get('schema')!r} (want {SCHEMA})")
    files = doc.get("files")
    if not isinstance(files, Mapping) or not files:
        raise ArtifactError("manifest_invalid", "deploy manifest lists no files")
    manifest = DeployManifest(path.resolve(), hashlib.sha256(raw).hexdigest(), dict(doc))
    for rel, sha in files.items():
        manifest.resolve(rel)
        if not isinstance(sha, str) or not _SHA256.match(sha):
            raise ArtifactError("manifest_invalid", f"invalid sha256 for {rel!r}")
    split = doc.get("split_manifest_sha256")
    if not isinstance(split, str) or not _SHA256.match(split):
        raise ArtifactError("manifest_invalid", "deploy manifest lacks split_manifest_sha256")
    return manifest


def verify_files(manifest: DeployManifest) -> None:
    """Every listed file exists and matches its sha256."""
    for rel, expected in sorted(manifest.files.items()):
        path = manifest.resolve(rel)
        if not path.is_file():
            raise ArtifactError("file_missing", f"deploy artifact missing: {rel}")
        if file_sha256(path) != expected:
            raise ArtifactError("sha_mismatch", f"deploy artifact sha256 differs from the manifest: {rel}")
