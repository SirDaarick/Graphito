# Guía de Implementación 05: Carga Masiva (Archivos Múltiples / Carpetas) y Pipeline en Background

## 1. Fundamentos & Filosofía de Arquitectura
En una clase de programación típica, un profesor recibe entre **30 y 60 entregas** por práctica de laboratorio. Obligar al docente a cargar archivos uno a uno es inviable operativamente.

Sin embargo, aquí yace una **trampa de ingeniería crítica**:
* La inferencia bimodal de Graphito (Parser DFG con Tree-sitter + Inferencia con GraphCodeBERT + Convolución por caracteres con CharCNN) toma aproximadamente entre **400 ms y 1 segundo por archivo** en CPU/GPU estándar.
* Si el backend intenta procesar 40 archivos de forma síncrona en una sola petición HTTP, la conexión tardará entre 20 y 45 segundos, provocando un **HTTP 504 Gateway Timeout** en cualquier proxy inverso (Nginx, Caddy o Docker).
* **Solución Arquitectónica:** Patrón **Asynchronous Task Processing (HTTP 202 Accepted + Polling/SSE)**.
  1. El cliente envía el lote de archivos (o carpeta).
  2. El servidor persiste los registros con estado `PENDIENTE` y responde de inmediato con `202 Accepted` y un `lote_id`.
  3. Un worker en segundo plano (`FastAPI BackgroundTasks` o cola de tareas) procesa los análisis secuencialmente.
  4. La UI muestra una barra de progreso en tiempo real consultando el estado del lote.

---

## 2. Impacto en el Sistema
* **Base de Datos (PostgreSQL):**
  * Entidad `LoteAnalisis` en `backend/app/infrastructure/database/models.py`:
    * `id`: UUID (Primary Key).
    * `problema_id`: FK a `problemas.id`.
    * `docente_id`: FK a `docentes.id`.
    * `total_archivos`, `procesados`, `errores`, `estado` (`PENDIENTE`, `PROCESANDO`, `COMPLETADO`, `ERROR`).
  * Columna en `ReporteAnalisis`: `lote_id` (FK a `lotes_analisis.id`, nullable).
* **Frontend (React):**
  * Input de archivos con atributos `multiple` y `webkitdirectory` para soporte de carpetas completas.
  * Extracción automática y heurística del nombre del alumno a partir del nombre del archivo (ej. `2023640112_Perez_Juan_Tarea1.c` -> `Perez Juan`).
  * Modal/Panel de progreso: *"Procesando entrega 12 de 35..."*.
* **Backend (FastAPI):**
  * Endpoint `POST /api/v1/analysis/bulk-upload` (recibe `List[UploadFile]`).
  * Endpoint `GET /api/v1/analysis/batch/{batch_id}/status` (monitorea progreso y métricas parciales).
  * Orquestador en background en `app/application/services/batch_analysis_service.py`.

---

## 3. Especificación Técnica Detallada

### 3.1. Paso a Paso en Base de Datos (SQLAlchemy)
1. **Crear el lote maestro:** Al recibir los archivos, se inserta un registro en `LoteAnalisis` con `estado="PENDIENTE"` y `total_archivos=len(archivos)`.
2. **Asociar cada entrega al lote:** Al insertar cada `ReporteAnalisis`, se asigna `reporte.lote_id = nuevo_lote.id`.
3. **Actualización incremental en background:** A medida que cada análisis concluye, el worker incrementa `lote.procesados += 1` o `lote.errores += 1`.
4. **Cierre de lote:** Al finalizar el último archivo, se actualiza `lote.estado = "COMPLETADO"`.

### 3.2. Extracción Heurística del Alumno en el Frontend (`frontend/src/lib/filename_parser.ts`)
```typescript
export interface ParsedStudentFile {
  file: File;
  authorName: string;
  filename: string;
}

export function parseStudentFilename(file: File): ParsedStudentFile {
  const cleanName = file.name.replace(/\.(c|cpp|cc|h)$/i, "");
  
  // Patrón común: [Boleta/Matricula]_[Apellidos]_[Nombres]
  // Ejemplo: "2024630123_Torres_Reyes_Carlos" -> "Torres Reyes Carlos"
  const tokens = cleanName.split(/[-_]/).filter(t => isNaN(Number(t)));
  
  const authorName = tokens.length > 0 
    ? tokens.join(" ") 
    : cleanName;

  return {
    file,
    authorName: authorName.trim(),
    filename: file.name
  };
}
```

### 3.3. Endpoint de Carga Masiva (`backend/app/presentation/api/v1/endpoints/analysis.py`)
```python
from fastapi import APIRouter, UploadFile, File, Form, BackgroundTasks, Depends, status
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

### 3.4. Procesamiento en Background (`backend/app/application/services/batch_pipeline.py`)
```python
def process_batch_inference_pipeline(batch_id: str, submissions: list, problema_id: int):
    # Obtener nueva sesión de base de datos aislada para el hilo de fondo
    db = SessionLocal()
    try:
        # Cargar referencias del problema una sola vez en memoria
        referencias = db.query(CodigoFuente).filter(
            CodigoFuente.problema_id == problema_id,
            CodigoFuente.tipo == TipoCodigoEnum.REFERENCIA
        ).all()
        
        for entrega_id, reporte_id, content, lenguaje in submissions:
            reporte = db.query(ReporteAnalisis).get(reporte_id)
            reporte.estado = EstadoAnalisisEnum.PROCESANDO
            db.commit()
            
            try:
                # Ejecutar Fusión Bimodal (GraphCodeBERT + CharCNN)
                resultado = run_bimodal_analysis(content, referencias, lenguaje)
                
                reporte.similitud_semantica = resultado.sem_sim
                reporte.probabilidad_ia = resultado.prob_ia
                reporte.dictamen = resultado.dictamen
                reporte.estado = EstadoAnalisisEnum.COMPLETADO
                
                # Crear indicadores de alerta si aplica
                for indicador in resultado.indicadores:
                    db.add(IndicadorIntegridad(
                        reporte_id=reporte.id,
                        tipo_alerta=indicador.tipo,
                        descripcion=indicador.desc,
                        severidad=indicador.severidad
                    ))
            except Exception as e:
                reporte.estado = EstadoAnalisisEnum.ERROR
                reporte.error_mensaje = str(e)
                
            db.commit()
    finally:
        db.close()
```

---

## 4. Riesgos y Anti-Patrones a Evitar
* ❌ **Consumo descontrolado de VRAM:** En GPU, ejecutar múltiples inferencias de `GraphCodeBERT` concurrentes en hilos paralelos saturará la memoria y arrojará `CUDA Out of Memory`. El procesamiento en background de un lote debe ser **secuencial o en mini-batches controlados**.
* ⚠️ **Codificación de caracteres (Encoding):** Los estudiantes en México e Iberoamérica frecuentemente usan acentos y caracteres especiales en comentarios (`ñ`, `á`, `é`). Al leer el archivo en backend se debe utilizar `errors="ignore"` o decodificación robusta con `chardet` para evitar excepciones de decodificación `UnicodeDecodeError`.

---

## 5. Criterios de Aceptación y Pruebas
1. El usuario puede arrastrar una carpeta con 30 archivos `.c` al modal de carga.
2. El modal extrae los nombres preliminares de los alumnos y permite corregirlos antes de subir.
3. El frontend muestra una barra de progreso reactiva sin que la petición se corte por timeout.
4. Cada entrega aparece en la biblioteca con sus métricas calculadas y asociadas al alumno correspondiente.
