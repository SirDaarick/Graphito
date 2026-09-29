# Guía de Implementación 06: Visualizador de Códigos Cara a Cara (Diff Viewer) y Anotaciones

## 1. Fundamentos & Filosofía de Arquitectura
Un Sistema de Apoyo a la Decisión Docente (DSS) no puede ser una **caja negra**. Decirle a un profesor que un código tiene *"88% de similitud semántica y 92% de probabilidad sintética"* sin permitirle confrontar el código del estudiante frente al código canónico de referencia imposibilita la labor docente.

Para lograr una experiencia de revisión profesional:
1. **Comparación Visual Lado a Lado (Side-by-Side Diff):** Enfrentar el código de referencia (izquierda) contra el código del estudiante (derecha) con resaltado sintáctico adecuado para C/C++.
2. **Anotaciones y Comentarios Pedagógicos:** Permitir al profesor insertar comentarios vinculados a líneas específicas o generales para respaldar su evaluación (e.g. *"Uso idéntico del algoritmo de inversión de punteros generado por LLM"*).

---

## 2. Impacto en el Sistema
* **Frontend (React):**
  * Dependencia recomendada: `@monaco-editor/react` (el núcleo de VS Code en el navegador, con soporte nativo de `DiffEditor`, minimapa y cambio de temas) o alternativamente `react-diff-viewer-continued`.
  * Componente `CodeComparisonView.tsx`: Renderiza la vista dividida con sincronización de scroll.
  * Componente `LineCommentOverlay.tsx` para agregar anotaciones sobre líneas de código.
* **Backend (FastAPI):**
  * Nueva tabla `comentarios_revision` en PostgreSQL.
  * Endpoints en `app/presentation/api/v1/endpoints/comments.py` (`POST`, `GET`, `DELETE`).

---

## 3. Especificación Técnica Detallada

### 3.1. Modelo Relacional para Comentarios (`backend/app/infrastructure/database/models.py`)
```python
class ComentarioRevision(Base):
    __tablename__ = "comentarios_revision"

    id = Column(Integer, primary_key=True, index=True)
    reporte_id = Column(Integer, ForeignKey("reportes_analisis.id", ondelete="CASCADE"), nullable=False)
    docente_id = Column(Integer, ForeignKey("docentes.id", ondelete="CASCADE"), nullable=False)
    numero_linea = Column(Integer, nullable=True) # Null si es un comentario general de la entrega
    contenido = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    reporte = relationship("ReporteAnalisis", backref="comentarios")
    docente = relationship("Docente")
```

### 3.2. Implementación de la Vista Monaco Diff (`frontend/src/components/code/CodeDiffViewer.tsx`)
```tsx
import { DiffEditor } from "@monaco-editor/react";
import { useTheme } from "../../lib/theme";

interface CodeDiffViewerProps {
  referenceCode: string;
  studentCode: string;
  language: "c" | "cpp";
  readOnly?: boolean;
}

export function CodeDiffViewer({
  referenceCode,
  studentCode,
  language,
  readOnly = true
}: CodeDiffViewerProps) {
  const { resolvedTheme } = useTheme();

  return (
    <div className="w-full h-[600px] border border-line-subtle rounded-xl overflow-hidden shadow-2xl bg-surface">
      <div className="flex justify-between items-center px-4 py-2 bg-surface-elevated border-b border-line-subtle text-xs font-mono text-content-secondary">
        <span>Código Canónico / Referencia</span>
        <span>Entrega del Alumno</span>
      </div>
      <DiffEditor
        height="100%"
        language={language}
        original={referenceCode}
        modified={studentCode}
        theme={resolvedTheme === "dark" ? "vs-dark" : "light"}
        options={{
          readOnly,
          renderSideBySide: true,
          minimap: { enabled: false },
          scrollBeyondLastLine: false,
          fontSize: 13,
          lineNumbers: "on",
          folding: true,
          wordWrap: "on"
        }}
      />
    </div>
  );
}
```

### 3.3. Endpoints de Anotaciones (`backend/app/presentation/api/v1/endpoints/comments.py`)
```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.presentation.api.v1.deps import get_db, get_current_user

router = APIRouter(prefix="/reports/{reporte_id}/comments", tags=["Comentarios"])

@router.post("/", response_model=ComentarioResponse)
def agregar_comentario(
    reporte_id: int,
    payload: ComentarioCreateSchema,
    db: Session = Depends(get_db),
    current_user: Docente = Depends(get_current_user)
):
    nuevo_comentario = ComentarioRevision(
        reporte_id=reporte_id,
        docente_id=current_user.id,
        numero_linea=payload.numero_linea,
        contenido=payload.contenido
    )
    db.add(nuevo_comentario)
    db.commit()
    db.refresh(nuevo_comentario)
    return nuevo_comentario
```

---

## 4. Riesgos y Anti-Patrones a Evitar
* ❌ **Carga pesada de Monaco Editor:** Monaco Editor es un paquete voluminoso (~4MB). Debe cargarse de forma perezosa (`React.lazy()` o dynamic import) para no degradar el First Contentful Paint (FCP) de la aplicación inicial.
* ⚠️ **Desalineación por comentarios sintéticos:** Los códigos generados por LLM frecuentemente contienen comentarios verbosos que desalinean el diff visual respecto al código conciso del docente. Se recomienda incluir un interruptor en la UI: *"Ocultar comentarios al comparar"* para ver la estructura pura del código.

---

## 5. Criterios de Aceptación y Pruebas
1. El docente puede abrir una entrega y ver el código del alumno frente al código de referencia en paralelo.
2. Las líneas con divergencias estructurales se resaltan nítidamente.
3. El profesor puede agregar una observación en una línea específica y esta queda guardada y visible para futuras revisiones o descargas de reporte PDF.
