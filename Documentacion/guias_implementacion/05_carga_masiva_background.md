# Guía de Implementación 05: Carga Masiva (Archivos Múltiples / Carpetas) y Pipeline en Background

## 1. Fundamentos & Filosofía de Arquitectura
En una clase de programación típica, un profesor recibe entre **30 y 60 entregas** por práctica de laboratorio. Obligar al docente a cargar archivos uno a uno es inviable operativamente.

Sin embargo, aquí yace una **trampa de ingeniería crítica**:
* La inferencia bimodal de Graphito (Parser DFG con Tree-sitter + Inferencia con GraphCodeBERT + Convolución por caracteres con CharCNN) toma aproximadamente entre **400 ms y 1 segundo por archivo** en CPU/GPU estándar.
* Si el backend intenta procesar 40 archivos de forma síncrona en una sola petición HTTP, la conexión tardará entre 20 y 45 segundos, provocando un **HTTP 504 Gateway Timeout**.
* **Solución Arquitectónica:** Patrón **Asynchronous Task Processing (HTTP 202 Accepted + Polling/SSE)** con una entidad `LoteAnalisis`.

---

## 2. Impacto en el Sistema
* **Base de Datos (PostgreSQL):**
  * Entidad `LoteAnalisis`: `id` (UUID), `problema_id`, `docente_id`, `total_archivos`, `procesados`, `errores`, `estado`.
  * Columna en `ReporteAnalisis`: `lote_id` (FK a `lotes_analisis.id`, nullable).
* **Frontend (React):**
  * Input de archivos con atributos `multiple` y `webkitdirectory` para soporte de carpetas completas.
  * Extracción automática y heurística del nombre del alumno a partir del nombre del archivo.
  * Modal/Panel de progreso: *"Procesando entrega 12 de 35..."*.
* **Backend (FastAPI):**
  * Endpoint `POST /api/v1/analysis/batch`.
  * Endpoint `GET /api/v1/analysis/batch/{batch_id}/status`.
  * Orquestador en background en `app/application/services/batch_pipeline.py`.

---

## 3. Especificación Técnica Detallada

### 3.1. Sentencia DDL en PostgreSQL
```sql
CREATE TABLE IF NOT EXISTS lotes_analisis (
    id UUID PRIMARY KEY,
    problema_id INTEGER NOT NULL REFERENCES problemas(id) ON DELETE CASCADE,
    docente_id INTEGER NOT NULL REFERENCES docentes(id) ON DELETE CASCADE,
    total_archivos INTEGER NOT NULL DEFAULT 0,
    procesados INTEGER NOT NULL DEFAULT 0,
    errores INTEGER NOT NULL DEFAULT 0,
    estado VARCHAR(50) NOT NULL DEFAULT 'PENDIENTE',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_lotes_docente_id ON lotes_analisis(docente_id);
CREATE INDEX IF NOT EXISTS ix_lotes_problema_id ON lotes_analisis(problema_id);

ALTER TABLE reportes_analisis ADD COLUMN IF NOT EXISTS lote_id UUID REFERENCES lotes_analisis(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS ix_reportes_lote_id ON reportes_analisis(lote_id);
```

### 3.2. Endpoint de Carga Masiva (`backend/app/presentation/api/v1/endpoints/analysis.py`)
```python
from fastapi import APIRouter, UploadFile, File, BackgroundTasks, Depends, status
import uuid
from app.infrastructure.database.models import LoteAnalisis, CodigoFuente, ReporteAnalisis, EstadoAnalisisEnum, TipoCodigoEnum

router = APIRouter(prefix="/analysis", tags=["Análisis"])

@router.post("/batch", status_code=status.HTTP_202_ACCEPTED)
async def upload_batch_submissions(
    problema_id: int,
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: Docente = Depends(get_current_user)
):
    lote_id = uuid.uuid4()
    
    # 1. Crear el registro del Lote en PostgreSQL
    lote = LoteAnalisis(
        id=lote_id,
        problema_id=problema_id,
        docente_id=current_user.id,
        total_archivos=len(files),
        procesados=0,
        errores=0,
        estado="PROCESANDO"
    )
    db.add(lote)
    db.flush()

    # 2. Leer contenidos y pre-crear registros en estado PENDIENTE
    submissions_data = []
    for file in files:
        if not file.filename.endswith(('.c', '.cpp', '.cc')):
            continue
        content = (await file.read()).decode("utf-8", errors="ignore")
        author = extract_author_from_filename(file.filename)
        
        codigo = CodigoFuente(
            problema_id=problema_id,
            tipo=TipoCodigoEnum.ENTREGA_ALUMNO,
            autor=author,
            contenido=content,
            lenguaje="cpp" if file.filename.endswith(('.cpp', '.cc')) else "c"
        )
        db.add(codigo)
        db.flush()
        
        reporte = ReporteAnalisis(
            entrega_id=codigo.id,
            lote_id=lote.id,
            estado=EstadoAnalisisEnum.PENDIENTE,
            dictamen=DictamenEnum.SIN_ALERTAS
        )
        db.add(reporte)
        submissions_data.append((codigo.id, reporte.id, content, codigo.lenguaje))
        
    db.commit()
    
    # 3. Despachar pipeline asíncrono en background
    background_tasks.add_task(
        process_batch_inference_pipeline,
        batch_id=lote_id,
        submissions=submissions_data,
        problema_id=problema_id
    )

    return {
        "batch_id": str(lote_id),
        "total_archivos": len(submissions_data),
        "mensaje": "Lote recibido y encolado para análisis bimodal."
    }
```

---

## 4. Riesgos y Anti-Patrones a Evitar
* ❌ **Consumo descontrolado de VRAM:** En GPU, ejecutar múltiples inferencias de `GraphCodeBERT` concurrentes en hilos paralelos saturará la memoria (`CUDA Out of Memory`). El procesamiento de un lote debe ser secuencial o en mini-batches controlados.

---

## 5. Criterios de Aceptación y Pruebas
1. El usuario puede arrastrar una carpeta con 30 archivos `.c` al modal de carga.
2. El modal extrae los nombres preliminares de los alumnos y permite corregirlos antes de subir.
3. El frontend muestra una barra de progreso reactiva sin que la petición se corte por timeout.
