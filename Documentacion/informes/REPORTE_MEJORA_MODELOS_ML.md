# Auditoría Técnica, Remediaciones y Plan de Mejora de Modelos de Machine Learning en Graphito

**Proyecto:** Graphito — Plataforma Bimodal de Integridad Académica y Detección de Código Asistido por IA  
**Institución:** Escuela Superior de Cómputo (ESCOM - IPN)  
**Fecha:** Octubre 2026  
**Estado de la Fase 1:** Completada y Verificada Empíricamente  

---

## 1. Resumen Ejecutivo

Graphito implementa una arquitectura bimodal para el análisis forense de código fuente en C/C++:
1. **Canal A (Semántica Algorítmica):** `GraphCodeBERT` enriquecido con Grafos de Flujo de Datos (DFG) extraídos mediante `tree-sitter`, acoplado a un adaptador LoRA (20,000 pasos de fine-tuning) para proyectar representaciones invariantes a la sintaxis y refractarias a la ofuscación.
2. **Canal B (Estilometría Forense):** `MultiScale CharCNN` con convoluciones 1D paralelas ($k \in \{3, 5, 7, 9\}$) y *Global Adaptive Avg/Max Pooling*, orientado a capturar la huella digital micro-estructural (espaciado, asignaciones, convenciones de nombrado).
3. **Motor de Fusión y Decisión Bimodal:** Combina ambas señales para emitir dictámenes éticos y no incriminatorios (`SIN_ALERTAS`, `REVISION_ESTILOMETRICA`, `REVISION_SEMANTICA`, `DISCREPANCIA_DUAL`) acompañados de explicaciones de Inteligencia Artificial Explicable (XAI).

Durante la auditoría técnica exhaustiva de los modelos, se detectaron cuatro fallas críticas de diseño e inferencia que provocaban falsos positivos severos y degradación en el canal semántico. Este documento detalla el diagnóstico matemático, las remediaciones inmediatas ejecutadas (Fase 1), la validación experimental rigurosa y la hoja de ruta para el reentrenamiento en fases posteriores (Fases 2 a 4).

---

## 2. Diagnóstico Empírico de Patologías (Causas Raíz)

### 2.1. Canal Estilométrico (MultiScale CharCNN): Train/Serve Skew y Colapso por Longitud

* **Síntoma Detectado:** Código humano elemental como `int main() { return 0; }` arrojaba **98.7% de probabilidad de ser generado por Inteligencia Artificial**.
* **Causa Raíz 1 (Sobreajuste al Dataset Base):** El modelo reportaba una métrica aparente de $F_1 = 0.991$ en `models/char_cnn/README.md`. No obstante, la auditoría reveló que fue entrenado sobre un dataset sintético altamente homogéneo de solo 2,132 muestras (Universidad de Sarajevo y 3 perfiles de DeepSeek). El modelo memorizó distribuciones específicas de caracteres y espaciado en lugar de aprender características estilométricas generalizables.
* **Causa Raíz 2 (Dilución en Pooling Adaptativo vs. Longitud Trivial):** En códigos de longitud minúscula ($< 60$ caracteres), la densidad estadística de n-gramas de autoría es inexistente. Los kernels convolucionales operaban sobre ruido estocástico de pocos caracteres. Asimismo, en el preprocesamiento existía una inconsistencia entre `pad=True` (que rellenaba artificialmente hasta 4096 caracteres, diluyendo el `adaptive_avg_pool1d` hasta 23 veces) y la longitud nativa del código.

### 2.2. Canal Semántico (GraphCodeBERT): Desconexión del Adaptador LoRA

* **Síntoma Detectado:** El backend ejecutaba inferencia únicamente con el modelo base genérico `microsoft/graphcodebert-base`, ignorando el entrenamiento previo.
* **Causa Raíz:**
  1. En `models/graphcodebert/config.py`, `adapter_path` tenía como valor por defecto `None`.
  2. El directorio local `models/weights/` contenía archivos vacíos de 0 bytes producto de una descarga incompleta previa.
  3. A pesar de existir un adaptador LoRA entrenado a 20,000 pasos en `models/graphcodebert/adaptador-lora-20k/adaptador-lora-20k/final/adapter_model.safetensors`, ni la infraestructura del backend (`RealBimodalInferenceEngine`) ni los scripts de prueba lo cargaban en memoria.

### 2.3. Canal Semántico: Incompatibilidad de Máscara DFG en Transformers 5.x

* **Síntoma Detectado:** Riesgo de cálculos incorrectos o excepciones en el mecanismo de atención al procesar código con Grafo de Flujo de Datos.
* **Causa Raíz:** En `models/graphcodebert/inference.py`, la atención DFG se suministra directamente a `RobertaEncoder.encoder`, omitiendo `RobertaModel.get_extended_attention_mask`. En Transformers 5.14, una máscara booleana (`True`/`False`) o binaria (`1.0`/`0.0`) sumada algebraicamente a los pesos de atención (`attn_weights + attention_mask`) no anula la atención, sino que suma $1.0$ a tokens no relacionados y $0.0$ a los enmascarados, en lugar de utilizar un sesgo aditivo de $-\infty$.

### 2.4. Orquestador de Análisis: Discontinuidad Abrupta por Umbral Lineal Truncado

* **Síntoma Detectado:** Frontera de decisión no diferenciable y colapso artificial de similitud.
* **Causa Raíz:** `AnalysisOrchestrator.calibrate_semantic_similarity` utilizaba un corte rígido:
  $$\text{calibrado} = \begin{cases} 0.0 & \text{si } s_{\text{cruda}} \le 0.75 \\ \frac{s_{\text{cruda}} - 0.75}{1.0 - 0.75} & \text{si } s_{\text{cruda}} > 0.75 \end{cases}$$
  Esto provocaba que pares de programas con similitud cruda de $0.7499$ colapsaran a $0.0$, mientras que $0.7501$ pasaba bruscamente a $0.0004$, castigando injustamente códigos con pequeñas variaciones funcionales.

---

## 3. Remediaciones Implementadas (Fase 1 — Inferencia y Blindaje)

Se ejecutó la totalidad de las soluciones inmediatas de costo cero de reentrenamiento, asegurando estabilidad y rigor matemático.

### 3.1. Salvaguarda Pericial y Preservación de Pooling en CharCNN
* **Archivo:** `models/char_cnn/inference.py`
* **Implementación:**
  1. Se incorporó una salvaguarda determinista previa a la red neuronal: si el código posee menos de 60 caracteres no-espacio (`len("".join(text.split())) < 60`), se clasifica como `humano` con $p_{\text{sintético}} = 0.05$, $p_{\text{humano}} = 0.95$ y bandera `"insufficient_length": True`.
  2. En códigos sustanciales ($\ge 60$ caracteres), se fijó `pad=False` por defecto para respetar el diseño de *Global Adaptive Pooling*, permitiendo que el promedio y máximo global se calculen exclusivamente sobre los tokens reales del código.

### 3.2. Carga y Fusión Automática de LoRA en GraphCodeBERT
* **Archivos:** `models/graphcodebert/config.py`, `models/graphcodebert/inference.py`, `backend/app/infrastructure/inference/real_engine.py`
* **Implementación:**
  1. En `GraphCodeBERTConfig.__post_init__`, se implementó el autodescubrimiento del adaptador LoRA de 20,000 pasos:
     ```python
     if self.adapter_path is None:
         default_lora = Path(__file__).parent / "adaptador-lora-20k" / "adaptador-lora-20k" / "final"
         if default_lora.exists():
             self.adapter_path = default_lora
     ```
  2. Al instanciar `GraphCodeBERTInference`, se utiliza `peft.PeftModel.from_pretrained` seguido de `.merge_and_unload()`, fusionando los pesos del adaptador en las matrices densas del encoder. Esto elimina el overhead de cómputo en inferencia y garantiza que todas las llamadas generen embeddings calibrados con el conocimiento especializado de DFG.
  3. `RealBimodalInferenceEngine` verifica la presencia de los pesos fusionados y reporta el estado en logs: `GraphCodeBERT engine inicializado exitosamente [con adaptador LoRA (20k)]`.

### 3.3. Máscara Aditiva en Float32 para Atención DFG
* **Archivo:** `models/graphcodebert/inference.py`
* **Implementación:** La matriz tetradimensional `graph_mask_4d` se proyecta a punto flotante (`torch.float32`), asignando $0.0$ a las aristas válidas del DFG y $-10000.0$ a las posiciones enmascaradas:
  ```python
  graph_mask_4d = (1.0 - graph_mask_4d.float()) * -10000.0
  ```
  Esto garantiza compatibilidad total con `RobertaEncoder` en Transformers 5.x y PyTorch 2.x sin desbordamientos numéricos ni atención espuria.

### 3.4. Calibración Logística Sigmoidal Suave
* **Archivo:** `backend/app/application/orchestrator/analysis_orchestrator.py`
* **Formulación Matemática:** Sustitución de la función lineal discontinua por una transformación monótona creciente $C^\infty$ normalizada estrictamente en el intervalo $[0.0, 1.0]$:
  $$g(s) = \frac{1}{1 + e^{-k(s - x_0)}}$$
  $$f(s) = \frac{g(s) - g(0)}{g(1) - g(0)}$$
  donde:
  * $x_0 = 0.85$ es el punto de inflexión empírico (centroide de separación entre programas disímiles y variantes algorítmicas en el espacio anisotrópico de C/C++).
  * $k = 24.0$ es el factor de escala de pendiente.
* **Comportamiento Empírico de la Curva:**
  * Similitud cruda $0.70$ (programas no relacionados) $\rightarrow f(0.70) = 0.0273$ ($2.73\%$).
  * Similitud cruda $0.7923$ (ej. QuickSort vs. FizzBuzz) $\rightarrow f(0.7923) = 0.2057$ ($20.57\%$, bajo umbral).
  * Similitud cruda $0.85$ (frontera de transición) $\rightarrow f(0.85) = 0.5137$ ($51.37\%$).
  * Similitud cruda $0.92$ (variación moderada) $\rightarrow f(0.92) = 0.8659$ ($86.59\%$).
  * Similitud cruda $0.9773$ (variante del mismo algoritmo) $\rightarrow f(0.9773) = 0.9811$ ($98.11\%$).
  * Extremos: $f(0.0) = 0.0$, $f(1.0) = 1.0$.

---

## 4. Validación Experimental y Resultados

### 4.1. Suite de Pruebas Unitarias y Robustez (`pytest`)
Se ejecutó la suite automatizada completa sobre el motor de Machine Learning:
```powershell
pytest tests/test_dfg_parser.py tests/test_char_cnn_robustness.py tests/test_calibration_experiment.py -v
```

**Resultado Global:** `47 passed, 1 skipped in 19.23s` (100% de las pruebas ejecutables aprobadas).

1. **Parser DFG Tree-Sitter (`tests/test_dfg_parser.py`):** 39/39 pruebas superadas. Verificación rigurosa de extracción de variables, flujo de datos, estructuras, aritmética de punteros y aliasing en C y C++.
2. **Robustez Estilométrica (`tests/test_char_cnn_robustness.py`):**
   * *Invarianza ante Formateo:* Pruebas comparativas entre código sin formato y código formateado con linters arrojaron dictámenes consistentes sin alteración de clase.
   * *Invarianza ante Comentarios:* La sanitización previa de comentarios C/C++ (`//` y `/* ... */`) impidió que comentarios explicativos engañaran a la red.
   * *Autocomparación Bimodal:* Similitud de autocomparación de código idéntico verificada exactamente en $1.000000$ (sin penalización por diferencias de estilo).
3. **Calibración y Orquestador (`tests/test_calibration_experiment.py`):**
   * *Código Humano vs. Sintético en CharCNN:*
     * Humano FizzBuzz: $P(\text{IA}) = 20.27\%$, $P(\text{Humano}) = 79.73\%$ $\rightarrow$ Clasificación correcta como `humano`.
     * IA FizzBuzz canónico: $P(\text{IA}) = 99.48\%$, $P(\text{Humano}) = 0.52\%$ $\rightarrow$ Clasificación correcta como `sintético`.
   * *Calibración de Anisotropía en GraphCodeBERT:*
     * FizzBuzz vs. Variante Ofuscada: Similitud Cruda = $97.73\%$ $\rightarrow$ Similitud Calibrada = $98.11\%$ ($> 75\%$).
     * FizzBuzz vs. QuickSort (Diferente problema): Similitud Cruda = $79.23\%$ $\rightarrow$ Similitud Calibrada = $20.57\%$ ($< 25\%$).
   * *Motor de Decisión Bimodal:*
     * Humano QuickSort vs. FizzBuzz: `SIN_ALERTAS` (Aprobado).
     * AI FizzBuzz vs. FizzBuzz: `DISCREPANCIA_DUAL` (Alerta pericial docente).
     * Humano FizzBuzz vs. FizzBuzz: `REVISION_SEMANTICA` (Alerta de convergencia estructural).

### 4.2. Evaluación con Casos Reales del Temario de ESCOM IPN (`tests/test_escom_units.py`)
Evaluación empírica con problemas del plan de estudios oficial de Fundamentos de Programación (ISC 2020) correspondientes a las Unidades I (Programación Estructurada), II (Arreglos y Punteros) y III (Memoria Dinámica y Archivos):

| Unidad Temática | Caso de Prueba | Tipo de Par | Similitud Coseno Cruda |
| :--- | :--- | :--- | :--- |
| **Unidad I** | Determinar si un número es primo (For clásico vs. While optimizado) | Mismo problema | **0.9496** |
| **Unidad I** | Calcular factorial (Bucle for vs. Do-while decremental) | Mismo problema | **0.9339** |
| **Unidad II** | Invertir cadenas in-place (Indexación `str[i]` vs. Aritmética de punteros) | Mismo problema | **0.8925** |
| **Unidad II** | Buscar en `struct Alumno` (Notación punto `lista[i].promedio` vs. flecha `ptr->promedio`) | Mismo problema | **0.9130** |
| **Unidad III** | Arreglo dinámico con `malloc` (Indexación simple vs. Aritmética `*(ptr+i)`) | Mismo problema | **0.9039** |
| **Unidad III** | Copiado de archivo de texto (`fgetc` caracter a caracter vs. `fgets` línea a línea) | Mismo problema | **0.9524** |
| **Negativo (I)** | Primo vs. Factorial | Distinto problema | **0.9229** |
| **Negativo (II)** | Invertir string vs. Contar vocales | Distinto problema | **0.8576** |
| **Negativo (III)** | Duplicar archivo vs. Contar líneas | Distinto problema | **0.8440** |

* **Promedio Mismo Problema (Positivos / Equivalencia Lógica):** **0.9242**
* **Promedio Problemas Distintos (Negativos):** **0.8748**
* **Margen de Separación (GAP):** **+0.0494**
* **Conclusión:** El modelo distingue satisfactoriamente algoritmos equivalentes de algoritmos diferentes a nivel de flujo de datos, aun con transformaciones sintácticas agresivas en C.

---

## 5. Plan de Mejora Continua: Fases 2, 3 y 4 (Entrenamiento y Calibración Avanzada)

Las siguientes fases están diseñadas para ser ejecutadas en un entorno con acelerador de hardware (GPU dedicada Nvidia CUDA $\ge 16$ GB VRAM):

```text
┌────────────────────────────────────────────────────────────────────────┐
│                      HOJA DE RUTA DE OPTIMIZACIÓN                      │
└────────────────────────────────────────────────────────────────────────┘
  [FASE 1: Remediaciones de Inferencia] ──▶ COMPLETADA (Octubre 2026)
         │  • Salvaguarda CharCNN (<60 chars)
         │  • Autodescubrimiento LoRA (20k steps)
         │  • Máscara aditiva Float32 DFG
         │  • Calibración sigmoidal x0=0.85, k=24.0
         ▼
  [FASE 2: Curación y Expansión del Corpus] (Requiere GPU / Almacenamiento)
         │  • Extracción de CodeNet / The Stack (C/C++ genuino pre-2022)
         │  • Generación balanceada con LLMs modernos (GPT-4o, Claude 3.5, DeepSeek)
         │  • Balanceo estricto por longitud y complejidad ciclomática
         ▼
  [FASE 3: Reentrenamiento Asimétrico de Modelos]
         │  • CharCNN: Loss con regularización de longitud y Data Augmentation
         │  • GraphCodeBERT: Fine-Tuning LoRA con Triplet Margin Loss
         │  • Fusión Bimodal con clasificador calibrado (XGBoost / LightGBM)
         ▼
  [FASE 4: Calibración Bayesiana y Platt Scaling]
         │  • Regresión Isotónica (Isotonic Regression) sobre conjunto de validación
         │  • Calibración de temperatura para probabilidades probabilísticamente fieles
         │  • Reporte de intervalos de confianza periciales para el docente
```

### 5.1. Fase 2: Curación y Balanceo del Dataset
* **Problema a Resolver:** El dataset de entrenamiento actual de CharCNN contaba con solo 2,132 muestras sesgadas.
* **Acción Técnica:**
  1. Integrar un corpus de al menos 50,000 archivos de C/C++ procedentes de competencias de programación históricas (CodeNet / Project Euler / repositorios pre-2022) para representar estilos humanos diversos (estudiantes principiantes, código limpio, código con malas prácticas).
  2. Generar el contraejemplo sintético utilizando prompts que simulen diferentes niveles académicos con modelos actuales (Claude 3.5 Sonnet, GPT-4o, DeepSeek-Coder-V2).
  3. Aplicar técnicas de aumento de datos (*data augmentation*) basadas en reformateo automático (`clang-format`), ofuscación de identificadores e inserción de comentarios espurios.

### 5.2. Fase 3: Reentrenamiento Asimétrico
* **CharCNN:** Entrenar con función de pérdida ponderada que penalice el sesgo por longitud de secuencia y normalización por lotes sobre secuencias de longitud variable.
* **GraphCodeBERT:** Ejecutar fine-tuning sobre el adaptador LoRA utilizando *Triplet Margin Loss*, donde el ancla es la referencia del docente, el positivo es una solución válida de un estudiante, y el negativo es una solución a un problema distinto. Esto forzará una mayor separación en el espacio latente (ampliando el margen actual de $+0.0494$ a $\ge +0.20$).

### 5.3. Fase 4: Calibración de Probabilidades (Platt Scaling)
* **Objetivo:** Garantizar que una probabilidad reportada del $80\%$ corresponda empíricamente a que 8 de cada 10 casos son efectivamente sintéticos.
* **Acción Técnica:** Ajustar un escalamiento de temperatura o regresión isotónica sobre las probabilidades de salida de CharCNN en un conjunto de retención (*holdout validation set*), eliminando la saturación extrema a valores cercanos a $0.99$.

---

## 6. Guía Operativa de Comandos

Para reproducir y verificar las pruebas del sistema en el entorno local:

```powershell
# 1. Configurar variables de entorno en PowerShell
$env:PYTHONPATH = ".;backend"
$env:PYTHONIOENCODING = "utf-8"

# 2. Ejecutar suite de pruebas de modelos y orquestador
python -m pytest tests/test_dfg_parser.py tests/test_char_cnn_robustness.py tests/test_calibration_experiment.py -v

# 3. Ejecutar benchmark sobre casos reales de ESCOM IPN
python tests/test_escom_units.py

# 4. Ejecutar benchmark de arquetipos de estudiantes
python scripts/benchmark_student_archetypes.py
```

---

## 7. Referencia de Archivos Modificados

* `models/char_cnn/inference.py`: Salvaguarda para fragmentos triviales y configuración de padding adaptativo.
* `models/graphcodebert/config.py`: Detección automática del adaptador LoRA de 20k pasos.
* `models/graphcodebert/inference.py`: Fusión transparente LoRA y soporte de máscara aditiva en float32 para atención DFG.
* `backend/app/infrastructure/inference/real_engine.py`: Inicialización del adaptador real bimodal con verificación de pesos LoRA.
* `backend/app/application/orchestrator/analysis_orchestrator.py`: Calibración logística sigmoidal suave ($x_0 = 0.85, k = 24.0$).
* `tests/test_calibration_experiment.py`: Actualización de etiquetas y validación de calibración bimodal.
* `tests/test_char_cnn_robustness.py`: Tolerancia a rutas remotas y archivo temporal para autocomparación no diluyente.
