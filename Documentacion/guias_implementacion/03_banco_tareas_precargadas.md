# Guía de Implementación 03: Banco de Tareas Precargadas (Plantillas Canónicas)

## 1. Fundamentos & Filosofía de Arquitectura
El mayor inhibidor de tracción en un producto B2B/Educativo es el **síndrome del lienzo en blanco (Cold Start Problem)**. Cuando un docente ingresa a Graphito por primera vez y ve una biblioteca vacía, la fricción de:
1. Redactar el enunciado del problema,
2. Especificar el lenguaje (C / C++),
3. Diseñar y subir los códigos de referencia canónicos (soluciones óptimas),

provoca el abandono temprano de la plataforma.

Para resolverlo, la arquitectura debe incorporar el patrón **Prototype / Cloner (Adopción de Plantillas)**:
* El sistema mantiene un catálogo de problemas estándar universitarios (Búsqueda Binaria, Palíndromos, Quicksort, Listas Enlazadas).
* Cada plantilla contiene el enunciado y **códigos de referencia pre-analizados con sus embeddings en ChromaDB**.
* La adopción de una plantilla ejecuta una clonación profunda (*Deep Copy*) transaccional hacia el espacio privado del docente.

---

## 2. Impacto en el Sistema
* **Base de Datos (PostgreSQL):**
  * Opción recomendada por simplicidad y consistencia: Agregar a la tabla `problemas`:
    * `es_plantilla`: `Boolean`, default `False`, indexado.
    * `dificultad`: `String(50)`, nullable `True` (`"Principiante"`, `"Intermedio"`, `"Avanzado"`).
    * `docente_id`: Permitir `nullable=True` para plantillas del sistema, o asignar un usuario especial `System/Admin` (ID: 1).
* **Base de Datos Vectorial (ChromaDB):**
  * Los códigos de referencia clonados pueden reutilizar los embeddings existentes o re-indexarse bajo el ID del nuevo problema.
* **Backend (FastAPI):**
  * Endpoints:
    * `GET /api/v1/plantillas`: Listado público/docente de plantillas disponibles.
    * `POST /api/v1/plantillas/{id}/adoptar`: Clona la plantilla y crea un `Problema` propio.
* **Frontend (React):**
  * Pestaña o modal en la `Biblioteca`: "Explorar Banco de Problemas".
  * Previsualización del enunciado y botón "Copiar a mi Biblioteca".

---

## 3. Especificación Técnica Detallada

### 3.1. Modelo de Datos (`backend/app/infrastructure/database/models.py`)
```python
class Problema(Base):
    __tablename__ = "problemas"

    id = Column(Integer, primary_key=True, index=True)
    docente_id = Column(Integer, ForeignKey("docentes.id", ondelete="CASCADE"), nullable=True) # Nullable para plantillas maestras
    titulo = Column(String(255), nullable=False)
    enunciado = Column(Text, nullable=False)
    lenguaje = Column(String(50), default="c", nullable=False)
    es_plantilla = Column(Boolean, default=False, index=True)
    dificultad = Column(String(50), default="Principiante")
    fecha_creacion = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    docente = relationship("Docente", back_populates="problemas")
    codigos = relationship("CodigoFuente", back_populates="problema", cascade="all, delete-orphan")
```

### 3.2. Lógica de Clonación Profunda Transaccional (`backend/app/application/services/plantilla_service.py`)
```python
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.infrastructure.database.models import Problema, CodigoFuente, TipoCodigoEnum

class PlantillaService:
    @staticmethod
    def adoptar_plantilla(db: Session, plantilla_id: int, docente_id: int) -> Problema:
        # 1. Obtener la plantilla original
        plantilla = db.query(Problema).filter(
            Problema.id == plantilla_id,
            Problema.es_plantilla == True
        ).first()

        if not plantilla:
            raise HTTPException(status_code=404, detail="La plantilla solicitada no existe.")

        # 2. Iniciar transacción de clonación
        try:
            nuevo_problema = Problema(
                docente_id=docente_id,
                titulo=f"{plantilla.titulo} (Copia)",
                enunciado=plantilla.enunciado,
                lenguaje=plantilla.lenguaje,
                es_plantilla=False,
                dificultad=plantilla.dificultad
            )
            db.add(nuevo_problema)
            db.flush() # Obtener el nuevo ID generado

            # 3. Clonar los códigos de referencia asociados
            referencias_originales = db.query(CodigoFuente).filter(
                CodigoFuente.problema_id == plantilla.id,
                CodigoFuente.tipo == TipoCodigoEnum.REFERENCIA
            ).all()

            for ref in referencias_originales:
                nueva_ref = CodigoFuente(
                    problema_id=nuevo_problema.id,
                    tipo=TipoCodigoEnum.REFERENCIA,
                    autor=ref.autor,
                    contenido=ref.contenido,
                    lenguaje=ref.lenguaje
                )
                db.add(nueva_ref)

            db.commit()
            db.refresh(nuevo_problema)
            return nuevo_problema

        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Error al clonar plantilla: {str(e)}")
```

### 3.3. Sembrado de Datos Inicial (Seed Script: `backend/scripts/seed_plantillas.py`)
```python
TEMPLATES = [
    {
        "titulo": "Búsqueda Binaria en Arreglos Ordenados",
        "enunciado": "Implementar una función en C que busque un elemento en un arreglo de enteros previamente ordenado...",
        "lenguaje": "c",
        "dificultad": "Principiante",
        "referencia": """#include <stdio.h>
int busquedaBinaria(int arr[], int l, int r, int x) {
    while (l <= r) {
        int m = l + (r - l) / 2;
        if (arr[m] == x) return m;
        if (arr[m] < x) l = m + 1;
        else r = m - 1;
    }
    return -1;
}"""
    },
    {
        "titulo": "Inversión de Lista Enlazada Simple",
        "enunciado": "Escribir un programa en C++ que construya una lista simplemente enlazada y revierta los punteros in-situ...",
        "lenguaje": "cpp",
        "dificultad": "Intermedio",
        "referencia": """#include <iostream>
struct Nodo { int dato; Nodo* sig; };
Nodo* revertir(Nodo* cabeza) {
    Nodo *prev = nullptr, *act = cabeza, *sig = nullptr;
    while (act != nullptr) {
        sig = act->sig;
        act->sig = prev;
        prev = act;
        act = sig;
    }
    return prev;
}"""
    }
]
```

---

## 4. Riesgos y Anti-Patrones a Evitar
* ❌ **Copias Superficiales (Shallow Copy):** Vincular los mismos registros de `CodigoFuente` al nuevo problema. Si el profesor decide modificar la referencia para ajustarla a su rúbrica, alteraría la plantilla global. **Debe ser Deep Copy siempre.**
* ⚠️ **Desincronización Vectorial:** Al clonar un código de referencia, se debe decidir si se generan nuevos embeddings en ChromaDB para el nuevo `codigo_id` o si el recuperador vectorial soporta búsqueda cruzada. Para mantener Clean Architecture, registrar el embedding del nuevo código garantiza independencia total.

---

## 5. Criterios de Aceptación y Pruebas
1. Un docente recién registrado puede ver la lista de problemas del sistema ordenados por dificultad y lenguaje.
2. Al pulsar "Adoptar", el problema aparece en "Mi Biblioteca" con sus códigos de referencia intactos.
3. El profesor puede editar el enunciado y los códigos de referencia de su copia sin afectar la plantilla del sistema.
