# ⚙️ Graphito Backend — Arquitectura y API REST

Servicio de backend de alto rendimiento para **Graphito** (Sistema de Apoyo a la Decisión Docente para Integridad Académica en C/C++), implementado con **FastAPI**, **SQLAlchemy Asíncrono**, **PostgreSQL**, **ChromaDB**, **PyTorch** y **ReportLab**.

---

## 🏛️ Principios de Arquitectura (Clean Architecture)

El backend sigue estrictamente el patrón de **Arquitectura Limpia (Hexagonal / Clean Architecture)** para garantizar bajo acoplamiento, alta testeabilidad e independencia de frameworks:

```plaintext
app/
├── domain/                  # Núcleo de la aplicación (Reglas de negocio y contratos)
│   ├── entities/            # Entidades y tipos de valor puros (sin dependencias externas)
│   └── ports/               # Interfaces abstractas (InferencePort, VectorStorePort)
├── application/             # Casos de uso y orquestación
│   ├── orchestrator/        # Orquestador del pipeline de análisis y peritaje (S1 - S7)
│   └── services/            # Servicios de aplicación (PDF generation con ReportLab, etc.)
├── infrastructure/          # Adaptadores a tecnologías concretas
│   ├── database/            # Modelos SQLAlchemy, sesiones async y repositorios
│   ├── inference/           # Adaptador de inferencia GraphCodeBERT + CharCNN
│   └── vector_store/        # Adaptador vectorial ChromaDB
└── presentation/            # Capa de entrada (Controladores HTTP, Dependencias y Esquemas)
    ├── api/v1/endpoints/    # Rutas REST (auth, problems, analysis, submissions, comments)
    ├── deps.py              # Inyección de dependencias (Autenticación JWT, Contexto DB)
    └── schemas/             # Contratos Pydantic v2 (Request / Response DTOs)
```

---

## 🚀 Pipeline de Análisis Pericial Bimodal (S1 - S7)

El orquestador de análisis [`AnalysisOrchestrator`](file:///c:/Users/edani/OneDrive/Documents/Proyectos/Graphito/backend/app/application/orchestrator/analysis_orchestrator.py) ejecuta una secuencia coordinada de 7 pasos:

1. **S1 (Extracción & Normalización):** Lee el código fuente y extrae su estructura léxica y sintáctica mediante Tree-sitter.
2. **S2 (Canal A - Semántica DFG):** Construye el Grafo de Flujo de Datos (DFG) y genera embeddings contextuales con GraphCodeBERT.
3. **S3 (Búsqueda Vectorial de Referencias):** Realiza una consulta a ChromaDB buscando soluciones canónicas y soluciones históricas previas.
4. **S4 (Canal B - Estilometría CharCNN):** Evalúa la distribución de caracteres, entropía léxica y patrones sintácticos afines a modelos generativos (LLMs).
5. **S5 (Fusión Multimodal & Discrepancia):** Calcula el índice de similitud semántica y la penalización por discrepancia asimétrica.
6. **S6 (Generación de Señales e Indicadores):** Clasifica banderas de integridad (severidad `BAJA`, `MEDIA`, `ALTA`, `CRITICA`).
7. **S7 (Persistencia Relacional):** Almacena el reporte, indicadores y actualiza el estado en PostgreSQL.

---

## 📡 Endpoints Clave de la API (v1)

| Método | Ruta | Descripción |
| :--- | :--- | :--- |
| `POST` | `/api/v1/analysis/run` | Ejecuta el análisis pericial síncrono o en segundo plano (`async_mode=true`). |
| `GET` | `/api/v1/analysis/reports/{id}` | Recupera el reporte con sus métricas e indicadores forenses. |
| `GET` | `/api/v1/analysis/reports/{id}/code` | Provee los códigos fuente para el visor Side-by-Side Diff (código alumno vs. referencia). |
| `GET` | `/api/v1/analysis/reports/{id}/pdf` | Genera y transmite en streaming el dictamen pericial en PDF (con código numerado y notas). |
| `GET` | `/api/v1/comments/{reporte_id}/comments` | Lista cronológicamente las observaciones pedagógicas del docente. |
| `POST` | `/api/v1/comments/{reporte_id}/comments` | Registra una nueva observación pedagógica general o asociada a una línea específica. |
| `DELETE` | `/api/v1/comments/{reporte_id}/comments/{id}` | Elimina un comentario (con control de acceso por docente autor). |
| `POST` | `/api/v1/auth/login` | Autenticación y emisión de tokens de acceso Bearer JWT. |
| `GET` | `/api/v1/problems` | Catálogo de problemas y ejercicios de programación. |

---

## 🗄️ Persistencia y Migraciones

- **PostgreSQL Asíncrono:** Conexión con `asyncpg` y motor `SQLAlchemy 2.0+`.
- **Esquema de Base de Datos:** Entidades definidas en [`models.py`](file:///c:/Users/edani/OneDrive/Documents/Proyectos/Graphito/backend/app/infrastructure/database/models.py).
- **Scripts DDL Idempotentes:** Las migraciones funcionales de tablas y columnas (`comentarios_revision`, `grupos`, `lotes_analisis`) se encuentran en [`migrations/migration_features.sql`](file:///c:/Users/edani/OneDrive/Documents/Proyectos/Graphito/backend/migrations/migration_features.sql).
- **Aplicador Automatizado:** Script ejecutable [`apply_migrations.py`](file:///c:/Users/edani/OneDrive/Documents/Proyectos/Graphito/backend/apply_migrations.py).

---

## 🧪 Ejecución Local y Pruebas

### Configuración del entorno
```bash
# 1. Crear entorno virtual
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Iniciar servidor FastAPI en modo recarga activa
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Ejecutar Suite de Pruebas
```bash
pytest backend/tests/ -v
```
