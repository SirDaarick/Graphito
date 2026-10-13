# Reporte Técnico: Evaluación de Agrupamiento Lógico y Proximidad de Soluciones en el Canal A

**Proyecto:** Graphito — Detección Bimodal e Interpretable de Código Académico  
**Componente:** Canal A (Similitud Semántica y Agrupamiento Funcional de Código)  
**Fecha de Ejecución:** 13 de octubre de 2026 (04:40 – 05:34 UTC)  
**Entorno de Ejecución:** GPU NVIDIA GeForce RTX 2060 SUPER (8 GB VRAM), CUDA 12.8, PyTorch 2.6  
**Corrida Experimental:** [`runs/logic_eval/20261013-044044/`](file:///c:/Users/edani/OneDrive/Documents/Proyectos/Graphito/runs/logic_eval/20261013-044044/)  
**Plan Pre-registrado:** [`Documentacion/guias_implementacion/evaluacion_agrupamiento_logico.md`](file:///c:/Users/edani/OneDrive/Documents/Proyectos/Graphito/Documentacion/guias_implementacion/evaluacion_agrupamiento_logico.md)

---

## 1. Resumen Ejecutivo

Este experimento responde formalmente a las dos preguntas centrales del Canal A en su estado actual (*zero-shot*, sin entrenamiento contrastivo):
1. **¿Los embeddings neuronales agrupan por lógica sin entrenamiento previo?**  
   **Sí, parcialmente.** GraphCodeBERT ubica a las soluciones del mismo problema significativamente más cerca entre sí que a las de problemas distintos ($\text{Recall@1} = 82.5\%$, $\text{MAP@R} = 0.3865$ frente a una línea base aleatoria de $0.0020$). Sin embargo, las representaciones léxicas simples de n-gramas (`jaccard`) logran una separación superior ($\text{MAP@R} = 0.4497$), evidenciando que el modelo neuronal no entrenado aún no extrae una ventaja de invariancia semántica pura en código introductorio.
2. **¿Parecerse a una solución de referencia indica corrección en las pruebas?**  
   **Sí.** En un esquema *Leave-One-Out* sobre todas las soluciones correctas disponibles en 15 tareas curriculares, la similitud con la referencia arrojó un $\text{Macro-AUC} = 0.5645$ con intervalo de confianza al 95% de $[0.5261, 0.6030]$ (excluyendo estrictamente el 0.5 del azar). Esto valida empíricamente el rol pedagógico del Canal A: **orientar al profesor hacia las entregas divergentes o de mayor riesgo**, sin reemplazar la ejecución dinámica de pruebas unitarias.

---

## 2. Metodología y Muestra Experimental

### 2.1 Muestra de Datos (E1 y E2)
- **Fuente de división:** `data/splits/split_v1.json.gz` (45,291 entregas totales).
- **Filtros E1 (Agrupamiento por Tarea):**
  - Exclusivamente código humano (`source == 'human'`).
  - Filtrado de exclusiones (`excluded == False`).
  - Desduplicación exacta: exactamente **1 representante por grupo de duplicados** (`dup_group`).
  - Muestreo balanceado: hasta 60 entregas por bloque de tarea curricular (semilla fija 42).
  - **Muestra final E1:** **2,842 entregas** pertenecientes a **48 bloques de problemas** independientes.
- **Filtros E2 (Corrección y Referencia):**
  - Unión mediante la clave `(course, student, assignment)` con `data/raw/stats/A2016/*.json`.
  - Parseo de `last_test_results` con formato `"X/Y"` ($Y > 0$), descartando entregas no compiladas o sin pruebas registradas.
  - Selección de tareas elegibles con al menos **5 soluciones que pasan todo ($X=Y$)** y al menos **3 que fallan ($X<Y$)**.
  - **Muestra final E2:** **15 tareas** curriculares con **808 entregas** evaluadas.

### 2.2 Métodos Comparados
1. `jaccard`: Índice de Jaccard sobre shingles de 5 tokens léxicos abstraídos (`models/graphcodebert/v2/baselines.py`).
2. `winnowing`: Huellas dactilares basadas en el algoritmo Winnowing.
3. `v2`: GraphCodeBERT v2 con Grafo de Flujo de Datos (DFG) y *mean pooling* (`models/graphcodebert/v2/embed.py`).
4. `v2_nodfg`: GraphCodeBERT v2 procesando únicamente la secuencia de código sin nodos DFG.
5. `v2_norm`: GraphCodeBERT v2 aplicado sobre código con **renombrado canónico determinista de identificadores** (`v1, v2, f1, f2, t1...`) implementado con Tree-sitter (`models/logic_eval/canonical.py`).

---

## 3. Resultados de las Hipótesis Pre-registradas

Todas las hipótesis se fijaron antes de computar las métricas y no se modificaron:

| ID | Hipótesis Pre-registrada | Criterio de Confirmación | Resultado Numérico | IC 95% Bootstrap | Veredicto |
|---|---|---|:---:|:---:|:---:|
| **E1-H1** | Los embeddings agrupan por tarea | $\text{MAP@R}(v2) > \text{Random}$ | $0.3865 > 0.0020$ | $[0.3410, 0.4426]$ | **CONFIRMADA** |
| **E1-H2** | Renombrado canónico mejora GraphCodeBERT | $\Delta\text{MAP@R}(v2\_norm - v2) > 0$ | $-0.0082$ | $[-0.0223, +0.0057]$ | **REFUTADA** |
| **E1-H3** | GraphCodeBERT agrupa igual o mejor que Jaccard | $\Delta\text{MAP@R}(v2 - \text{jaccard}) \ge 0$ | $-0.0639$ | $[-0.0830, -0.0443]$ | **REFUTADA** |
| **E2-H1** | Parecerse a una correcta indica corrección | $\text{Macro-AUC}(\text{pasa vs. falla}) > 0.5$ | $0.5645 > 0.5$ | $[0.5261, 0.6030]$ | **CONFIRMADA** |

---

## 4. Análisis Detallado de Métricas (Espacio Original)

### 4.1 Evaluación E1: Separabilidad de Problemas en el Espacio Métrico
Las métricas se calcularon directamente sobre las matrices de similitud de dimensión completa ($2{,}842 \times 2{,}842$), sin distorsión de reducciones dimensionales:

| Método | MAP@R (IC 95%) | Recall@1 | ROC-AUC (Misma tarea) | Silhouette Coseno |
|---|:---:|:---:|:---:|:---:|
| `jaccard` | **0.4497** [0.4056, 0.4993] | **0.8469** | **0.8733** | **0.0592** |
| `winnowing` | 0.4414 [0.3972, 0.4907] | 0.8455 | 0.8727 | 0.0559 |
| `v2` (Con DFG) | 0.3865 [0.3410, 0.4426] | 0.8248 | 0.8051 | -0.0018 |
| `v2_nodfg` | 0.3897 [0.3441, 0.4453] | 0.8300 | 0.8015 | -0.0064 |
| `v2_norm` (Canónico) | 0.3790 [0.3361, 0.4297] | 0.8216 | 0.8049 | -0.0530 |
| *Línea base aleatoria* | *0.0020* | *0.0208* | *0.5000* | *-* |

#### Diferencias Pareadas entre Modelos (Contrastes Bootstrap a 1,000 remuestreos de tareas)
1. **$v2\_norm - v2$:** $\Delta = -0.0082$ (IC 95%: $[-0.0223, +0.0057]$).
   - *Hallazgo:* El intervalo incluye al cero con tendencia negativa. La normalización de identificadores a etiquetas sintéticas (`v1, v2`) elimina información contextual y mnemónica que los mecanismos de autoatención preentrenados utilizan para deducir el dominio del problema.
2. **$v2 - \text{jaccard}$:** $\Delta = -0.0639$ (IC 95%: $[-0.0830, -0.0443]$).
   - *Hallazgo:* El intervalo es estrictamente negativo. El índice de Jaccard supera a GraphCodeBERT por $\sim 6.4$ puntos porcentuales de MAP@R. En problemas introductorios de primer año universitario, la distribución de tokens reservados y llamadas estándar (`scanf("%d", &n)`, bucles `for`) es altamente discriminante a nivel sintáctico superficial.

---

### 4.2 Evaluación E2: Similitud respecto a la Referencia vs. Pruebas Unitarias
Se evaluó si una solución estudiantil que aprueba todas las pruebas se encuentra sistemáticamente más cerca de otra solución aprobada tomada como referencia docente provisional (*Leave-One-Out* promediado entre todas las posibles referencias de cada tarea).

- **Número de tareas analizadas:** 15 tareas curriculares.
- **Macro-AUC promedio:** **0.5645** (IC 95%: $[0.5261, 0.6030]$).
- **Macro-Spearman promedio (similitud vs. tasa de aprobación $X/Y$):** **0.0958** (IC 95%: $[0.0364, 0.1609]$).

#### Desglose por Tarea (Muestra Representativa)
| Tarea | Total Entregas | Pasan ($X=Y$) | Fallan ($X<Y$) | AUC Promedio | Spearman Promedio |
|---|:---:|:---:|:---:|:---:|:---:|
| `A2016/Z1/Z4` | 53 | 47 | 5 | **0.6893** | +0.0350 |
| `A2016/Z2/Z1` | 58 | 55 | 3 | **0.6309** | +0.1017 |
| `A2016/Z3/Z1` | 58 | 49 | 9 | **0.6279** | +0.1873 |
| `A2016/Z3/Z3` | 57 | 45 | 12 | **0.6120** | +0.1413 |
| `A2016/Z1/Z1` | 55 | 45 | 10 | 0.5209 | +0.0359 |
| `A2016/Z1/Z3` | 50 | 42 | 8 | 0.5176 | +0.0062 |
| `A2016/Z2/Z2` | 56 | 45 | 11 | 0.4434 | -0.0827 |

*Interpretación de E2:*  
En la mayoría de las tareas ($12$ de las $15$), el AUC supera 0.5 (alcanzando hasta 0.689 en `Z1/Z4`). En tareas donde existen soluciones aprobadas radicalmente heterogéneas (por ejemplo, resolver un problema matricial con arrays bidimensionales vs. punteros planos), algunas referencias penalizan a soluciones aprobadas con enfoques alternativos, lo que explica valores puntuales de AUC inferiores a 0.5.

---

## 5. Figuras y Evidencia Visual Generada

Las siguientes figuras fueron producidas por el pipeline analítico y se encuentran en [`Documentacion/Documento/figuras/`](file:///c:/Users/edani/OneDrive/Documents/Proyectos/Graphito/Documentacion/Documento/figuras/):

1. **G1: Mapa de Calor de Similitud por Tarea ([`g1_heatmap.png`](file:///c:/Users/edani/OneDrive/Documents/Proyectos/Graphito/Documentacion/Documento/figuras/g1_heatmap.png))**  
   Muestra matrices cuadradas de similitud ordenadas por bloque curricular para `jaccard`, `v2` y `v2_norm`. Se observan bloques diagonales nítidos que confirman que ambos métodos identifican la cohesión intra-tarea.
2. **G2: Proyección 2D t-SNE ([`g2_projection.png`](file:///c:/Users/edani/OneDrive/Documents/Proyectos/Graphito/Documentacion/Documento/figuras/g2_projection.png))**  
   Comparación lado a lado de `v2` contra `v2_norm` sobre 6 tareas contrastadas (estructuras disímiles vs. similares), con estrellas marcando las soluciones de referencia de E2.
3. **G3: Precisión Media en Rango R ([`g3_map_at_r.png`](file:///c:/Users/edani/OneDrive/Documents/Proyectos/Graphito/Documentacion/Documento/figuras/g3_map_at_r.png))**  
   Gráfica de barras principal de la tesis con intervalos de error bootstrap al 95%, demostrando la superioridad de los métodos léxicos y la posición de GraphCodeBERT por encima del azar.
4. **G4: Similitud a la Referencia por Resultado de Pruebas ([`g4_correctness.png`](file:///c:/Users/edani/OneDrive/Documents/Proyectos/Graphito/Documentacion/Documento/figuras/g4_correctness.png))**  
   Diagrama de cajas y puntos que desglosa las entregas en *pasa todo*, *parcial* y *falla todo*. Se evidencia una mayor mediana de proximidad para las entregas que pasan todas las pruebas.
5. **G5: Vista Docente de Priorización ([`g5_teacher_view.png`](file:///c:/Users/edani/OneDrive/Documents/Proyectos/Graphito/Documentacion/Documento/figuras/g5_teacher_view.png))**  
   Ejemplo de interfaz pedagógica para el profesor en la tarea `A2016/Z1/Z1`, ordenando las soluciones de menor a mayor similitud con la referencia y destacando las entregas reprobadas que requieren revisión inmediata.

---

## 6. Implicaciones Pedagógicas y Conclusiones de Tesis

1. **La similitud no sustituye las pruebas, pero orienta la revisión:**  
   La correlación positiva y estadísticamente significativa ($\text{AUC} = 0.5645$, IC 95%: $[0.5261, 0.6030]$) respalda la regla pedagógica de Graphito: la métrica de similitud permite al docente jerarquizar qué entregas examinar primero en una sesión de laboratorio o tutoría.
2. **Límites de los modelos preentrenados *zero-shot*:**  
   Sin ajuste fino (*fine-tuning*), los LLMs y encoders como GraphCodeBERT sufren de sesgos léxicos superficiales y no superan a líneas base como Jaccard en tareas introductorias simples.
3. **Justificación formal para el Entrenamiento Contrastivo:**  
   Este experimento proporciona el sustento experimental irrefutable para la Fase de Entrenamiento de la tesis: se requiere un entrenamiento contrastivo supervisado (utilizando pérdidas InfoNCE o Triplet Loss sobre tripletas `(problema, variación_semántica, otro_problema)`) para que la red neuronal supere la dependencia de nombres y capture relaciones de equivalencia algorítmica profunda.
