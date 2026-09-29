# Guía de Implementación 09: Estrategia de Mejora de Modelos & Benchmark Riguroso

## 1. Fundamentos & Filosofía de Arquitectura
En Machine Learning y Deep Learning aplicado a código fuente (*Code Intelligence*), existe un principio inquebrantable:
> **"No puedes mejorar lo que no puedes medir con precisión."**

Modificar hiperparámetros o cambiar la arquitectura de `GraphCodeBERT` o `CharCNN` a ciegas sin un conjunto de prueba estandarizado es una receta para el sobreajuste (*overfitting*).

Para evolucionar los modelos de Graphito, se requiere:
1. **Un Benchmark de Evaluación Canónico (Golden Dataset):**
   * **Humano genuino:** Entregas históricas reales de estudiantes previas a 2022.
   * **Sintético puro (LLM):** Códigos generados por GPT-4o, Claude 3.5 Sonnet, DeepSeek y Gemini.
   * **Adversarial / Ofuscado:** Código generado por IA sometido a reformateo automático (`clang-format`), renombramiento de variables y reordenamiento de funciones.
2. **Evolución por Canal:**
   * **Canal A (Semántica):** Evaluar `UniXcoder` vs `GraphCodeBERT` + mejoras en la extracción del Grafo de Flujo de Datos (DFG).
   * **Canal B (Estilometría):** Superar la fragilidad de `CharCNN` ante linters mediante métricas independientes del formateo (Halstead y McCabe).
   * **Fusión:** Reemplazar la ponderación lineal manual por un clasificador calibrado.

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
```python
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

### 3.2. Canal B: Resistencia ante Formateadores de Código (`clang-format`)
* **Problema crítico del CharCNN actual:** Si un alumno pasa el código de ChatGPT por `clang-format`, los espacios, saltos de línea y tabuladores típicos de LLMs se normalizan, reduciendo la efectividad del CharCNN.
* **Solución (Estilometría Híbrida):** Extraer características sintácticas independientes del espaciado:
  * **Volumen y Esfuerzo de Halstead.**
  * **Complejidad Ciclomática de McCabe.**
  * **Entropía de Naming:** Nivel de especificidad de los nombres de variables.

---

## 4. Riesgos y Anti-Patrones a Evitar
* ❌ **Data Leakage (Fuga de Información):** El modelo debe evaluarse en **problemas no vistos** (*Out-of-Distribution*) para garantizar que generaliza la lógica algorítmica y no memoriza enunciados.

---

## 5. Plan de Ejecución
1. Consolidar el dataset de validación de 300 códigos C/C++ clasificados y correr la línea base actual.
2. Añadir el extractor de métricas de Halstead/McCabe al Canal B.
3. Reentrenar el clasificador de fusión y comparar curvas ROC vs la línea base.
