# Guía de Implementación 07: Botones de Triaje Docente (Aceptar, Rechazar, En Duda)

## 1. Fundamentos & Filosofía de Arquitectura
En sistemas éticos de Inteligencia Artificial para el ámbito educativo, existe un principio inviolable: **Human-in-the-Loop (El Humano Toma la Decisión Final)**.

Actualmente, Graphito genera un `dictamen` algorítmico (`SIN_ALERTAS`, `REVISION_ESTILOMETRICA`, `REVISION_SEMANTICA`). Sin embargo:
* El dictamen del modelo es una **sugerencia probabilística**, no una sentencia pedagógica.
* El sistema carece de un registro formal de la **decisión humana del docente**.
* Agregar el estado de triaje docente (`APROBADO`, `RECHAZADO`, `EN_DUDA`) resuelve dos necesidades críticas:
  1. **Gestión de flujo de trabajo:** Permite al profesor marcar entregas dudosas para citar al alumno a una entrevista o revisión en laboratorio.
  2. **Active Learning (Oro para reentrenamiento):** Cada veredicto del profesor se convierte en una etiqueta de verdad fundamental (*Ground Truth*) para evaluar la precisión real de GraphCodeBERT y CharCNN.

---

## 2. Impacto en el Sistema
* **Base de Datos (PostgreSQL):**
  * Nuevo Enum `DecisionDocenteEnum`:
    * `PENDIENTE` (Aún no revisado)
    * `APROBADO` (El profesor valida la entrega como íntegra)
    * `RECHAZADO` (El profesor confirma plagio o uso fraudulento de IA)
    * `EN_DUDA` (Marcado con bandera para revisión presencial posterior)
  * Campos nuevos en `reportes_analisis`:
    * `decision_docente`: `Enum(DecisionDocenteEnum)`, default `PENDIENTE`.
    * `fecha_decision`: `DateTime`, nullable.
    * `notas_docente`: `Text`, nullable.
* **Backend (FastAPI):**
  * Endpoint `PATCH /api/v1/reports/{reporte_id}/verdict`.
* **Frontend (React):**
  * Barra de acciones fijas en el reporte de similitud:
    * Botón Verde: `[Aceptar Entrega]`
    * Botón Amarillo: `[Marcar en Duda / Revisar Después]`
    * Botón Rojo: `[Rechazar / Sospecha Confirmada]`
  * Badges visuales en `Biblioteca.tsx` que reflejan el estado del triaje.

---

## 3. Especificación Técnica Detallada

### 3.1. Modelo Relacional (`backend/app/infrastructure/database/models.py`)
```python
import enum

class DecisionDocenteEnum(str, enum.Enum):
    PENDIENTE = "PENDIENTE"
    APROBADO = "APROBADO"
    RECHAZADO = "RECHAZADO"
    EN_DUDA = "EN_DUDA"

# En la clase ReporteAnalisis:
class ReporteAnalisis(Base):
    __tablename__ = "reportes_analisis"
    # ... campos existentes ...
    decision_docente = Column(
        Enum(DecisionDocenteEnum),
        nullable=False,
        default=DecisionDocenteEnum.PENDIENTE,
        index=True
    )
    fecha_decision = Column(DateTime(timezone=True), nullable=True)
    notas_docente = Column(Text, nullable=True)
```

### 3.2. Endpoint de Veredicto (`backend/app/presentation/api/v1/endpoints/analysis.py`)
```python
from pydantic import BaseModel

class VerdictUpdateRequest(BaseModel):
    decision: DecisionDocenteEnum
    notas: str | None = None

@router.patch("/{reporte_id}/verdict")
def update_verdict(
    reporte_id: int,
    payload: VerdictUpdateRequest,
    db: Session = Depends(get_db),
    current_user: Docente = Depends(get_current_user)
):
    reporte = db.query(ReporteAnalisis).get(reporte_id)
    if not reporte:
        raise HTTPException(status_code=404, detail="Reporte no encontrado")

    reporte.decision_docente = payload.decision
    reporte.notas_docente = payload.notas
    reporte.fecha_decision = datetime.now(timezone.utc)
    
    db.commit()
    db.refresh(reporte)
    return {
        "status": "success",
        "reporte_id": reporte_id,
        "decision_docente": reporte.decision_docente
    }
```

### 3.3. Componente de Triaje en la UI (`frontend/src/components/review/TriageBar.tsx`)
```tsx
import { CheckCircle2, HelpCircle, XCircle } from "lucide-react";

interface TriageBarProps {
  currentDecision: "PENDIENTE" | "APROBADO" | "RECHAZADO" | "EN_DUDA";
  onSelectVerdict: (verdict: "APROBADO" | "RECHAZADO" | "EN_DUDA") => void;
  isSubmitting?: boolean;
}

export function TriageBar({ currentDecision, onSelectVerdict, isSubmitting }: TriageBarProps) {
  return (
    <div className="flex items-center justify-between p-4 bg-surface-elevated border border-line-subtle rounded-xl shadow-lg">
      <span className="text-sm font-medium text-content-secondary">
        Dictamen Docente:
      </span>
      <div className="flex items-center gap-3">
        <button
          onClick={() => onSelectVerdict("APROBADO")}
          disabled={isSubmitting}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium text-sm transition-all ${
            currentDecision === "APROBADO"
              ? "bg-emerald-600 text-white shadow-emerald-500/20 shadow-lg"
              : "bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20"
          }`}
        >
          <CheckCircle2 size={16} /> Aceptar Código
        </button>

        <button
          onClick={() => onSelectVerdict("EN_DUDA")}
          disabled={isSubmitting}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium text-sm transition-all ${
            currentDecision === "EN_DUDA"
              ? "bg-amber-600 text-white shadow-amber-500/20 shadow-lg"
              : "bg-amber-500/10 text-amber-400 hover:bg-amber-500/20"
          }`}
        >
          <HelpCircle size={16} /> Dejar en Duda
        </button>

        <button
          onClick={() => onSelectVerdict("RECHAZADO")}
          disabled={isSubmitting}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium text-sm transition-all ${
            currentDecision === "RECHAZADO"
              ? "bg-rose-600 text-white shadow-rose-500/20 shadow-lg"
              : "bg-rose-500/10 text-rose-400 hover:bg-rose-500/20"
          }`}
        >
          <XCircle size={16} /> Rechazar / Plagio
        </button>
      </div>
    </div>
  );
}
```

---

## 4. Riesgos y Anti-Patrones a Evitar
* ❌ **Sobrescribir el dictamen de IA:** La decisión docente **no debe sobreescribir el campo `dictamen` original del modelo**. Ambos deben coexistir para auditar discrepancias (e.g. *"El modelo dijo SOSPECHA_IA, pero el profesor validó que era APROBADO porque el alumno usó una técnica avanzada permitida"*).
* ⚠️ **Filtros en Biblioteca:** La vista de la biblioteca debe ofrecer filtros rápidos por veredicto: `[Todos (40)]`, `[Pendientes (28)]`, `[En Duda (3)]`, `[Revisados (9)]`.

---

## 5. Criterios de Aceptación y Pruebas
1. El docente puede asignar veredicto (`APROBADO`, `EN_DUDA`, `RECHAZADO`) desde el modal o vista de entrega.
2. La biblioteca muestra una insignia visual inmediata para entregas "En Duda".
3. El estado persiste en la base de datos y se incluye en la exportación de reportes.
