<div align="center">
  <h1 align="center">🔍 Graphito</h1>
  <h3>Sistema de Comparación de Código en C/C++ mediante Similitud Semántica</h3>
</div>

<br/>

**Graphito** es un Sistema de Apoyo a la Decisión Docente (DSS) diseñado para automatizar la evaluación de integridad académica en cursos introductorios de programación. A diferencia de las herramientas tradicionales basadas en texto, Graphito utiliza un **enfoque bimodal** que analiza tanto la lógica funcional como la "huella digital" del autor para detectar código generado por Inteligencia Artificial.

---

## 🚀 Innovación: Análisis Bimodal

El sistema opera a través de dos canales paralelos para garantizar una evaluación integral:

- 🧠 **Canal A (Semántica):** Utiliza el modelo `GraphCodeBERT` e integra Grafos de Flujo de Datos (DFG) para capturar la lógica algorítmica profunda, ignorando cambios superficiales en la sintaxis.
- ✍️ **Canal B (Estilometría):** Implementa una red `CharCNN` (Convolutional Neural Network a nivel de caracteres) para identificar patrones de escritura y detectar la "perfección sintética" propia de los modelos de lenguaje (LLMs).

---

## ✨ Características Principales

- 🧹 **Normalización Inteligente:** Eliminación de ruido y preservación de estructuras de estilo según el canal de análisis.
- 🤖 **Referencias Sintéticas:** Generación automática de múltiples versiones funcionalmente equivalentes mediante modelos LLM externos para robustecer la comparación.
- ⚖️ **Métrica de Integridad:** Uso de la Similitud del Coseno asimétrica para penalizar discrepancias entre la lógica esperada y el estilo detectado.
- 📊 **Reportes Visuales:** Visualización interactiva y clara del índice de similitud semántica y probabilidad de autoría.

---

## 🛠️ Stack Tecnológico

### Frontend
- **React** (con Vite) + **Tailwind CSS**

### Backend & Inteligencia Artificial
- **FastAPI** (Python)
- **PyTorch** y **LangGraph** (Orquestación de agentes de decisión)

### Persistencia Híbrida
- **PostgreSQL:** Gestión de metadatos relacionales.
- **ChromaDB:** Base de datos vectorial para el almacenamiento y búsqueda de embeddings de alta dimensionalidad.

---

## 📊 Estado Actual del Proyecto

| Componente | Módulo | Estado | Descripción |
|------------|--------|--------|-------------|
| **Canal A (Semántica)** | `models/graphcodebert/` | ✅ Completado | Parser AST + DFG con Tree-sitter para C/C++, inferencia graph-aware y fine-tuning contrastivo con LoRA (`adaptador-lora-20k`). |
| **Canal B (Estilometría)** | `models/char_cnn/` | ✅ Completado | Arquitectura CharCNN a nivel de caracteres, pipeline de preprocesamiento, tokenización e inferencia estilométrica. |
| **Fusión Multimodal** | `models/fusion.py` | ✅ Completado | Módulo de combinación de similitud semántica y estilométrica con ponderación configurable. |
| **Pipeline de Datos** | `data/` | ✅ Completado | Generación de referencias sintéticas con soporte para DeepSeek, Google Gemini y Ollama, normalización y extracción. |
| **Pruebas Automatizadas** | `tests/`, `backend/tests/` | ✅ 40/40 Pasadas | 38 pruebas del parser DFG + 2 pruebas de integración E2E del backend. |
| **Documentación & Specs** | `sdd/`, `Documentacion/` | ✅ Actualizado | Especificaciones de diseño, tareas estructuradas (SDD) y documentación técnica de Trabajo Terminal. |
| **Backend API** | `backend/` | ✅ Completado | API REST con FastAPI, Clean Architecture, persistencia híbrida (PostgreSQL + ChromaDB), desacoplamiento con patrón Strategy y orquestador S1-S7. |
| **Frontend** | `frontend/` | 🚧 En Desarrollo | Interfaz de usuario interactiva en React + Vite + Tailwind CSS. |

---

## 📂 Estructura del Proyecto

```plaintext
graphito/
├── frontend/               # Interfaz de usuario (React + Vite + Tailwind)
├── backend/                # API REST y orquestación de agentes (FastAPI + LangGraph)
├── models/                 # Módulos de IA e inferencia
│   ├── graphcodebert/      # Canal A: GraphCodeBERT + DFG Parser + Adaptador LoRA
│   ├── char_cnn/           # Canal B: CharCNN para detección estilométrica
│   └── fusion.py           # Fusión multimodal (Semántica + Estilometría)
├── data/                   # Pipeline de generación sintética y datasets
├── sdd/                    # Especificaciones y roadmap (Spec-Driven Development)
├── tests/                  # Suite de pruebas automatizadas (Pytest)
└── Documentacion/          # Documentación técnica, diagramas y Trabajo Terminal
```

---

## ⚙️ Instalación y Configuración

### Prerrequisitos
- **Docker** y **Docker Compose** instalados en tu sistema.
- Claves de API de modelos LLM externos y credenciales correspondientes.

### Paso a paso

1. **Clonar el repositorio:**
   ```bash
   git clone https://github.com/tu-usuario/graphito.git
   cd graphito
   ```

2. **Configurar variables de entorno:**
   Establece tus variables en el archivo `.env` en la raíz del proyecto para definir las API Keys y conexiones a las bases de datos.

3. **Ejecutar mediante Docker (Recomendado):**
   ```bash
   docker-compose up --build
   ```
   *Esto levantará tanto el servicio del Frontend (en el puerto 5173) como el laboratorio de datos.*

4. **Ejecutar pruebas unitarias:**
   ```bash
   pytest tests/
   ```

---

## 👥 Autores

- **García Rodríguez Erick Daniel**
- **Sánchez García Claudia Emilia**

**Directores:**
- M. en C. Portillo Cedillo Manuel
- M. en C. Aragón García Maribel

---

<p align="center">
  <i>Este proyecto es un Trabajo Terminal desarrollado en la <b>Escuela Superior de Cómputo (ESCOM)</b> del <b>Instituto Politécnico Nacional (IPN)</b>.</i>
</p>