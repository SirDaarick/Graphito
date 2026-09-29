# Guía de Implementación 04: Agrupación por Grupos / Cursos Académicos

## 1. Fundamentos & Filosofía de Arquitectura
En el diseño de software para educación, un profesor no debe acoplar rígidamente una tarea a un curso:
* Un profesor diseña un ejercicio de *"Árboles Binarios en C"* y lo reutiliza durante semestres consecutivos en múltiples grupos.
* La solución arquitectónica limpia y extensible es separar:
  1. **Catálogo de Problemas (Biblioteca del Docente):** Define *qué* se evalúa (enunciado, referencias, lenguaje).
  2. **Entidad Grupo / Curso:** Define *dónde* y *cuándo* se imparte (nombre, periodo escolar, descripción).
  3. **Asignación (Asociación N:M):** Vincula un problema a un grupo específico.

---

## 2. Impacto en el Sistema
* **Base de Datos (PostgreSQL):**
  * Nueva tabla `grupos`.
  * Nueva tabla de asociación / asignación `grupo_problemas`.
  * Relación en `codigos_fuente`: Agregar `grupo_id` (opcional/nullable).
* **Backend (FastAPI):**
  * CRUD completo en `app/presentation/api/v1/endpoints/grupos.py`.
  * Filtro por grupo en la consulta de entregas y reportes.
* **Frontend (React):**
  * Barra lateral o selector superior de grupo activo.

---

## 3. Especificación Técnica Detallada

### 3.1. Sentencias DDL en PostgreSQL
```sql
CREATE TABLE IF NOT EXISTS grupos (
    id SERIAL PRIMARY KEY,
    docente_id INTEGER NOT NULL REFERENCES docentes(id) ON DELETE CASCADE,
    nombre VARCHAR(150) NOT NULL,
    codigo_grupo VARCHAR(50) NOT NULL,
    periodo VARCHAR(50) NOT NULL,
    descripcion TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_grupos_docente_id ON grupos(docente_id);

CREATE TABLE IF NOT EXISTS grupo_problemas (
    id SERIAL PRIMARY KEY,
    grupo_id INTEGER NOT NULL REFERENCES grupos(id) ON DELETE CASCADE,
    problema_id INTEGER NOT NULL REFERENCES problemas(id) ON DELETE CASCADE,
    fecha_limite TIMESTAMP WITH TIME ZONE,
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_grupo_problema UNIQUE (grupo_id, problema_id)
);
CREATE INDEX IF NOT EXISTS ix_grupo_problemas_grupo_id ON grupo_problemas(grupo_id);
CREATE INDEX IF NOT EXISTS ix_grupo_problemas_problema_id ON grupo_problemas(problema_id);

ALTER TABLE codigos_fuente ADD COLUMN IF NOT EXISTS grupo_id INTEGER REFERENCES grupos(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS ix_codigos_fuente_grupo_id ON codigos_fuente(grupo_id);
```

### 3.2. Modelo Relacional (`backend/app/infrastructure/database/models.py`)
```python
class Grupo(Base):
    __tablename__ = "grupos"

    id = Column(Integer, primary_key=True, index=True)
    docente_id = Column(Integer, ForeignKey("docentes.id", ondelete="CASCADE"), nullable=False, index=True)
    nombre = Column(String(150), nullable=False)
    codigo_grupo = Column(String(50), nullable=False)
    periodo = Column(String(50), nullable=False)
    descripcion = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    docente = relationship("Docente", back_populates="grupos")
    asignaciones = relationship("GrupoProblema", back_populates="grupo", cascade="all, delete-orphan")
    codigos = relationship("CodigoFuente", back_populates="grupo")


class GrupoProblema(Base):
    __tablename__ = "grupo_problemas"
    __table_args__ = (UniqueConstraint("grupo_id", "problema_id", name="uq_grupo_problema"),)

    id = Column(Integer, primary_key=True, index=True)
    grupo_id = Column(Integer, ForeignKey("grupos.id", ondelete="CASCADE"), nullable=False, index=True)
    problema_id = Column(Integer, ForeignKey("problemas.id", ondelete="CASCADE"), nullable=False, index=True)
    fecha_limite = Column(DateTime(timezone=True), nullable=True)
    activo = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    grupo = relationship("Grupo", back_populates="asignaciones")
    problema = relationship("Problema", back_populates="asignaciones")
```

---

## 4. Riesgos y Anti-Patrones a Evitar
* ❌ **Eliminación en cascada destructiva:** Si un docente borra un `Grupo`, **NO se deben borrar los `Problemas` de su biblioteca**, únicamente las asociaciones en `grupo_problemas`.
* ⚠️ **Compatibilidad Retroactiva:** `grupo_id` en las entregas debe ser nullable para que el historial preexistente no se corrompa.

---

## 5. Criterios de Aceptación y Pruebas
1. Un docente puede crear múltiples grupos con nombre y periodo escolar.
2. Un mismo problema de la biblioteca puede asignarse a más de un grupo sin duplicar el código de referencia.
3. El filtrado por grupo en la UI segrega correctamente las entregas de los estudiantes de dicho salón.
