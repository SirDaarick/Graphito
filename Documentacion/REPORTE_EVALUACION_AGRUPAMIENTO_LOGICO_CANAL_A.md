# Reporte Técnico: Evaluación de Agrupamiento Lógico y Proximidad de Soluciones en el Canal A (Versión Corregida y Deduplicada)

**Proyecto:** Graphito — Detección Bimodal e Interpretable de Código Académico  
**Componente:** Canal A (Similitud Semántica y Agrupamiento Funcional de Código)  
**Fecha de Ejecución:** 13 de octubre de 2026 (15:26 – 15:41 UTC)  
**Entorno de Ejecución:** GPU NVIDIA GeForce RTX 2060 SUPER (8 GB VRAM), CUDA 12.8, PyTorch 2.6  
**Corrida Experimental:** [`runs/logic_eval/20261013-152644/`](file:///c:/Users/edani/OneDrive/Documents/Proyectos/Graphito/runs/logic_eval/20261013-152644/)  
**Plan Pre-registrado:** [`Documentacion/guias_implementacion/evaluacion_agrupamiento_logico.md`](file:///c:/Users/edani/OneDrive/Documents/Proyectos/Graphito/Documentacion/guias_implementacion/evaluacion_agrupamiento_logico.md)

---

## 1. Resumen Ejecutivo

Este experimento evalúa formalmente dos propiedades del Canal A en su estado actual (*zero-shot*, sin entrenamiento contrastivo):
1. **¿Los embeddings neuronales agrupan por lógica sin entrenamiento previo?**  
   **Sí, parcialmente.** GraphCodeBERT ubica a las soluciones del mismo problema significativamente más cerca entre sí que a las de problemas distintos ($\text{Recall@1} = 82.5\%$, $\text{MAP@R} = 0.3865$ frente a una línea base aleatoria de $0.0020$). No obstante, la similitud de n-gramas léxicos abstraídos (`jaccard`) alcanza una precisión superior ($\text{MAP@R} = 0.4497$), evidenciando que el transformador preentrenado sin ajuste fino no supera la correlación léxica superficial de ejercicios introductorios.
2. **¿Parecerse a una solución de referencia indica corrección en las pruebas?**  
   Se detecta una señal **débil pero estadísticamente positiva** ($\text{Macro-AUC} = 0.5598$ para GraphCodeBERT $v2$, con IC 95% de $[0.5199, 0.6015]$). En un par compuesto por una entrega aprobada y una reprobada, el sistema ordena primero a la aprobada el 56% de las veces (donde 50% sería puro azar). Esto confirma que la similitud **complementa** a las pruebas dinámicas al orientar la atención del docente hacia las entregas divergentes o de mayor riesgo, pero **no las sustituye**.

---

## 2. Metodología, Muestra y Deduplicación Rigurosa

### 2.1 Muestra de Datos E1 (Agrupamiento por Tarea)
- **Origen:** `data/splits/split_v1.json.gz`.
- **Criterios de inclusión:** Entregas exclusivamente humanas (`source == 'human'`), no excluidas (`excluded == False`), desduplicadas por grupo de duplicado (`dup_group`) y balanceadas hasta 60 entregas por bloque curricular con semilla fija (42).
- **Muestra final E1:** **2,842 entregas** en **48 bloques de problemas** independientes.

### 2.2 Auditoría, Limpieza y Deduplicación de Datos E2 (Corrección Dinámica)
A partir de la unión con `data/raw/stats/A2016/*.json`, se realizó una auditoría rigurosa para garantizar la independencia estadística de las observaciones:
1. **Reducción de 808 a 632 entregas iniciales:** En ejecuciones preliminares se consideraban 808 registros en A2016 al incluir entregas sin filtrar el estado de pruebas válidas (`last_test_results` nulo o sin formato `"X/Y"` evaluable). Al exigir resultados dinámicos confirmados ($Y > 0$), el universo inicial de A2016 se acotó estrictamente a **632 entregas humanas**.
2. **Verificación de archivos por alumno:** En A2016 existen 6,668 registros de entrega humana; se verificó que la clave `(course, student, assignment)` es unívoca (no hay múltiples archivos por entrega). En el resolvedor de datos se garantiza además la conservación determinista de un único archivo (priorizando el que contiene `main` o mayor volumen en tokens).
3. **Distribución en el split original (632 entregas):**
   - `train`: 396 entregas (62.7%)
   - `test`: 131 entregas (20.7%)
   - `val`: 105 entregas (16.6%)
4. **Deduplicación intra-tarea y descarte de ruido:**
   - **Duplicados consistentes:** Se identificaron y podaron **14 entregas** duplicadas exactas dentro de la misma tarea que compartían idéntico resultado de pruebas, conservando un único representante elegido con semilla fija. Dejar duplicados artificiales inflaría la similitud a 1.0 entre entregas aprobadas.
   - **Duplicados inconsistentes (ruido en ground truth):** Se descartaron **25 entregas** pertenecientes a grupos de duplicados cuyo código idéntico registraba resultados de pruebas discordantes (ej. uno marcaba 10/10 y otro 5/10 debido a ejecuciones desactualizadas en el dataset original).
5. **Umbrales de corte:** Se conservaron únicamente las tareas con al menos 5 entregas aprobadas ($X=Y$) y 3 reprobadas ($X<Y$).
6. **Muestra final E2 limpia:** **14 tareas curriculares** con un total de **543 entregas deduplicadas**.

---

## 3. Hipótesis Pre-registradas y Veredictos

| ID | Hipótesis Pre-registrada | Criterio de Confirmación | Resultado Numérico | IC 95% Bootstrap | Veredicto |
|---|---|---|:---:|:---:|:---:|
| **E1-H1** | Embeddings agrupan por tarea | $\text{MAP@R}(v2) > \text{Random}$ | $0.3865 > 0.0020$ | $[0.3410, 0.4426]$ | **CONFIRMADA** |
| **E1-H2** | Renombrado canónico mejora $v2$ | $\Delta\text{MAP@R}(v2\_norm - v2) > 0$ | $-0.0082$ | $[-0.0223, +0.0057]$ | **REFUTADA** |
| **E1-H3** | GraphCodeBERT agrupa igual o mejor que Jaccard | $\Delta\text{MAP@R}(v2 - \text{jaccard}) \ge 0$ | $-0.0639$ | $[-0.0830, -0.0443]$ | **REFUTADA** |
| **E2-H1** | Parecido a correcta indica corrección | $\text{Macro-AUC}(v2) > 0.5$ | $0.5598 > 0.5$ | $[0.5199, 0.6015]$ | **CONFIRMADA** |

---

## 4. Análisis Detallado de Resultados

### 4.1 Evaluación E1: Agrupamiento por Tarea (Espacio Original)

| Método | MAP@R (IC 95%) | Recall@1 | ROC-AUC (Misma tarea) | Silhouette Coseno |
|---|:---:|:---:|:---:|:---:|
| `jaccard` | **0.4497** [0.4056, 0.4993] | **0.8469** | **0.8733** | **0.0592** |
| `winnowing` | 0.4414 [0.3972, 0.4907] | 0.8455 | 0.8727 | 0.0559 |
| `v2` (Con DFG) | 0.3865 [0.3410, 0.4426] | 0.8248 | 0.8051 | -0.0018 |
| `v2_nodfg` | 0.3897 [0.3441, 0.4453] | 0.8300 | 0.8015 | -0.0064 |
| `v2_norm` (Canónico) | 0.3790 [0.3361, 0.4297] | 0.8216 | 0.8049 | -0.0530 |
| *Línea base aleatoria* | *0.0020* | *0.0208* | *0.5000* | *-* |

#### Discusión E1:
1. **Contraste $v2\_norm - v2$ ($\Delta = -0.0082$, IC 95%: $[-0.0223, +0.0057]$):**  
   Una **posible explicación** es que los nombres mnemónicos de variables aportan información semántica que los mecanismos de autoatención preentrenados en código natural aprovechan; no obstante, este experimento no lo demuestra de forma causal.
2. **Contraste $v2 - \text{jaccard}$ ($\Delta = -0.0639$, IC 95%: $[-0.0830, -0.0443]$):**  
   Existe la hipótesis de que las soluciones en cursos de introducción a la programación comparten un vocabulario acotado (estructuras `for`, `scanf`, librerías homogéneas), permitiendo que la similitud de conjuntos capture nítidamente la separación sintáctica entre problemas sin el costo computacional de un transformador denso.
3. **Interpretación del coeficiente Silhouette ($\approx 0$ a negativo):**  
   El hecho de que el Recall@1 sea alto ($82.5\% - 84.7\%$) mientras el Silhouette es cercano a cero o levemente negativo indica una propiedad topológica clara: **los vecinos más cercanos de cada entrega pertenecen a su misma tarea, pero las tareas no forman agrupaciones densas y globalmente separadas en el espacio métrico**, sino que se intercalan debido a subrutinas comunes a nivel básico.

---

### 4.2 Evaluación E2: Evaluación Multi-Método de Proximidad a la Referencia

En esta versión corregida, se evaluaron los **5 métodos** bajo el mismo esquema *Leave-One-Out* sobre las 14 tareas deduplicadas:

| Método | Macro AUC (IC 95%) | Macro Spearman (IC 95%) |
|---|:---:|:---:|
| `jaccard` | **0.5631** [0.5205, 0.6114] | **0.1069** [0.0364, 0.1859] |
| `winnowing` | 0.5581 [0.5168, 0.6045] | 0.0999 [0.0363, 0.1726] |
| `v2` (GraphCodeBERT + DFG) | 0.5598 [0.5199, 0.6015] | 0.0772 [0.0215, 0.1407] |
| `v2_nodfg` | 0.5536 [0.5119, 0.5992] | 0.0705 [0.0149, 0.1328] |
| `v2_norm` (Canónico) | 0.5550 [0.5049, 0.6094] | 0.0646 [0.0008, 0.1387] |

#### Contrastes Pareados E2 (Macro-AUC sobre tareas remuestreadas con 1,000 bootstraps):
- **$v2 - \text{jaccard}$:** $\Delta = -0.0033$ (IC 95%: $[-0.0516, +0.0358]$).
- **$v2\_norm - v2$:** $\Delta = -0.0047$ (IC 95%: $[-0.0423, +0.0304]$).

*Nota de pre-registro:* La hipótesis principal E2-H1 se pre-registró para `v2`, por lo que el veredicto formal se sostiene en $\text{AUC}(v2) = 0.5598$ (**CONFIRMADA**). Los resultados de `jaccard`, `winnowing`, `v2_nodfg` y `v2_norm` corresponden a un **análisis exploratorio secundario**.

#### Desglose por Tarea en la Muestra Limpia (543 entregas totales):
| Tarea | Total ($N$) | Aprobadas | Reprobadas | AUC (`jaccard`) | AUC (`winnowing`) | AUC (`v2`) | AUC (`v2_nodfg`) | AUC (`v2_norm`) |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| `A2016/Z1/Z1` | 54 | 44 | 10 | 0.4410 | 0.4331 | 0.5232 | 0.5293 | 0.4768 |
| `A2016/Z1/Z3` | 49 | 41 | 8 | 0.5372 | 0.5148 | 0.5158 | 0.5096 | 0.6255 |
| `A2016/Z1/Z4` | 49 | 46 | 3 | 0.6948 | 0.6771 | **0.7457** | 0.7516 | **0.7624** |
| `A2016/Z2/Z1` | 57 | 54 | 3 | 0.6372 | 0.6713 | 0.6276 | 0.6348 | 0.5655 |
| `A2016/Z2/Z2` | 49 | 34 | 15 | 0.5340 | 0.5504 | 0.5327 | 0.5255 | 0.6234 |
| `A2016/Z2/Z3` | 52 | 45 | 7 | 0.5551 | 0.5659 | **0.6343** | 0.6503 | **0.6846** |
| `A2016/Z2/Z4` | 48 | 34 | 14 | 0.5859 | 0.5820 | 0.4955 | 0.5054 | 0.4575 |
| `A2016/Z3/Z1` | 49 | 40 | 9 | 0.5111 | 0.5027 | 0.4905 | 0.4756 | 0.4548 |
| `A2016/Z3/Z2` | 41 | 29 | 12 | 0.4791 | 0.4792 | 0.5074 | 0.5144 | 0.5342 |
| `A2016/Z3/Z3` | 39 | 28 | 11 | 0.4548 | 0.4705 | 0.4458 | 0.4460 | 0.4871 |
| `A2016/Z4/Z1` | 19 | 11 | 8 | 0.5943 | 0.5750 | **0.6295** | 0.6364 | 0.5739 |
| `A2016/Z4/Z2` | 14 | 9 | 5 | 0.5167 | 0.5028 | **0.6000** | 0.5750 | 0.4444 |
| `A2016/Z4/Z3` | 10 | 6 | 4 | **0.7583** | **0.7333** | 0.4833 | 0.4417 | 0.4250 |
| `A2016/Z4/Z4` | 12 | 6 | 6 | 0.5833 | 0.5556 | **0.6056** | 0.5556 | **0.6556** |

*(Nota de verificación: en `Z1/Z4` el total son exactamente 46 aprobadas + 3 reprobadas = **49 entregas**)*.

---

## 5. Figuras Actualizadas en [`Documentacion/Documento/figuras/`](file:///c:/Users/edani/OneDrive/Documents/Proyectos/Graphito/Documentacion/Documento/figuras/)

1. **`g1_heatmap.png`:** Mapa de calor de similitud coseno ordenado por tarea (matrices completas).
2. **`g2_projection.png`:** Proyección 2D t-SNE comparativa de `v2` contra `v2_norm` sobre tareas heterogéneas vs. similares.
3. **`g3_map_at_r.png`:** Gráfica de barras de MAP@R con intervalos bootstrap al 95%.
4. **`g4_correctness.png`:** Paneles comparativos lado a lado (`jaccard`, `v2`, `v2_norm`) de la similitud según resultado en pruebas.
5. **`g5_teacher_view.png`:** Interfaz ilustrativa de priorización docente para `A2016/Z1/Z1` basada en $v2$.
6. **`clusters_canal_a.png`:** Proyección t-SNE (coseno, perplejidad 30, inicialización PCA, semilla 42) de embeddings `v2` de GraphCodeBERT sin ajuste fino. Panel (a): 3 tareas con lógica distinta, elegidas como el triplete de menor similitud cruzada (`A/Z2/Z1`, `B/Z5/Z5`, `B/Z6/Z4`), más un punto externo seleccionado con una regla objetiva: entre las tareas E1 que no están en el panel, la de menor similitud coseno media (en el espacio original `v2`) respecto a la unión de las tres tareas del panel, y dentro de ella la solución de menor similitud media (resultado: `A/Z1/Z1`, similitud media 0.9304 con el panel; solución elegida con 0.8970). En la figura, ese punto (cruz morada) no queda dentro de ningún grupo: se ubica en el espacio entre los grupos de `B/Z5/Z5` y `A/Z2/Z1`, a unas 1.9 unidades de t-SNE del borde derecho del grupo de `B/Z5/Z5`, que es el más cercano; por lo tanto, la separación es parcial y no debe leerse como un valor atípico claro. Cada estrella (una por tarea, con el color de su tarea) marca la solución de referencia de estudiante usada como ancla visual; el conjunto de datos no incluye soluciones del docente. Las estrellas son la primera solución muestreada de cada tarea: las estadísticas disponibles solo permiten verificar el estado de aprobación de una fracción mínima de la muestra (40 de 2842 entregas, ninguna en las tareas de las estrellas), por lo que la leyenda las describe como "ejemplo de alumno" y no afirma que hayan aprobado. Panel (b): 2 tareas con lógica similar (`B/Z3/Z5`, `B/Z3/Z6`) con superposición parcial. El panel (a) mezcla tareas de los cursos A y B, por lo que parte de la separación puede reflejar convenciones de curso y no solo la lógica. La proyección 2D es ilustrativa y distorsiona distancias; las conclusiones se basan en MAP@R y silhouette calculados en el espacio original.

---

## 6. Limitaciones del Estudio

1. **Naturaleza de la solución de referencia:** Al no contar con una solución canónica oficial provista por los docentes en el dataset histórico, la referencia se aproxima mediante soluciones aprobadas de estudiantes bajo un esquema *Leave-One-Out*.
2. **Sesgo en la tasa de aprobación:** La muestra de pruebas está marcadamente sesgada: ~80% de los estudiantes aprueban todas las pruebas en las tareas elegibles, lo que reduce la representatividad de fallos atípicos.
3. **Carácter temporal de `last_test_results`:** El campo corresponde a la última ejecución registrada en el entorno de desarrollo y podría no coincidir exactamente con el archivo final congelado de entrega.
4. **Acotamiento a A2016:** La evaluación E2 se realizó exclusivamente sobre la cohorte A2016, que es la única con métricas dinámicas completas.
5. **Magnitud del efecto:** La correlación de Spearman es modesta ($\rho \approx 0.077 - 0.107$), reafirmando que la similitud léxico-semántica es un indicador orientativo y no un criterio resolutivo.
6. **Estado del repositorio en la corrida:** la corrida 20261013-152644 registra `dirty: true` en `config.json`; al verificar con `git status --short` hay archivos modificados ajenos al experimento (`models/char_cnn/best_model.pth`, `models/robustness/scoring.py`, `scripts/robustness_experiment.py`) y archivos sin seguimiento no relacionados; el código del experimento de agrupamiento lógico estaba confirmado en el commit `f1a85fb`.

---

## 7. Conclusiones para la Tesis

1. **La similitud complementa y prioriza:** Los resultados sugieren una señal débil pero positiva ($\text{Macro-AUC} = 0.5598$, Spearman $\approx 0.077 - 0.107$) para orientar la atención del docente hacia códigos atípicos o fallidos; la similitud complementa a las pruebas dinámicas, no las sustituye.
2. **Diferenciación entre agrupamiento general y corrección funcional:**
   - En **E1 (agrupamiento por tarea)**, la representación léxica (`jaccard`) agrupó mejor las soluciones que GraphCodeBERT $v2$ con una diferencia estadísticamente significativa ($\Delta\text{MAP@R} = -0.0639$, IC 95%: $[-0.0830, -0.0443]$).
   - En **E2 (proximidad a la referencia y corrección)**, se observó un empate práctico entre métodos (`jaccard` AUC 0.5631 vs. `v2` AUC 0.5598; contraste pareado con $\Delta = -0.0033$, cuyo intervalo de confianza incluye el cero $[-0.0516, +0.0358]$).
3. **Motivación para el entrenamiento contrastivo:** Los hallazgos motivan explorar el entrenamiento contrastivo supervisado (pérdidas InfoNCE / SimCLR con aumentaciones de preservación semántica) para inducir invariancias genuinas en los encoders preentrenados y superar la dependencia de rasgos léxicos superficiales.
 
---

## 8. Registro de Correcciones Aplicadas

1. **Revisión y aclaración del conteo de entregas iniciales en E2:**
   - Se documentó la razón exacta por la cual la cohorte A2016 pasó de 808 registros iniciales a 632: 176 registros carecían de resultados válidos de ejecución en pruebas (`last_test_results == null` o sin formato `"X/Y"` evaluable).
2. **Deduplicación intra-tarea en E2:**
   - Se podaron 14 duplicados exactos consistentes (para no inflar artificialmente el AUC con similitudes de 1.0 entre entregas idénticas aprobadas).
   - Se descartaron 25 entregas con resultados contradictorios dentro del mismo grupo de duplicados (ruido en ground truth).
   - Muestra final E2 limpia: 543 entregas en 14 tareas curriculares.
3. **Automatización de la tabla E2 por tarea:**
   - La tabla de la sección 4.2 se genera automáticamente desde `e2_metrics.json` mediante código sin valores manuales.
   - Se corrigió el conteo de la tarea `A2016/Z1/Z4`: son exactamente 46 aprobadas + 3 reprobadas = 49 entregas.
4. **Evaluación multi-método completa en E2:**
   - Se evaluaron los 5 métodos (`jaccard`, `winnowing`, `v2`, `v2_nodfg`, `v2_norm`) bajo el mismo protocolo *Leave-One-Out*.
   - Contrastes pareados por bootstrap calculados sobre las mismas tareas remuestreadas.
5. **Generación objetiva de figura de clusters para la tesis:**
   - Incorporación de `plot_cluster_showcase` en `models/logic_eval/plots.py` con selección cuantitativa de tareas basada en similitud cruzada (triplete con menor similitud y par con mayor similitud).
   - Generación de `Documentacion/Documento/figuras/clusters_canal_a.png` (300 dpi) y registro de metadatos en `cluster_showcase.json`.
   - Corrección posterior: el punto externo ya no se elige de forma ad hoc, sino con la regla objetiva descrita en la sección 5 (ítem 6) y registrada en `cluster_showcase.json`; la leyenda "Referencia docente" se reemplazó por "Solución de referencia (ejemplo de alumno)" porque el conjunto de datos solo contiene soluciones de estudiantes y su estado de aprobación no puede verificarse para estas tareas; cada estrella usa el color de su tarea; la perplejidad de t-SNE pasó de 25 a 30; la figura se regeneró con `python scripts/logic_grouping_eval.py --only-cluster-figure --run-dir runs/logic_eval/20261013-152644` sin crear una nueva corrida.
6. **Calibración de redacción y conclusiones:**
   - Se evitaron afirmaciones de validación definitiva o causal; se califica la señal como débil pero positiva ($\text{Macro-AUC} = 0.5598$).
   - Se diferenció explícitamente el agrupamiento general (E1, donde Jaccard supera a GraphCodeBERT) de la proximidad funcional (E2, donde hay empate práctico).

