import re
from typing import List, Dict, Any, Optional

from app.domain.scoring import ScoringOutcome

ORIGEN_DECISION = "decision"
ORIGEN_HEURISTICA = "heuristica"


class XAIService:
    """
    Explicaciones para el docente (spec AR4). Las filas se derivan de las banderas de decisión
    calibradas: nunca de umbrales fijos en este módulo. Las reglas por línea son heurísticas
    (no salida del modelo) y se etiquetan así.
    """

    # Patrones estilométricos característicos de modelos generativos (LLMs)
    LLM_COMMENT_PATTERNS = [
        (
            r"//\s*(Time complexity|Complejidad temporal|Time Complexity)",
            "Comentario formal de análisis asintótico típico de modelos LLM.",
            "ESTILO_LLM",
            "MEDIA",
        ),
        (
            r"//\s*(Space complexity|Complejidad espacial|Space Complexity)",
            "Declaración explícita de complejidad espacial característica de código generado.",
            "ESTILO_LLM",
            "MEDIA",
        ),
        (
            r"//\s*(Helper function|Función auxiliar|Utility function)",
            "Comentario estructurado redundantemente antes de una función secundaria.",
            "ESTILO_LLM",
            "BAJA",
        ),
        (
            r"//\s*(Base case|Caso base)",
            "Comentario de libro de texto en recursión elemental.",
            "ESTILO_LLM",
            "BAJA",
        ),
        (
            r"//\s*(Driver code|Código principal|Test cases|Casos de prueba)",
            "Etiqueta de ejecución común en prompts de código autogenerado.",
            "ESTILO_LLM",
            "MEDIA",
        ),
        (
            r"//\s*Step\s*\d+:|//\s*Paso\s*\d+:",
            "Explicación paso a paso numerada generada por IA pedagógica.",
            "ESTILO_LLM",
            "MEDIA",
        ),
    ]

    # Inclusiones avanzadas o construcciones atípicas para cursos introductorios de C/C++
    ADVANCED_CONSTRUCTS = [
        (
            r"#include\s*<algorithm>",
            "Inclusión de <algorithm> en práctica elemental donde se evalúa algoritmia básica manual.",
            "NIVEL_AVANZADO",
            "MEDIA",
        ),
        (
            r"#include\s*<tuple>|#include\s*<utility>",
            "Uso de tuplas y utilidades modernas en problemas introductorios de estructuras.",
            "NIVEL_AVANZADO",
            "MEDIA",
        ),
        (
            r"\bstd::chrono\b",
            "Medición de rendimiento de alta precisión en ejercicio no profilado.",
            "NIVEL_AVANZADO",
            "BAJA",
        ),
        (
            r"\[.*?\]\s*\(.*?\)\s*(?:->.*?)?\s*\{",
            "Expresión lambda moderna en código escolar de primer año.",
            "NIVEL_AVANZADO",
            "ALTA",
        ),
        (
            r"\bauto\b\s+[a-zA-Z_]\w*\s*=",
            "Inferencia automática de tipos ('auto') atípica en sintaxis académica inicial de C.",
            "NIVEL_AVANZADO",
            "BAJA",
        ),
    ]

    @classmethod
    def extract_explanations(
        cls,
        code: str,
        language: str = "c",
        outcome: Optional[ScoringOutcome] = None,
    ) -> List[Dict[str, Any]]:
        """Explanations for one scored submission, consistent with its decision (spec AR4).

        - A file-level `SIMILITUD_ARCHIVO` row (origin `decision`) only when `flag_a` is true: the
          raw and calibrated Channel A Jaccard, the artifact threshold and key, and the argmax
          reference. Nothing asserts similarity when `flag_a` is false or null.
        - Rule-based line rows (origin `heuristica`, labelled "no es salida del modelo") only when
          `flag_b` is true, so a stylistic pattern never contradicts a negative or abstained
          Channel B. Without an outcome there is no decision to explain and nothing is returned.
        """
        explanations: List[Dict[str, Any]] = []
        if not code or outcome is None:
            return explanations

        if outcome.flag_a is True:
            explanations.append(cls._file_similarity_row(outcome))
        if outcome.flag_b is True:
            explanations.extend(cls._heuristic_rows(code))
        return explanations

    @staticmethod
    def _file_similarity_row(outcome: ScoringOutcome) -> Dict[str, Any]:
        a = outcome.channel_a
        author = (outcome.provenance or {}).get("reference_author")
        reference = f"{author} ({outcome.reference_id})" if author else str(outcome.reference_id)
        raw = "no disponible" if a.raw is None else f"{a.raw:.4f}"
        return {
            "numero_linea": None,
            "tipo_alerta": "Similitud léxica con la referencia (archivo completo)",
            "descripcion": (
                f"Jaccard léxico (shingles de 5 tokens) {raw}; calibrado {a.calibrated:.4f} >= umbral "
                f"{a.threshold:.4f} ({a.threshold_key}). Referencia más cercana: {reference}."
            ),
            "severidad": "ALTA",
            "categoria": "SIMILITUD_ARCHIVO",
            "reference_id": outcome.reference_id,
            "origen": ORIGEN_DECISION,
        }

    @classmethod
    def _heuristic_rows(cls, code: str) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for idx, line in enumerate(code.split("\n"), start=1):
            line_str = line.strip()
            if not line_str:
                continue
            for patterns, titulo, flags in (
                (cls.LLM_COMMENT_PATTERNS, "Patrón de Documentación LLM", re.IGNORECASE),
                (cls.ADVANCED_CONSTRUCTS, "Construcción Atípica para Nivel Escolar", 0),
            ):
                for pattern, reason, categoria, severidad in patterns:
                    if re.search(pattern, line_str, flags):
                        rows.append({
                            "numero_linea": idx,
                            "tipo_alerta": f"Heurística: {titulo}",
                            "descripcion": f"Heurística (no es salida del modelo). Línea {idx}: {reason}",
                            "severidad": severidad,
                            "categoria": categoria,
                            "origen": ORIGEN_HEURISTICA,
                        })
                        break
        return rows

    @classmethod
    def compute_code_metrics(cls, code: str) -> Dict[str, Any]:
        """
        Calcula métricas sintácticas y de complejidad de código.
        """
        if not code:
            return {
                "total_lineas": 0,
                "lineas_codigo": 0,
                "lineas_comentarios": 0,
                "densidad_comentarios": "0%",
                "complejidad_ciclomatica": 1,
            }

        lines = code.split("\n")
        total_lines = len(lines)
        comment_lines = 0
        code_lines = 0

        # Estimación heurística de complejidad ciclomática de McCabe:
        # 1 + conteo de estructuras de decisión (if, for, while, case, catch, &&, ||)
        decision_points = len(re.findall(r"\b(if|for|while|case|catch)\b|&&|\|\|", code))
        complexity = 1 + decision_points

        in_multiline_comment = False
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            if in_multiline_comment:
                comment_lines += 1
                if "*/" in stripped:
                    in_multiline_comment = False
                continue

            if stripped.startswith("/*"):
                comment_lines += 1
                if "*/" not in stripped:
                    in_multiline_comment = True
                continue

            if stripped.startswith("//"):
                comment_lines += 1
            else:
                code_lines += 1

        density = round((comment_lines / max(total_lines, 1)) * 100, 1)

        return {
            "total_lineas": total_lines,
            "lineas_codigo": code_lines,
            "lineas_comentarios": comment_lines,
            "densidad_comentarios": f"{density}%",
            "complejidad_ciclomatica": complexity,
        }
