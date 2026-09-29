# Guía de Implementación 10: Interpretabilidad de Modelos en la UI (Explainable AI / XAI)

## 1. Fundamentos & Filosofía de Arquitectura
En la evaluación de integridad académica, **un porcentaje abstracto carece de validez pedagógica y jurídica**.

Si un profesor acusa a un estudiante diciéndole: *"Graphito dice que tu código tiene 89% de probabilidad de ser generado por IA"*, el estudiante exigirá evidencia concreta.

La **Inteligencia Artificial Explicable (XAI)** en Graphito debe responder a tres preguntas fundamentales en la UI:
1. **¿Qué partes del código causaron la alerta?** (Resaltado de líneas atípicas y patrones sintéticos).
2. **¿Por qué la lógica se considera idéntica a la referencia?** (Trazabilidad del Grafo de Flujo de Datos / DFG).
3. **¿Cuál es el desglose multidimensional?** (*Semántica*, *Estilometría* y *Nivel Académico*).

---

## 2. Impacto en el Sistema
* **Base de Datos (PostgreSQL):**
  * Ampliar tabla `indicadores_integridad`: `numero_linea` (Integer, nullable) y `categoria` (VARCHAR(50)).
* **Backend (Inferencia & Servicios):**
  * Generación de explicaciones contextualizadas en `IndicadorIntegridad`.
* **Frontend (React + Tailwind):**
  * Componente `EvidenceDrawer.tsx`: Desglose multidimensional y lista de puntos de interés.

---

## 3. Especificación Técnica Detallada

### 3.1. Sentencia DDL en PostgreSQL
```sql
ALTER TABLE indicadores_integridad ADD COLUMN IF NOT EXISTS numero_linea INTEGER;
ALTER TABLE indicadores_integridad ADD COLUMN IF NOT EXISTS categoria VARCHAR(50) DEFAULT 'GENERAL';
```

### 3.2. Modelo Relacional (`backend/app/infrastructure/database/models.py`)
```python
class IndicadorIntegridad(Base):
    __tablename__ = "indicadores_integridad"

    id = Column(Integer, primary_key=True, index=True)
    reporte_id = Column(Integer, ForeignKey("reportes_analisis.id", ondelete="CASCADE"), nullable=False)
    tipo_alerta = Column(String(100), nullable=False)
    descripcion = Column(Text, nullable=False)
    severidad = Column(String(50), default="MEDIA", nullable=False)
    numero_linea = Column(Integer, nullable=True)
    categoria = Column(String(50), default="GENERAL", nullable=True)

    reporte = relationship("ReporteAnalisis", back_populates="indicadores")
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

      <div className="grid grid-cols-2 gap-4">
        <div className="p-4 rounded-xl bg-surface-elevated border border-line-subtle">
          <div className="flex items-center gap-2 text-xs font-mono text-content-muted mb-1">
            <Cpu size={14} className="text-purple-400" />
            ANÁLISIS SEMÁNTICO (DFG)
          </div>
          <div className="text-2xl font-black text-content-primary">{semanticScore}%</div>
          <p className="text-xs text-content-secondary mt-1">
            {semanticScore > 75 
              ? "Estructura lógica y flujo de datos muy similar al algoritmo de referencia." 
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
              ? "Perfección sintáctica y densidad de comentarios coherentes con generación por LLM." 
              : "Patrones de escritura acordes a un programador novel."}
          </p>
        </div>
      </div>

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
              <span className="font-semibold text-content-primary block">{ind.tipo_alerta}</span>
              <span className="text-xs text-content-secondary">{ind.descripcion}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
```

---

## 4. Criterios de Aceptación y Pruebas
1. El modal de reporte de similitud presenta el desglose justificado de cada métrica.
2. Cada alerta mostrada en la lista tiene una causa clara explicada en lenguaje pedagógico.
3. El profesor puede hacer clic en una observación y el editor se desplaza hacia la línea involucrada.
