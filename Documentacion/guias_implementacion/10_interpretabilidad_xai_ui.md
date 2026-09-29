# Guía de Implementación 10: Interpretabilidad de Modelos en la UI (Explainable AI / XAI)

## 1. Fundamentos & Filosofía de Arquitectura
En la evaluación de integridad académica, **un porcentaje abstracto carece de validez pedagógica y jurídica**.

Si un profesor acusa a un estudiante diciéndole: *"Graphito dice que tu código tiene 89% de probabilidad de ser generado por IA"*, la respuesta del estudiante será inmediata: *"¿En qué se basa el sistema? ¿Qué líneas son sospechosas?"*.

Si el docente no puede responder con evidencia visual concreta, el sistema fracasa como herramienta de apoyo a la decisión.

La **Inteligencia Artificial Explicable (XAI)** en Graphito debe responder a tres preguntas fundamentales en la UI:
1. **¿Qué partes del código causaron la alerta?** (Resaltado de líneas atípicas y patrones sintéticos).
2. **¿Por qué la lógica se considera idéntica a la referencia?** (Trazabilidad del Grafo de Flujo de Datos / DFG).
3. **¿Cuál es el desglose multidimensional?** (Separar la evaluación en 3 pilares independientes: *Semántica*, *Estilometría* y *Nivel Académico*).

---

## 2. Impacto en el Sistema
* **Backend (Inferencia & Servicios):**
  * Canal A: Extraer los nodos del DFG y AST que presentan correspondencia isomórfica con la referencia.
  * Canal B: Generar mapa de calor o puntajes de atribución a nivel de línea (usando gradientes o detección de patrones léxicos).
  * Generación de explicaciones contextualizadas en `IndicadorIntegridad`.
* **Frontend (React + Tailwind):**
  * Componente `XaiBreakdownRadar.tsx`: Gráfico o barras de desglose multidimensional.
  * Resaltado de líneas en el editor con códigos de color de severidad:
    * 🟡 **Ámbar:** Inconsistencia de nivel (construcciones avanzadas no vistas en clase).
    * 🔴 **Rojo:** Bloque con flujo de datos idéntico a referencia o sintaxis típica de LLM.
  * Panel desplegable: *"Evidencias Técnicas del Dictamen"*.

---

## 3. Especificación Técnica Detallada

### 3.1. Estructura de Datos Enriquecida para XAI (`backend/app/presentation/schemas/analysis.py`)
```python
from pydantic import BaseModel
from typing import List, Optional

class LineaExplicada(BaseModel):
    numero_linea: int
    severidad: str  # "INFO", "MEDIA", "ALTA", "CRITICA"
    categoria: str  # "ESTILO_LLM", "ISOMORFISMO_DFG", "NIVEL_AVANZADO"
    explicacion: str

class ReporteExplicableResponse(BaseModel):
    similitud_semantica: float
    probabilidad_ia: float
    discrepancia_score: float
    dictamen: str
    lineas_sospechosas: List[LineaExplicada]
    resumen_pedagogico: str
    metricas_codigo: dict  # {"complejidad_mccabe": 4, "densidad_comentarios": "35%"}
```

### 3.2. Generador de Indicadores Explicables en Backend (`backend/app/application/services/xai_service.py`)
```python
import re

class XAIService:
    @staticmethod
    def extract_explanations(code: str, dgf_matches: list, is_synthetic: bool) -> list[dict]:
        explanations = []
        lines = code.split("\n")

        # 1. Reglas estilométricas explicables (Comentarios típicos de LLMs)
        llm_comment_patterns = [
            (r"//\s*(Time complexity|Complejidad temporal):", "Comentario formal de análisis asintótico típico de modelos LLM"),
            (r"//\s*(Helper function|Función auxiliar para):", "Comentario explicativo redundante característico de código generado"),
            (r"#include\s*<algorithm>", "Inclusión de biblioteca de algoritmos estándar en ejercicio elemental de punteros en C")
        ]

        for idx, line in enumerate(lines, start=1):
            for pattern, reason in llm_comment_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    explanations.append({
                        "numero_linea": idx,
                        "severidad": "MEDIA",
                        "categoria": "ESTILO_LLM",
                        "explicacion": reason
                    })

        # 2. Atribución de nodos DFG (Flujo de variables idéntico)
        for match in dgf_matches:
            explanations.append({
                "numero_linea": match["line"],
                "severidad": "ALTA",
                "categoria": "ISOMORFISMO_DFG",
                "explicacion": f"El flujo de la variable '{match['var_name']}' es idéntico a la solución canónica a pesar del renombramiento."
            })

        return explanations
```

### 3.3. Componente de UI: Desglose y Resaltado (`frontend/src/components/xai/EvidenceDrawer.tsx`)
```tsx
import { AlertTriangle, Cpu, FileCode2, Sparkles } from "lucide-react";
import { IndicadorItem } from "../../pages/SimilarityReportModal";

interface EvidenceDrawerProps {
  semanticScore: number;
  aiScore: number;
  indicadores: IndicadorItem[];
  onLineClick?: (line: number) => void;
}

export function EvidenceDrawer({ semanticScore, aiScore, indicadores, onLineClick }: EvidenceDrawerProps) {
  return (
    <div className="space-y-6 bg-surface p-6 rounded-2xl border border-line-subtle shadow-xl">
      <h3 className="text-lg font-bold text-content-primary flex items-center gap-2">
        <Sparkles className="text-cyan-400" size={20} />
        Desglose de Evidencias (XAI)
      </h3>

      {/* Tarjetas de los Pilares de Análisis */}
      <div className="grid grid-cols-2 gap-4">
        <div className="p-4 rounded-xl bg-surface-elevated border border-line-subtle">
          <div className="flex items-center gap-2 text-xs font-mono text-content-muted mb-1">
            <Cpu size={14} className="text-purple-400" />
            ANÁLISIS SEMÁNTICO (DFG)
          </div>
          <div className="text-2xl font-black text-content-primary">{semanticScore}%</div>
          <p className="text-xs text-content-secondary mt-1">
            {semanticScore > 75 
              ? "Estructura lógica y flujo de datos prácticamente idéntico al algoritmo de referencia." 
              : "Lógica algorítmica con variantes estructurales independientes."}
          </p>
        </div>

        <div className="p-4 rounded-xl bg-surface-elevated border border-line-subtle">
          <div className="flex items-center gap-2 text-xs font-mono text-content-muted mb-1">
            <FileCode2 size={14} className="text-emerald-400" />
            HUELLA ESTILOMÉTRICA
          </div>
          <div className="text-2xl font-black text-content-primary">{aiScore}%</div>
          <p className="text-xs text-content-secondary mt-1">
            {aiScore > 70 
              ? "Perfección sintáctica, indentación y densidad de comentarios coherentes con generación por LLM." 
              : "Patrones de escritura, espaciado y nombres acordes a un programador novel."}
          </p>
        </div>
      </div>

      {/* Lista de Observaciones y Líneas Específicas */}
      <div className="space-y-3">
        <span className="text-xs font-bold uppercase tracking-wider text-content-muted">
          Puntos de Interés Detectados
        </span>
        {indicadores.map((ind, idx) => (
          <div 
            key={idx}
            className="flex items-start gap-3 p-3 rounded-xl bg-surface-elevated border border-line-subtle hover:border-cyan-500/40 transition-colors cursor-pointer"
          >
            <AlertTriangle size={18} className="text-amber-400 shrink-0 mt-0.5" />
            <div className="text-sm">
              <span className="font-semibold text-content-primary block">
                {ind.tipo_alerta}
              </span>
              <span className="text-xs text-content-secondary">
                {ind.descripcion}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
```

---

## 4. Riesgos y Anti-Patrones a Evitar
* ❌ **Falsas certezas:** Usar expresiones categóricas como *"Este código fue 100% hecho por ChatGPT"*. En sistemas de soporte a la decisión, el lenguaje debe ser **técnico, probabilístico y descriptivo**: *"Se detectaron patrones estructurales con alta correlación a soluciones generadas por modelos de lenguaje"*.
* ⚠️ **Sobrecarga de información (Cognitive Overload):** Mostrar 50 líneas resaltadas confunde al profesor. La UI debe agrupar los hallazgos en máximo **3 o 4 evidencias principales** con opción de expandir detalles.

---

## 5. Criterios de Aceptación y Pruebas
1. El modal de reporte de similitud presenta el desglose justificado de cada métrica.
2. Cada alerta mostrada en la lista tiene una causa clara explicada en lenguaje pedagógico comprensible.
3. El profesor puede hacer clic en una observación y el editor de código se desplaza hacia la línea involucrada.
