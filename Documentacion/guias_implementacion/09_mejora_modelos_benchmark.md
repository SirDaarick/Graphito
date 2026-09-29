# Guía de Implementación 09: Estrategia de Mejora de Modelos & Benchmark Riguroso

## 1. Fundamentos & Filosofía de Arquitectura
En Machine Learning y Deep Learning aplicado a código fuente (*Code Intelligence*), existe un principio inquebrantable:
> **"No puedes mejorar lo que no puedes medir con precisión."**

Modificar hiperparámetros o cambiar la arquitectura de `GraphCodeBERT` o `CharCNN` a ciegas sin un conjunto de prueba estandarizado es una receta para el sobreajuste (*overfitting*) y la degradación silenciosa del sistema.

Para evolucionar los modelos de Graphito hacia un nivel de publicación científica o producto de grado industrial, se requiere:
1. **Un Benchmark de Evaluación Canónico (Golden Dataset):** Un banco cerrado de pruebas en C/C++ con tres categorías rigurosamente etiquetadas:
   * **Humano genuino:** Entregas históricas reales de estudiantes previas a 2022 (antes de la explosión de los LLMs).
   * **Sintético puro (LLM):** Códigos generados por GPT-4o, Claude 3.5 Sonnet, DeepSeek-V3 y Gemini Flash con diferentes prompts de estudiante.
   * **Adversarial / Ofuscado:** Código generado por IA sometido a reformateo automático (`clang-format`), renombramiento de variables y reordenamiento de funciones.
2. **Evolución por Canal:**
   * **Canal A (Semántica):** Evaluar `UniXcoder` vs `GraphCodeBERT` + mejoras en la extracción del Grafo de Flujo de Datos (DFG).
   * **Canal B (Estilometría):** Superar la fragilidad de `CharCNN` ante linters mediante métricas independientes del formateo.
   * **Fusión:** Reemplazar la ponderación lineal manual por un clasificador calibrado (XGBoost/LightGBM o MLP).

---

## 2. Mapa de Ruta de Optimización Técnica

```text
       CÓDIGO FUENTE (C / C++)
             │
      ┌──────┴──────────────────────────┐
      ▼                                 ▼
CANAL A: Semántica              CANAL B: Estilometría
(Lógica Invariante)             (Huella Digital del Autor)
┌─────────────────────────┐     ┌─────────────────────────────┐
│ 1. Parser AST/DFG       │     │ 1. CharCNN (Secuencias raw) │
│    (Tree-sitter)        │     │ 2. Métricas de Halstead     │
│ 2. UniXcoder / GCB      │     │ 3. Complejidad Ciclomática  │
│ 3. LoRA Fine-Tuning     │     │ 4. Entropía de Nombres      │
└────────────┬────────────┘     └──────────────┬──────────────┘
             │ Vector Semántico                │ Vector de Estilo
             └───────────────┬─────────────────┘
                             ▼
                 CLASIFICADOR DE FUSIÓN
              (MLP Calibrado / LightGBM)
                             ▼
         [Similitud Semántica, Prob. IA, Dictamen]
```

---

## 3. Especificación Técnica de las Mejoras

### 3.1. Benchmark y Métricas de Desempeño (`tests/benchmarks/benchmark_suite.py`)
Antes de tocar los pesos del modelo, se define la suite de métricas:
* **F1-Score y ROC-AUC** para la clasificación sintético vs humano.
* **Recall en ataques adversariales:** Qué porcentaje de códigos generados por LLM siguen siendo detectados después de pasar por `clang-format -style=Google`.

```python
# Script de evaluación automatizada
def evaluate_model_pipeline(fusion_model, benchmark_dataset):
    y_true = []
    y_pred = []
    
    for item in benchmark_dataset:
        result = fusion_model.fuse(item.file_path)
        y_true.append(item.is_synthetic)
        y_pred.append(result.prob_sintetico >= 0.5)

    report = classification_report(y_true, y_pred, target_names=["Humano", "Sintético"])
    return report
```

### 3.2. Canal A: Extracción Enriquecida de DFG y UniXcoder
* **Problema actual:** `GraphCodeBERT` procesa un máximo de 512 tokens. Códigos largos de C/C++ sufren truncamiento y pérdida de contexto de funciones auxiliares.
* **Mejora:**
  1. Integrar **UniXcoder** (`microsoft/unixcoder-base`), el cual soporta de forma nativa representaciones unificadas de AST + comentarios + código con menor pérdida semántica.
  2. En el parser Tree-sitter (`models/graphcodebert/dfg/parser.py`), expandir el seguimiento del DFG para registrar transferencias de punteros y estructuras de datos (`struct`, `typedef`).

### 3.3. Canal B: Resistencia ante Formateadores de Código (`clang-format`)
* **Problema crítico del CharCNN actual:** Si un alumno pasa el código de ChatGPT por `clang-format`, los espacios, saltos de línea y tabuladores típicos de LLMs se normalizan, reduciendo la efectividad del CharCNN hasta en un 40%.
* **Solución (Estilometría Híbrida):** Extraer características sintácticas independientes del espaciado:
  * **Volumen y Esfuerzo de Halstead:** Razón entre operadores y operandos únicos vs totales.
  * **Complejidad Ciclomática de McCabe:** Conteo de caminos independientes en el grafo de flujo de control.
  * **Entropía de Naming:** Nivel de especificidad de los nombres de variables (los LLMs usan nombres idiomáticos y muy descriptivos como `isPalindromeHelper`, mientras que los alumnos novatos usan `aux`, `cont`, `i`, `flag`).

### 3.4. Fusión Calibrada (`models/fusion_v2.py`)
En lugar de fijar constantes heurísticas (`0.6 * sem_sim + 0.4 * prob_ia`), se entrena una capa densa (MLP de 2 capas: `Linear(fused_dim, 64) -> ReLU -> Linear(64, 3)`) con función de pérdida focal (*Focal Loss*) para manejar el desbalance de clases y calibrar las probabilidades de salida con temperatura.

---

## 4. Riesgos y Anti-Patrones a Evitar
* ❌ **Data Leakage (Fuga de Información):** Entrenar con variantes de un mismo problema y evaluar con ese mismo problema. El modelo debe evaluarse en **problemas no vistos** (*Out-of-Distribution*) para garantizar que generaliza la lógica algorítmica y no memoriza enunciados.
* ⚠️ **Costo computacional de inferencia:** Un modelo con 7B de parámetros (ej. DeepSeek-Coder-7B) tiene gran precisión pero requerirá GPUs dedicadas de 16GB VRAM, encareciendo el despliegue del sistema. Mantenerse en modelos compactos (125M a 350M parámetros como UniXcoder o LoRA) garantiza que Graphito pueda correr en servidores modestos.

---

## 5. Plan de Ejecución del Experimento
1. **Semana 1:** Consolidar el dataset de validación de 300 códigos C/C++ clasificados y correr la línea base (*baseline*) actual. Guardar métricas en `benchmark_baseline_results.json`.
2. **Semana 2:** Añadir el extractor de métricas de Halstead/McCabe al Canal B.
3. **Semana 3:** Reentrenar el clasificador de fusión y comparar curvas ROC vs la línea base.
4. **Semana 4:** Congelar los pesos solo si el F1-Score mejora en al menos un 5% sobre código formateado con `clang-format`.
