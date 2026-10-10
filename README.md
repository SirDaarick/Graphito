<div align="center">
  <h1 align="center">🔍 Graphito</h1>
  <h3>Sistema de Apoyo a la Decisión Docente para Integridad Académica en C/C++</h3>
  <p>Evaluación bimodal de código mediante Grafos de Flujo de Datos (DFG) y Estilometría con Deep Learning</p>
</div>

<br/>

**Graphito** es una plataforma pericial basada en el principio ético **Human-in-the-Loop (HITL)**, diseñada para asistir a los profesores en la evaluación de la autoría e integridad de soluciones de software en lenguajes C y C++. 

A diferencia de los verificadores tradicionales basados únicamente en cadenas de texto o árboles sintácticos rígidos, Graphito implementa una **arquitectura de análisis bimodal asimétrica** que examina simultáneamente la lógica algorítmica profunda y la huella estilométrica generativa.

---

## 🚀 Arquitectura de Análisis Bimodal

```mermaid
flowchart LR
    A["Código Evaluado (C/C++)"] --> B["Normalizador Léxico & Tree-sitter"]
    B --> C["Canal A: Semántica Lógica"]
    B --> D["Canal B: Estilometría IA"]
    
    C --> E["Grafo de Flujo de Datos (DFG) + GraphCodeBERT"]
    D --> F["Red Neuronal Convolucional (CharCNN)"]
    
    E --> G["Búsqueda Vectorial (ChromaDB)"]
    G --> H["Fusión Multimodal Asimétrica"]
    F --> H
    
    H --> I["Dashboard Minimalista HITL & Diff Synthwave '84"]
    I --> J["Decisión Docente: Conforme / Duda"]
```

1. 🧠 **Canal A (Semántica Algorítmica):**
   - Extrae el Grafo de Flujo de Datos (**DFG**) con *Tree-sitter*, capturando el flujo de valores entre variables a través de ciclos y condicionales.
   - Aplica **GraphCodeBERT** optimizado con adaptadores **LoRA** (`adaptador-lora-20k`) para garantizar invarianza ante renombramiento de variables y reordenamiento de bloques.
2. ✍️ **Canal B (Estilometría y Detección de Sintaxis de LLMs):**
   - Implementa una arquitectura **CharCNN** (Convolutional Neural Network a nivel de caracteres) que analiza la cadencia sintáctica, regularidad léxica y patrones estilométricos característicos de modelos generativos (como ChatGPT, Claude o Copilot).
3. ⚖️ **Fusión Multimodal y Penalización por Discrepancia:**
   - Si un código presenta una similitud semántica alta con una solución canónica pero una probabilidad de estilo de IA significativa, el sistema calcula un **Índice de Discrepancia Asimétrica** que alerta al docente sobre una posible reelaboración sintética.

---

## ✨ Características Principales

- 💻 **Visualizador Diff Side-by-Side con Tema Synthwave '84:** Cotejo en pantalla completa (expandible al 94%-98% del viewport) del código del alumno contra la solución de referencia o soluciones previas con telemetría Hero HUD en tiempo real.
- 💬 **Anotaciones Pedagógicas en Línea:** Posibilidad de registrar observaciones vinculadas a líneas concretas o notas generales, persistidas en base de datos.
- 📊 **Reporte Técnico de Integridad Académica:** Vista pericial con gráfico circular de similitud total, desglose estilométrico y semántico, e interpretación diagnóstica orientada a la cátedra.
- 🏷️ **Triaje Docente Rápido:** Calificación ágil de entregas con atajos de teclado (`A` para *Conforme*, `R` para *Citar a Aclaración / Duda*) y reflejo reactivo inmediato en la lista de tareas.
- 🖨️ **Dictamen Pericial Oficial en PDF:** Exportación institucional generada por el backend (ReportLab) con métricas bimodales, código fuente numerado y anotaciones del docente.
- 🌙 **Sistema de Diseño Ergonómico:** Scrollbars oscuros personalizados, navegación ágil con atajos (`←` / `→`) y diseño adaptable.

---

## 🛠️ Stack Tecnológico

| Capa | Tecnologías |
| :--- | :--- |
| **Frontend** | React 18, TypeScript, Vite, Tailwind CSS, GSAP, Lucide Icons |
| **Backend API** | FastAPI, Python 3.11+, SQLAlchemy 2.0 (Asíncrono), Pydantic v2 |
| **Inteligencia Artificial** | PyTorch, HuggingFace Transformers (GraphCodeBERT), CharCNN, Tree-sitter |
| **Persistencia** | PostgreSQL (Metadatos relacionales), ChromaDB (Embeddings vectoriales) |
| **Documentación & Reportes** | LaTeX (IEEEtran), ReportLab (PDF Engine) |

---

## 📂 Estructura General del Repositorio

```plaintext
graphito/
├── frontend/               # Aplicación cliente web (React + Vite + Tailwind)
│   ├── src/components/     # SideBySideDiffViewer, SynthwaveHighlighter, ReferenceCard
│   ├── src/pages/          # Biblioteca, SimilarityReportModal
│   └── README.md           # Guía de arquitectura del frontend
├── backend/                # Servicio REST y motor analítico (FastAPI + Clean Architecture)
│   ├── app/domain/         # Entidades puras y puertos (InferencePort, VectorStorePort)
│   ├── app/application/    # Orquestador pericial S1-S7 y generación de PDF
│   ├── app/infrastructure/ # SQLAlchemy, adaptadores de inferencia y ChromaDB
│   ├── app/presentation/   # Endpoints de API v1, esquemas y dependencias
│   └── README.md           # Guía técnica del backend
├── models/                 # Modelos de Machine Learning e inferencia
│   ├── graphcodebert/      # Parser DFG y adaptador LoRA para Canal A
│   ├── char_cnn/           # Modelo convolucional a nivel de caracteres para Canal B
│   └── fusion.py           # Algoritmo de combinación y cálculo de discrepancia
├── data/                   # Pipeline de generación sintética y datasets
├── Documentacion/          # Documentación formal de Trabajo Terminal y guías
│   ├── Documento/          # Proyecto LaTeX compilable (capítulos, figuras, main.tex)
│   ├── guias_implementacion/ # 10 guías maestras de diseño e implementación
│   └── PLAN_METODOLOGIA_KOMOREBI.md
├── tests/                  # Suite de pruebas automatizadas con Pytest
├── docker-compose.yml      # Despliegue orquestado con contenedores
└── README.md               # Este documento
```

---

## ⚙️ Instalación y Puesta en Marcha

### Prerrequisitos
- **Git**
- **Docker** y **Docker Compose** (recomendado para entorno completo)
- O en su defecto: **Python 3.11+**, **Node.js 18+**, **PostgreSQL** y **ChromaDB**.

### Opción A: Despliegue con Docker Compose (Recomendado)

```bash
# 1. Clonar el repositorio
git clone https://github.com/SirDaarick/Graphito.git
cd Graphito

# 2. Configurar variables de entorno
cp .env.example .env  # Ajustar credenciales según sea necesario

# 3. Levantar servicios
docker-compose up --build
```
- Frontend: `http://localhost:5173`
- Backend Swagger Docs: `http://localhost:8000/docs`

### Opción B: Ejecución Local por Módulos

#### Backend:
```bash
cd backend
python -m venv venv
# Activar entorno (Windows: venv\Scripts\activate | Linux/Mac: source venv/bin/activate)
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

#### Frontend:
```bash
cd frontend
npm install
npm run dev
```

---

## 🧪 Pruebas y Validación

```bash
# Ejecutar suite de pruebas de backend e inferencia
pytest tests/ backend/tests/ -v

# Validar compilación de producción del frontend
cd frontend && npm run build
```

Tests that need model weights or cached HuggingFace files are skipped automatically when those are absent (`requires_charcnn_weights`, `requires_graphcodebert` markers). Dev-only extras (scikit-learn) are in `requirements-dev.txt`.

### Decision thresholds

`backend/app/config.py` is the single source: `THRESHOLD_SEM=0.85` (calibrated semantic similarity) and `THRESHOLD_AI=0.20` (AI probability; tuned for the format-invariant CharCNN). Override them with the environment variables of the same name (e.g. in `.env`); a request to `/analysis/run` may still override them per call. The sigmoid `baseline` of `calibrate_semantic_similarity` is a separate calibration parameter, not a decision threshold.

### Offline evaluation (split, golden set, benchmark)

Every reported metric comes from one shared split manifest and a run directory that records its sha256. The manifest is committed as deterministic gzip (`data/splits/split_v1.json.gz`; plain `.json` also loads), and its sha256 is taken over the decompressed JSON bytes, so it does not depend on gzip settings:

```bash
python scripts/build_split.py                                   # -> data/splits/split_v1.json.gz
python data/golden_set/build_corpus.py --split test --force     # -> data/golden_set/corpus
python data/golden_set/build_corpus.py --split val --force      # -> data/golden_set/corpus_val (calibration only)
python data/golden_set/build_manifest.py data/golden_set/corpus --out data/golden_set/manifest.json
python data/golden_set/build_manifest.py data/golden_set/corpus_val --out data/golden_set/manifest_val.json
python scripts/benchmark_suite.py --manifest data/golden_set/manifest.json \
    --calibrate --val-manifest data/golden_set/manifest_val.json   # fit on val, freeze, score test
python scripts/benchmark_suite.py --manifest data/golden_set/manifest.json \
    --mode calibrated-frozen --calibration-dir runs/benchmark/<ts> # reuse frozen calibrations
```

The benchmark modes are `calibrated-fit-in-run`, `calibrated-frozen` and `uncalibrated` (threshold-free metrics only). Thresholds always come from `calibration_<channel>.json` files fitted on val; there are no numeric defaults. See `data/golden_set/README.md`.

- Fused (provisional, production fusion is SDD-4): runs on submissions scored by both channels (the config records `dropped_without_reference`). ROC/PR-AUC rank by the max of the calibrated channel scores; operating points are the confusion of the OR decision (calibrated A >= t_A OR calibrated B >= t_B).
- A run is staged under `runs/.staging/` and moved to `runs/benchmark/<ts>/` only when complete (`summary.json` has `"status": "complete"`); a failure leaves no run behind. Input errors (non-test golden sample, missing source hash, split manifest hash mismatch, missing calibration) print `ERROR: ...` and exit 2.
- Outputs go to `runs/benchmark/<ts>/` (one subdir per channel), which is gitignored. Commit only selected artifacts, explicitly: `git add -f runs/benchmark/<ts>/channel_a/<ts>/metrics.json runs/benchmark/<ts>/channel_a/<ts>/report.md runs/benchmark/<ts>/calibration_channel_a.json`.
- **Legacy results:** the root `benchmark_*results.json` and `benchmark_charcnn_*.json` files predate the split manifest (the old golden set reused 1825/2621 CharCNN train/val samples and used hardcoded thresholds). They are kept for history but are NOT comparable with new runs, which carry the split manifest sha256.

### Migration note: 768-dim semantic vectors (Chroma v2 collection)

Previously the reference index stored a 769-dim vector (768 semantic + `ai_prob`). The stylometry component leaked into the semantic similarity, so the index now stores and queries only the 768-dim semantic embedding, in a new collection `codigos_referencia_v2`. The legacy `codigos_referencia` collection is left untouched.

1. Deploy the new backend. At startup it logs a warning if the legacy collection has data and v2 is empty.
2. Migrate the existing references (exact, no models needed, idempotent):
   `docker compose exec backend python reindex_chroma.py --mode slice`
   If the legacy collection is missing or the model changed, rebuild from Postgres instead: `--mode reembed`.
3. Optional cleanup once verified: add `--drop-legacy`.

Rollback: revert the commit and delete `codigos_referencia_v2`; the legacy collection is still intact.

---

## 📖 Documentación Técnica y Auditoría de Modelos

- 📄 **[Auditoría Técnica y Reporte de Mejora de Modelos ML (Fase 1)](Documentacion/REPORTE_MEJORA_MODELOS_ML.md)**: Diagnóstico empírico de patologías (train/serve skew, desconexión LoRA, anisotropía), remediaciones de inferencia, formulación matemática de calibración sigmoidal ($x_0 = 0.85, k = 24.0$) y validación experimental en casos reales de ESCOM IPN.
- 📚 **[Guías de Implementación Arquitectónica](Documentacion/guias_implementacion/README.md)**: Especificaciones técnicas detalladas para los módulos y flujos del sistema.

---

## 👥 Autores y Dirección

- **Erick Daniel García Rodríguez**
- **Claudia Emilia Sánchez García**

**Directores de Trabajo Terminal:**
- **M. en C. Manuel Portillo Cedillo**
- **M. en C. Maribel Aragón García**

---

<p align="center">
  <i>Trabajo Terminal desarrollado en la <b>Escuela Superior de Cómputo (ESCOM)</b> del <b>Instituto Politécnico Nacional (IPN)</b>.</i>
</p>