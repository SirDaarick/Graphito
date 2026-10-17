"""Read-only catalog of preloaded ESCOM programs, loaded once from a bundled JSON file."""
import json
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, Optional, Tuple

CATALOG_PATH = Path(__file__).resolve().parents[2] / "data" / "catalog_escom.json"

MATERIA_NAMES = {
    "algoritmos_estructuras_datos": "Algoritmos y Estructuras de Datos",
    "analisis_diseño_algoritmos": "Análisis y Diseño de Algoritmos",
    "fundamentos_programación": "Fundamentos de Programación",
    "paradigmas_programación": "Paradigmas de Programación",
}

_UNIT_RE = re.compile(r"^Unidad_([IVXLC]+)_(.+)$")
_LEADING_NUMBER_RE = re.compile(r"^\d+[_-]*")


@dataclass(frozen=True)
class CatalogEntry:
    id: str
    titulo: str
    materia: str
    materia_nombre: str
    unidad: str
    unidad_nombre: str
    lenguaje: str
    nombre_archivo: str
    codigo: str


def _slug(text: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9_-]", "", ascii_text.lower())


def _title_from_filename(nombre_archivo: str) -> str:
    stem = Path(nombre_archivo).stem
    words = _LEADING_NUMBER_RE.sub("", stem).replace("_", " ").strip() or stem
    return words[:1].upper() + words[1:]


def _materia_nombre(materia: str) -> str:
    return MATERIA_NAMES.get(materia) or materia.replace("_", " ").title()


def _unidad_nombre(unidad: str) -> str:
    match = _UNIT_RE.match(unidad)
    if match:
        return f"Unidad {match.group(1)} · {match.group(2).replace('_', ' ')}"
    return unidad.replace("_", " ")


@lru_cache(maxsize=1)
def load_catalog() -> Tuple[CatalogEntry, ...]:
    """All entries in file order; raises ValueError if the derived ids are not unique."""
    raw = json.loads(CATALOG_PATH.read_text(encoding="utf-8-sig"))
    entries = []
    seen = set()
    for item in raw:
        entry_id = f"{_slug(item['materia'])}--{_slug(Path(item['nombre_archivo']).stem)}"
        if entry_id in seen:
            raise ValueError(f"Duplicate catalog id: {entry_id}")
        seen.add(entry_id)
        entries.append(
            CatalogEntry(
                id=entry_id,
                titulo=_title_from_filename(item["nombre_archivo"]),
                materia=item["materia"],
                materia_nombre=_materia_nombre(item["materia"]),
                unidad=item["unidad"],
                unidad_nombre=_unidad_nombre(item["unidad"]),
                lenguaje=item["lenguaje"],
                nombre_archivo=item["nombre_archivo"],
                codigo=item["codigo"],
            )
        )
    return tuple(entries)


@lru_cache(maxsize=1)
def _index() -> Dict[str, CatalogEntry]:
    return {entry.id: entry for entry in load_catalog()}


def get_catalog_entry(entry_id: str) -> Optional[CatalogEntry]:
    return _index().get(entry_id)
