# Guía de Implementación 06: Visualizador de Códigos Cara a Cara (Diff Viewer) y Anotaciones

## 1. Fundamentos & Filosofía de Arquitectura
Un Sistema de Apoyo a la Decisión Docente (DSS) no puede ser una **caja negra**. Decirle a un profesor que un código tiene *"88% de similitud semántica y 92% de probabilidad sintética"* sin permitirle confrontar el código del estudiante frente al código canónico de referencia imposibilita la labor docente.

Para lograr una experiencia de revisión profesional:
1. **Comparación Visual Lado a Lado (Side-by-Side Diff):** Enfrentar el código de referencia (izquierda) contra el código del estudiante (derecha) con resaltado sintáctico adecuado para C/C++.
2. **Anotaciones y Comentarios Pedagógicos:** Permitir al profesor insertar comentarios vinculados a líneas específicas o generales para respaldar su evaluación.

---

## 2. Impacto en el Sistema
* **Frontend (React):**
  * Dependencia recomendada: `@monaco-editor/react` (el núcleo de VS Code en el navegador, con soporte nativo de `DiffEditor`, minimapa y cambio de temas) o alternativamente `react-diff-viewer-continued`.
  * Componente `CodeComparisonView.tsx`: Renderiza la vista dividida con sincronización de scroll.
* **Base de Datos & Backend (FastAPI):**
  * Nueva tabla `comentarios_revision` en PostgreSQL.
  * Endpoints en `app/presentation/api/v1/endpoints/comments.py` (`POST`, `GET`, `DELETE`).

---

## 3. Especificación Técnica Detallada

### 3.1. Sentencia DDL en PostgreSQL
```sql
CREATE TABLE IF NOT EXISTS comentarios_revision (
    id SERIAL PRIMARY KEY,
    reporte_id INTEGER NOT NULL REFERENCES reportes_analisis(id) ON DELETE CASCADE,
    docente_id INTEGER NOT NULL REFERENCES docentes(id) ON DELETE CASCADE,
    numero_linea INTEGER,
    contenido TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_comentarios_reporte_id ON comentarios_revision(reporte_id);
CREATE INDEX IF NOT EXISTS ix_comentarios_docente_id ON comentarios_revision(docente_id);
```

### 3.2. Modelo Relacional (`backend/app/infrastructure/database/models.py`)
```python
class ComentarioRevision(Base):
    __tablename__ = "comentarios_revision"

    id = Column(Integer, primary_key=True, index=True)
    reporte_id = Column(Integer, ForeignKey("reportes_analisis.id", ondelete="CASCADE"), nullable=False, index=True)
    docente_id = Column(Integer, ForeignKey("docentes.id", ondelete="CASCADE"), nullable=False, index=True)
    numero_linea = Column(Integer, nullable=True) # Null si es un comentario general de la entrega
    contenido = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    reporte = relationship("ReporteAnalisis", back_populates="comentarios")
    docente = relationship("Docente", back_populates="comentarios")
```

### 3.3. Implementación de la Vista Monaco Diff (`frontend/src/components/code/CodeDiffViewer.tsx`)
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

---

## 4. Riesgos y Anti-Patrones a Evitar
* ❌ **Carga pesada de Monaco Editor:** Monaco Editor es un paquete voluminoso. Debe cargarse de forma perezosa (`React.lazy()`) para no degradar el First Contentful Paint (FCP).

---

## 5. Criterios de Aceptación y Pruebas
1. El docente puede abrir una entrega y ver el código del alumno frente al código de referencia en paralelo.
2. Las líneas con divergencias estructurales se resaltan nítidamente.
3. El profesor puede agregar una observación en una línea específica y esta queda guardada.
