import re
from typing import List, Dict, Any, Optional


class XAIService:
    """
    Servicio de Inteligencia Artificial Explicable (Explainable AI - XAI) para Graphito.
    Transforma probabilidades algorítmicas en evidencias visuales y pedagógicas concretas.
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
        semantic_sim: float = 0.0,
        ai_prob: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """
        Analiza el código línea por línea y genera la lista de evidencias técnicas contextualizadas.
        """
        explanations: List[Dict[str, Any]] = []
        if not code:
            return explanations

        lines = code.split("\n")

        # 1. Reglas estilométricas de LLMs
        for idx, line in enumerate(lines, start=1):
            line_str = line.strip()
            if not line_str:
                continue

            for pattern, reason, categoria, severidad in cls.LLM_COMMENT_PATTERNS:
                if re.search(pattern, line_str, re.IGNORECASE):
                    explanations.append(
                        {
                            "numero_linea": idx,
                            "tipo_alerta": "Patrón de Documentación LLM",
                            "descripcion": f"Línea {idx}: {reason}",
                            "severidad": severidad,
                            "categoria": categoria,
                        }
                    )
                    break

            for pattern, reason, categoria, severidad in cls.ADVANCED_CONSTRUCTS:
                if re.search(pattern, line_str):
                    explanations.append(
                        {
                            "numero_linea": idx,
                            "tipo_alerta": "Construcción Atípica para Nivel Escolar",
                            "descripcion": f"Línea {idx}: {reason}",
                            "severidad": severidad,
                            "categoria": categoria,
                        }
                    )
                    break

        # 2. Detección de isomorfismo y flujo de datos
        if semantic_sim >= 0.80:
            # Buscar la función principal o bucle crítico para marcar evidencia de flujo
            critical_line = 1
            for idx, line in enumerate(lines, start=1):
                if re.search(r"\b(for|while|if|switch)\b", line):
                    critical_line = idx
                    break

            explanations.append(
                {
                    "numero_linea": critical_line,
                    "tipo_alerta": "Isomorfismo en Flujo de Datos (DFG)",
                    "descripcion": (
                        f"Línea {critical_line}: El grafo de flujo de variables y ramificaciones lógicas "
                        f"presenta una concordancia del {round(semantic_sim * 100, 1)}% con el código de referencia."
                    ),
                    "severidad": "CRITICA" if semantic_sim >= 0.90 else "ALTA",
                    "categoria": "ISOMORFISMO_DFG",
                }
            )

        # 3. Alerta global si probabilidad sintética es alta pero no se hallaron comentarios
        if ai_prob >= 0.75 and not any(e["categoria"] == "ESTILO_LLM" for e in explanations):
            explanations.append(
                {
                    "numero_linea": 1,
                    "tipo_alerta": "Anomalía Estilométrica Característica (CharCNN)",
                    "descripcion": (
                        f"El clasificador convolucional detectó una regularidad sintáctica atípica "
                        f"(probabilidad de síntesis del {round(ai_prob * 100, 1)}%) a nivel de espaciado y estructura."
                    ),
                    "severidad": "ALTA",
                    "categoria": "ESTILO_LLM",
                }
            )

        return explanations

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
