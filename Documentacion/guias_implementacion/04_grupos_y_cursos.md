# Guía de Implementación 04: Agrupación por Grupos / Cursos Académicos

## 1. Fundamentos & Filosofía de Arquitectura
En el diseño de software para educación, uno de los errores más comunes es acoplar la **especificación de una tarea (Problema)** a un **contexto temporal específico (Grupo/Semestre)**.

Un profesor diseña un ejercicio de *"Árboles Binarios en C"* y lo reutiliza durante semestres consecutivos en múltiples grupos (e.g. *Grupo 1CV1* y *Grupo 1CV2*).
* Si modelamos una relación 1:N rígida donde un `Problema` pertenece obligatoriamente a un único `Grupo`, obligamos al docente a duplicar manualmente sus tareas cada semestre.
* La solución arquitectónica limpia y extensible es separar:
  1. **Catálogo de Problemas (Biblioteca del Docente):** Define *qué* se evalúa (enunciado, referencias, lenguaje).
  2. **Entidad Grupo / Curso:** Define *dónde* y *cuándo* se imparte (nombre, periodo escolar, descripción).
  3. **Asignación (Asociación N:M):** Vincula un problema a un grupo específico. Las entregas de los estudiantes (`CodigoFuente`) quedan contextualizadas en esa asignación.

---

## 2. Impacto en el Sistema
* **Base de Datos (PostgreSQL):**
  * Nueva tabla `grupos`: `id`, `docente_id`, `nombre`, `periodo` (e.g. "2026-1"), `descripcion`, `created_at`.
  * Nueva tabla de asociación / asignación `grupo_problemas`: `id`, `grupo_id`, `problema_id`, `fecha_limite`, `activo`.
  * Relación en `codigos_fuente`: Agregar `grupo_id` (opcional/nullable para mantener compatibilidad con entregas libres no agrupadas).
* **Backend (FastAPI):**
  * CRUD completo en `app/presentation/api/v1/endpoints/grupos.py`.
  * Filtro por grupo en la consulta de entregas y reportes.
* **Frontend (React):**
  * Barra lateral o selector superior de grupo activo ("Todos los grupos", "Estructuras de Datos - 2CM1").
  * Modal para crear nuevo grupo y asignar problemas existentes.

---

## 3. Especificación Técnica Detallada

### 3.1. Modelo Relacional (`backend/app/infrastructure/database/models.py`)
```python
class Grupo(Base):
    __tablename__ = "grupos"

    id = Column(Integer, primary_key=True, index=True)
    docente_id = Column(Integer, ForeignKey("docentes.id", ondelete="CASCADE"), nullable=False)
    nombre = Column(String(150), nullable=False)       # Ej: "Programación Avanzada"
    codigo_grupo = Column(String(50), nullable=False) # Ej: "3CM2"
    periodo = Column(String(50), nullable=False)      # Ej: "2026-B"
    descripcion = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    docente = relationship("Docente", backref="grupos")
    asignaciones = relationship("GrupoProblema", back_populates="grupo", cascade="all, delete-orphan")


class GrupoProblema(Base):
    __tablename__ = "grupo_problemas"

    id = Column(Integer, primary_key=True, index=True)
    grupo_id = Column(Integer, ForeignKey("grupos.id", ondelete="CASCADE"), nullable=False)
    problema_id = Column(Integer, ForeignKey("problemas.id", ondelete="CASCADE"), nullable=False)
    fecha_limite = Column(DateTime(timezone=True), nullable=True)
    activo = Column(Boolean, default=True)

    grupo = relationship("Grupo", back_populates="asignaciones")
    problema = relationship("Problema")
```

### 3.2. Endpoints Clave (`backend/app/presentation/api/v1/endpoints/grupos.py`)
```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.presentation.api.v1.deps import get_db, get_current_user

router = APIRouter(prefix="/grupos", tags=["Grupos"])

@router.post("/", response_model=GrupoResponse)
def crear_grupo(
    payload: GrupoCreateSchema,
    db: Session = Depends(get_db),
    current_user: Docente = Depends(get_current_user)
):
    nuevo_grupo = Grupo(
        docente_id=current_user.id,
        nombre=payload.nombre,
        codigo_grupo=payload.codigo_grupo,
        periodo=payload.periodo,
        descripcion=payload.descripcion
    )
    db.add(nuevo_grupo)
    db.commit()
    db.refresh(nuevo_grupo)
    return nuevo_grupo

@router.post("/{grupo_id}/asignar-problema")
def asignar_problema(
    grupo_id: int,
    payload: AsignarProblemaSchema,
    db: Session = Depends(get_db),
    current_user: Docente = Depends(get_current_user)
):
    # Validar propiedad del grupo y del problema
    # Crear vínculo en GrupoProblema
    ...
```

### 3.3. Integración en UI (`frontend/src/pages/Biblioteca.tsx`)
* Se añade un componente `GroupFilterDropdown.tsx`:
  * Permite al profesor conmutar la vista entre:
    * `[Vista Global - Todas las tareas]`
    * `[Estructuras de Datos - Grupo 2CM1 (18 entregas)]`
    * `[Algoritmia Básica - Grupo 1CM5 (32 entregas)]`
* Al seleccionar un grupo, las estadísticas y la lista de comparaciones se filtran de forma reactiva sin requerir recargar la página.

---

## 4. Riesgos y Anti-Patrones a Evitar
* ❌ **Eliminación en cascada destructiva:** Si un docente borra un `Grupo`, **NO se deben borrar los `Problemas` de su biblioteca**, únicamente las asociaciones en `grupo_problemas` y los metadatos de ese curso.
* ⚠️ **Compatibilidad Retroactiva:** Existen entregas creadas antes de la existencia de grupos. `grupo_id` en las entregas debe ser nullable para que el historial preexistente no se corrompa ni desaparezca.

---

## 5. Criterios de Aceptación y Pruebas
1. Un docente puede crear múltiples grupos con nombre y periodo escolar.
2. Un mismo problema de la biblioteca puede asignarse a más de un grupo sin duplicar el código de referencia en la base de datos.
3. El filtrado por grupo en la UI segrega correctamente las entregas de los estudiantes de dicho salón.
