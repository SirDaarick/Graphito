"""Build the committed example fixture of the "Ejemplo" group from the golden set (test split).

Every task of `data/golden_set/corpus/` written in C is scored with the backend's shared scoring path
(`ScoringService.score_code`, `INFERENCE_MODE=REAL`, artifacts in `models/deploy/`). A task is kept only
when its four example submissions behave as the example group needs:

- identical: a copy of the reference with Channel A flag true and Channel B flag false (the reference
  file itself when no corpus copy qualifies);
- similar: the student's own solution, both flags false, with the highest raw Channel A among those;
- different: the reference code of another task, Channel A flag false, lowest raw Channel A of the four;
- ai: an LLM-generated solution with Channel B flag true and Channel A flag false.

All numbers come from the real scoring run; nothing is invented. The output follows contract C1 of
`odd/tasks/example-group.md` and is read at runtime by the backend, never recomputed.

Usage (from the repository root):
  python scripts/build_example_fixture.py [--out PATH] [--count 5] [--dry-run]
Exits non-zero when fewer than `--count` tasks qualify.
"""

import argparse
import asyncio
import dataclasses
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "data" / "golden_set" / "corpus"
DEFAULT_OUT = ROOT / "backend" / "app" / "data" / "examples" / "ejemplo_fixture.json"
MAX_READABLE_LINES = 120

os.environ["INFERENCE_MODE"] = "REAL"  # the fixture is a real measurement; never a stub fallback
sys.path.insert(0, str(ROOT / "backend"))

from app.application.services.scoring_service import ScoringService  # noqa: E402
from app.config import settings  # noqa: E402
from app.domain.ports.vector_store_port import VectorStorePort  # noqa: E402
from app.domain.scoring import ScoringOutcome  # noqa: E402
from app.infrastructure.inference.runtime import build_runtime  # noqa: E402
from app.infrastructure.vector_store.chroma_adapter import (  # noqa: E402
    ChromaVectorStoreAdapter,
    collection_name_for_engine,
)

REFERENCE_AUTHOR = "Referencia del ejemplo"
AUTHORS = {
    "identical": "Ejemplo: copia de la referencia",
    "similar": "Ejemplo: solución propia",
    "different": "Ejemplo: código de otro problema",
    "ai": "Ejemplo: generado con IA",
}
CASES = ["identical", "similar", "different", "ai"]

# Spanish statements, written after reading each reference solution (the corpus has no statements).
META: Dict[str, Dict[str, str]] = {
    "A2017_Z4_Z1": {
        "titulo": "Insertar un número entre las palabras de un texto",
        "descripcion": (
            "Escribe la función ubaci_broj, que recibe una cadena de texto y un número entero y devuelve "
            "la misma cadena con el número insertado después de cada palabra, separado por espacios, "
            "modificándola en el sitio y respetando el signo del número."
        ),
    },
    "A2017_Z4_Z2": {
        "titulo": "Verificar las longitudes de las palabras de un texto",
        "descripcion": (
            "Escribe la función provjeri_duzine, que recibe una cadena, un arreglo de longitudes y su "
            "tamaño, y devuelve 1 si la cantidad de palabras de la cadena coincide con el tamaño del "
            "arreglo y cada palabra tiene exactamente la longitud indicada en su posición; en otro caso "
            "devuelve 0."
        ),
    },
    "A2016_Z3_Z3": {
        "titulo": "Eliminar filas y columnas repetidas de una matriz",
        "descripcion": (
            "Lee las dimensiones M y N (entre 1 y 200) y los elementos de una matriz de enteros, "
            "elimina las filas y las columnas que repiten el contenido de una anterior y muestra la "
            "matriz resultante."
        ),
    },
    "A2017_Z3_Z3": {
        "titulo": "Eliminar cifras indicadas de un arreglo de enteros",
        "descripcion": (
            "Lee un arreglo de enteros y un arreglo de cifras. Escribe la función izbaci_cifre, que "
            "quita de cada número las cifras listadas, comprueba que el arreglo de cifras no tenga "
            "repetidas ni valores fuera de 0 a 9, y el programa muestra los números resultantes."
        ),
    },
    "A2017_Z1_Z1": {
        "titulo": "Elegir el menú más económico para tres personas",
        "descripcion": (
            "Lee el plato elegido por tres personas (P, H o C), suma el costo del pedido en tres "
            "establecimientos con precios distintos, indica cuál resulta más económico y evalúa si "
            "aplicar el descuento en el restaurante lo volvería más barato."
        ),
    },
}


def _read(path: Path) -> Optional[str]:
    try:
        return path.read_bytes().decode("utf-8")
    except UnicodeDecodeError:
        return None


def _origin(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _line_count(code: str) -> int:
    return len(code.splitlines())


class Candidate:
    def __init__(self, path: Path, code: str, outcome: ScoringOutcome):
        self.path, self.code, self.outcome = path, code, outcome
        self.a, self.b = outcome.channel_a, outcome.channel_b

    @property
    def origin(self) -> str:
        return _origin(self.path)


def _evaluable(o: ScoringOutcome) -> bool:
    return o.channel_a.evaluable and o.channel_b.evaluable


async def _score_dir(
    scoring: ScoringService, directory: Path, ref: Tuple[str, str], pid: int
) -> List[Candidate]:
    out = []
    for path in sorted(directory.glob("*.c")):
        code = _read(path)
        if code is None or not code.strip():
            continue
        outcome = await scoring.score_code(code, [ref], language="c", problema_id=pid)
        if _evaluable(outcome):
            out.append(Candidate(path, code, outcome))
    return out


class TaskPick:
    """The identical, similar and ai picks of one task, before the different case is assigned."""

    def __init__(self, key: str, pid: int, ref: Candidate, identical: Candidate, similar: Candidate, ai: Candidate):
        self.key, self.pid, self.ref, self.identical, self.similar, self.ai = key, pid, ref, identical, similar, ai
        self.different: Optional[Candidate] = None

    @property
    def showcase_score(self) -> float:
        b = self.ai.b
        return (self.identical.a.raw - self.similar.a.raw) + (b.calibrated - b.threshold)


async def _pick_task(
    scoring: ScoringService, store: VectorStorePort, pid: int, key: str, rejected: Dict[str, str]
) -> Optional[TaskPick]:
    base = CORPUS / key
    ref_path = next(iter(sorted((base / "reference").glob("*.c"))), None)
    if ref_path is None:
        rejected[key] = "sin referencia en C"
        return None
    ref_code = _read(ref_path)
    if ref_code is None:
        rejected[key] = "la referencia no es UTF-8"
        return None
    ref = (ref_path.stem, ref_code)
    # Index the reference the way `ProblemService.add_reference_code` does, so GraphCodeBERT is measured.
    vector = await scoring.inference.extract_semantic_embedding(ref_code, lang="c")
    await store.upsert_reference(
        reference_id=f"{key}/{ref_path.stem}",
        embedding=vector,
        metadata={"problema_id": pid, "autor": REFERENCE_AUTHOR, "tipo": "REFERENCIA", "lenguaje": "c"},
        document=ref_code,
    )
    ref_outcome = await scoring.score_code(ref_code, [ref], language="c", problema_id=pid)
    ref_cand = Candidate(ref_path, ref_code, ref_outcome)

    copies = await _score_dir(scoring, base / "copy", ref, pid)
    originals = await _score_dir(scoring, base / "original", ref, pid)
    ais = await _score_dir(scoring, base / "ai", ref, pid)

    ident = [c for c in copies if c.a.flag is True and c.b.flag is False]
    if ident:
        identical = max(ident, key=lambda c: c.a.raw)
    elif _evaluable(ref_outcome) and ref_outcome.channel_a.flag is True and ref_outcome.channel_b.flag is False:
        identical = ref_cand
    else:
        rejected[key] = "ninguna copia ni la referencia cumple el caso idéntico"
        return None

    sim = [c for c in originals if c.a.flag is False and c.b.flag is False]
    if not sim:
        rejected[key] = "ninguna solución propia con ambas banderas apagadas"
        return None
    similar = max(sim, key=lambda c: c.a.raw)

    ai_ok = [c for c in ais if c.b.flag is True and c.a.flag is False]
    if not ai_ok:
        rejected[key] = "ninguna solución de IA con B encendido y A apagado"
        return None
    ai = max(ai_ok, key=lambda c: c.b.calibrated)

    return TaskPick(key, pid, ref_cand, identical, similar, ai)


async def _assign_different(scoring: ScoringService, picks: List[TaskPick]) -> Dict[str, str]:
    """Reference code of another selected task, scored against this task's reference (cyclic order)."""
    rejected: Dict[str, str] = {}
    n = len(picks)
    for i, pick in enumerate(picks):
        others = [picks[(i + k) % n] for k in range(1, n)]
        for other in others:
            outcome = await scoring.score_code(
                other.ref.code, [(pick.ref.path.stem, pick.ref.code)], language="c", problema_id=pick.pid
            )
            if not _evaluable(outcome):
                continue
            cand = Candidate(other.ref.path, other.ref.code, outcome)
            floor = min(pick.identical.a.raw, pick.similar.a.raw, pick.ai.a.raw)
            if cand.a.flag is False and cand.a.raw < floor:
                pick.different = cand
                break
        if pick.different is None:
            rejected[pick.key] = "ningún código de otro problema queda con A apagado y el menor A bruto"
    return rejected


def _serialize_outcome(o: ScoringOutcome) -> dict:
    prov = {k: v for k, v in o.provenance.items() if k != "tiempos_ms"}
    keep = ("canal_a_metodo", "manifest_sha", "checkpoint_sha_b", "gcb_estado", "label")
    return {
        "channel_a": dataclasses.asdict(o.channel_a),
        "channel_b": dataclasses.asdict(o.channel_b),
        "gcb_similarity": o.gcb_similarity,
        "engine": o.engine,
        "provenance": {k: prov.get(k) for k in keep},
    }


def _problem(pick: TaskPick) -> dict:
    meta = META[pick.key]
    cases = {"identical": pick.identical, "similar": pick.similar, "different": pick.different, "ai": pick.ai}
    return {
        "key": pick.key,
        "titulo": meta["titulo"],
        "descripcion": meta["descripcion"],
        "lenguaje": "c",
        "referencia": {"autor": REFERENCE_AUTHOR, "contenido": pick.ref.code},
        "entregas": [
            {
                "caso": case,
                "autor": AUTHORS[case],
                "origen": cases[case].origin,
                "contenido": cases[case].code,
                "outcome": _serialize_outcome(cases[case].outcome),
            }
            for case in CASES
        ],
    }


def _print_table(picks: List[TaskPick]) -> None:
    head = f"{'tarea':<14}{'caso':<10}{'A raw':>8}{'A cal':>8}{'flagA':>7}{'B raw':>8}{'B cal':>8}{'flagB':>7}{'GCB':>8}  origen"
    print(head)
    for p in picks:
        for case in CASES:
            c = getattr(p, case)
            print(
                f"{p.key:<14}{case:<10}{c.a.raw:>8.4f}{c.a.calibrated:>8.4f}{str(c.a.flag):>7}"
                f"{c.b.raw:>8.4f}{c.b.calibrated:>8.4f}{str(c.b.flag):>7}{c.outcome.gcb_similarity!s:>8}  {c.origin}"
            )


async def _run(count: int, dry_run: bool, out: Path) -> int:
    runtime = build_runtime(settings)
    if not runtime.ready:
        print(f"Inferencia REAL no lista (engine={runtime.engine_label}, motivo={runtime.reason}).", file=sys.stderr)
        return 2
    import chromadb

    # The production adapter over an in-memory Chroma client: same collection naming and cosine space as live.
    store = ChromaVectorStoreAdapter(
        collection_name_for_engine(runtime.engine),
        client=chromadb.EphemeralClient(),
        fingerprint=runtime.engine.embedding_fingerprint,
    )
    scoring = ScoringService(runtime.engine, runtime.calibration, store, runtime.lexical)
    try:
        rejected: Dict[str, str] = {}
        picks: List[TaskPick] = []
        for pid, task_dir in enumerate(sorted(p for p in CORPUS.iterdir() if p.is_dir()), start=1):
            pick = await _pick_task(scoring, store, pid, task_dir.name, rejected)
            if pick is not None:
                picks.append(pick)
                print(f"[ok] {task_dir.name}: líneas de referencia={_line_count(pick.ref.code)}")

        # Readable references first (teachers read them), then shortest; the shortlist is the candidate pool.
        picks.sort(key=lambda p: (_line_count(p.ref.code) >= MAX_READABLE_LINES, _line_count(p.ref.code), p.key))
        pool = picks
        rejected.update(await _assign_different(scoring, pool))
        qualified = [p for p in pool if p.different is not None][:count]
        for p in pool:
            if p not in qualified and p.key not in rejected:
                rejected[p.key] = "fuera de los primeros candidatos más legibles"
        for key, why in sorted(rejected.items()):
            print(f"[descartada] {key}: {why}")
        if len(qualified) < count:
            print(f"Solo {len(qualified)} de {count} tareas cumplen los cuatro casos.", file=sys.stderr)
            return 1

        qualified.sort(key=lambda p: p.showcase_score, reverse=True)  # problems[0] is the tour showcase
        _print_table(qualified)
        if dry_run:
            print("--dry-run: no se escribe el archivo.")
            return 0
        missing = [p.key for p in qualified if p.key not in META]
        if missing:
            print(f"Falta título y descripción en META para: {', '.join(missing)}", file=sys.stderr)
            return 3
        manifest_sha = qualified[0].identical.outcome.provenance.get("manifest_sha")
        fixture = {
            "version": 1,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "manifest_sha": manifest_sha,
            "engine": "real",
            "problems": [_problem(p) for p in qualified],
        }
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(fixture, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Escrito {out}")
        return 0
    finally:
        close = getattr(runtime.engine, "close", None)
        if callable(close):
            close()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--count", type=int, default=5)
    ap.add_argument("--dry-run", action="store_true", help="score and print the table without writing")
    args = ap.parse_args()
    sys.exit(asyncio.run(_run(args.count, args.dry_run, args.out)))


if __name__ == "__main__":
    main()
