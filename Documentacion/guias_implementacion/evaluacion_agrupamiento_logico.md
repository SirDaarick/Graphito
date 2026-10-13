# Plan de evaluación: agrupamiento por lógica en el Canal A

**Objetivo de la tesis:** apoyar la evaluación docente mostrando qué tan parecida es cada solución de un
alumno a la solución del profesor. El sistema no emite veredictos; el docente interpreta la información.

**Pregunta de esta evaluación:** sin entrenar ningún modelo, ¿los embeddings actuales colocan cerca las
soluciones con la misma lógica y lejos las de lógica distinta? ¿Parecerse a una solución correcta indica
que la solución es correcta?

**Alcance:** solo evaluación de modelos existentes (zero-shot). El entrenamiento contrastivo queda como
trabajo futuro, justificado con estos resultados.

---

## 0. Datos disponibles (verificados el 12 de octubre de 2026)

| Recurso | Estado |
|---|---|
| `data/splits/split_v1.json.gz` | 45,291 entradas (43,771 humanas, 1,520 IA). Campos: `course`, `assignment`, `student`, `split`, `excluded`, `dup_group`. Cargador: `models/evaluation/manifest.py`. |
| Resultados de pruebas | `data/raw/stats/<curso>/student<id>.json`, campo `last_test_results` con formato `"X/Y"` (`data/raw/readme.txt:19`). Solo ~850 entregas de tareas `Zn/Zm` lo tienen; se unen ~677 entregas humanas del split, 632 de ellas de A2016. |
| Solución oficial del profesor | **No existe en el dataset.** Los archivos `data/output/**/ref_*.c` son generaciones de un LLM sin probar y no se usan como referencia. |

**Llave de unión** entre el split y los resultados: `(course, student, assignment)`. En el archivo de
estadísticas del alumno, la llave es igual a `entry.assignment` (por ejemplo `A2016/Z1/Z1`).

**Regla del split:** como ningún método de esta evaluación se entrena, **no hay fuga de información**
si se usan archivos de train, val y test. La separación train/test solo protege a modelos ajustados.
Se documenta así en la tesis. Si en el futuro se entrena un modelo, esta evaluación debe repetirse
solo sobre los problemas de test.

---

## 1. Hipótesis (pre-registro)

Se escriben antes de ejecutar y no se modifican después.

| ID | Hipótesis | Se confirma si | Se refuta si |
|---|---|---|---|
| **E1-H1** | Los embeddings agrupan por tarea: las soluciones de la misma tarea están más cerca entre sí que las de tareas distintas. | MAP@R de `v2` > MAP@R de un orden aleatorio, con IC95 separado | El IC95 de MAP@R incluye el valor aleatorio |
| **E1-H2** | Normalizar los identificadores mejora el agrupamiento de GraphCodeBERT. | ΔMAP@R(`v2_norm` − `v2`) > 0 con IC95 que excluye 0 | El IC95 incluye 0 o es negativo |
| **E1-H3** | GraphCodeBERT agrupa por lógica igual o mejor que Jaccard. | ΔMAP@R(`v2` − `jaccard`) ≥ 0 | ΔMAP@R < 0 con IC95 que excluye 0 |
| **E2-H1** | Parecerse a una solución correcta indica corrección: las entregas que pasan todas las pruebas están más cerca de la referencia que las que fallan. | AUC(pasa vs. no pasa) > 0.5 con IC95 que excluye 0.5 | El IC95 incluye 0.5 |

**Métrica principal:** MAP@R en la Evaluación 1 (E1), vista completa, método `v2`.

---

## 2. Métodos comparados

| Método | Qué es | Código existente |
|---|---|---|
| `jaccard` | Jaccard de shingles de 5 tokens abstraídos | `models/graphcodebert/v2/baselines.py:45` (`jaccard_set`), `:90` (`SetSimilarity`) |
| `winnowing` | Huellas winnowing | `baselines.py:86` |
| `v2` | GraphCodeBERT v2 con DFG, mean pooling, zero-shot | `models/graphcodebert/v2/embed.py:81` (`GraphCodeBERTV2Embedder`), `baselines.py:115` (`V2FileEmbedder`) |
| `v2_nodfg` | Igual que `v2` sin DFG | `embed.py:115` (`use_dfg=False`) |
| `v2_norm` | `v2` sobre código con identificadores canónicos | **Por crear** (sección 4.2) |
| `v2_norm_nodfg` (opcional) | `v2_nodfg` sobre código canónico | **Por crear** |

Todos los embeddings pasan por la caché existente (`models/graphcodebert/v2/cache.py:78`
`EmbeddingCache`, `:119` `CachedEmbedder`), cuya llave incluye el sha256 del contenido. El código
canónico tiene otro contenido y por eso genera entradas nuevas; no hay que invalidar nada.

---

## 3. Evaluaciones

### E1. ¿Los embeddings agrupan por lógica? (principal)

**Etiqueta:** la tarea (`assignment`). Dos soluciones de la misma tarea resuelven el mismo problema,
así que se consideran "misma lógica".

**Muestra:**
- Solo entradas humanas, con `excluded == False`.
- Un archivo por `dup_group`, para que los duplicados exactos no inflen el resultado.
- Hasta **60 archivos por tarea** (muestreo aleatorio con semilla 42) en las 89 tareas: unos 5,000
  archivos. Así la matriz completa de similitud (~25 millones de pares) cabe en memoria y el cálculo de
  embeddings termina en horas, no en días.
- Antes de ejecutar, **verificar si la misma tarea en dos años** (por ejemplo `A2016/Z1/Z1` y
  `A2017/Z1/Z1`) es el mismo problema. El split se construyó "agrupando por tarea con años
  combinados": usar la misma agrupación que el campo `blocks` de `split_v1`. Si son el mismo problema,
  la etiqueta es la tarea sin el año; si no, la tarea con el año.

**Métricas (en el espacio original, nunca en 2D):**
- **MAP@R** con la etiqueta de tarea: `models/evaluation/metrics.py:257` (`map_at_r`), y el IC95 con
  `models/graphcodebert/v2/pairs.py:240` (`map_at_r_ci`). El bootstrap remuestrea **tareas**, no
  archivos.
- **Recall@1:** ¿el vecino más cercano de cada archivo es de la misma tarea?
- **ROC-AUC** de pares "misma tarea vs. distinta tarea", dentro del mismo curso (`metrics.py:71`).
- **Silhouette** con distancia coseno (`sklearn.metrics.silhouette_score`, `metric="cosine"`).
- **Diferencias pareadas** entre métodos (`v2_norm − v2`, `v2 − jaccard`) con
  `models/evaluation/metrics.py:356` (`bootstrap_many`), usando los mismos remuestreos.
- **Línea base aleatoria:** MAP@R esperado con similitudes aleatorias (se calcula permutando la matriz).

**Advertencia de interpretación:** dos tareas distintas pueden compartir lógica (por ejemplo, dos
ejercicios simples de ciclos). Eso baja el MAP@R aunque el modelo funcione bien. Se reporta una
**matriz de confusión entre tareas** (a qué tarea pertenece el vecino más cercano cuando falla) para
distinguir "el modelo se equivoca" de "las tareas se parecen".

### E2. ¿Parecerse a una correcta indica corrección? (secundaria)

**Datos:** entregas de A2016 con `last_test_results` válido (`X/Y` con `Y > 0`).
- `pasa` = `X == Y`; `pass_rate` = `X / Y`.
- Se descartan `""` y `0/0`, porque no se distingue "no probado" de "no compiló".
- Se incluyen solo las tareas con **al menos 5 entregas que pasan y 3 que no**.

**Referencia (aproximación a la solución del profesor):** como no hay solución oficial, por cada tarea
se toma como referencia una entrega que pasa todas las pruebas (**dejando una fuera**):
1. Para cada entrega `r` que pasa, se usa `r` como referencia y se calcula la similitud de `r` con
   todas las demás entregas de la tarea.
2. Se calcula el AUC (pasa vs. no pasa) y el Spearman (similitud vs. `pass_rate`).
3. Se promedia sobre todas las referencias posibles de la tarea; así el resultado no depende de una
   sola referencia.

**Agregación:** promedio por tarea (macro), con IC95 por bootstrap sobre tareas.

**Limitaciones que se escriben en la tesis:**
- La referencia es una solución de alumno, no la del profesor.
- La muestra es pequeña (~630 entregas) y está sesgada: ~76% aprueba.
- `last_test_results` es la última corrida de pruebas y puede no corresponder a la versión final.
- Un error de compilación puede aparecer como `0/Y`.

---

## 4. Implementación

### 4.1 Archivos

| Archivo | Contenido |
|---|---|
| `models/logic_eval/__init__.py` | Paquete |
| `models/logic_eval/data.py` | Carga de la muestra de E1 (desde `split_v1`) y de E2 (unión con `data/raw/stats`) |
| `models/logic_eval/canonical.py` | Normalización de identificadores (4.2) |
| `models/logic_eval/grouping.py` | Métricas de E1: MAP@R, Recall@1, AUC, silhouette, confusión entre tareas |
| `models/logic_eval/correctness.py` | Métricas de E2: referencia dejando una fuera, AUC, Spearman |
| `models/logic_eval/plots.py` | Gráficas (sección 5) |
| `scripts/logic_grouping_eval.py` | CLI que ejecuta todo y escribe la corrida |
| `tests/test_logic_eval_canonical.py`, `tests/test_logic_eval_metrics.py` | Pruebas (4.3) |

**Reutilizar:**
- `models/evaluation/report.py` (`RunContext`): carpeta de corrida con config, sha del split, git sha y semilla.
- `models/graphcodebert/v2/evaluate.py:147` (`load_files`) y `:184` (`load_embedders`): carga de archivos y modelos.
- `models/graphcodebert/v2/pairs.py:178` (`embedding_similarity`): matriz coseno.

### 4.2 Normalización de identificadores (`canonical.py`)

Renombrar cada identificador **definido por el alumno** con un nombre canónico, en orden de primera
aparición: variables `v1, v2, …`, funciones `f1, f2, …`, tipos propios `t1, t2, …`.

- Partir de `models/robustness/transforms.py:112` (`t1_rename_identifiers`), que ya sabe qué
  identificadores renombrar y respeta los ámbitos, pero cambiar la asignación de nombres: debe ser
  **determinista por orden de aparición, no aleatoria**.
- **No renombrar:** `main`, palabras reservadas, funciones y tipos de la biblioteca estándar (`printf`,
  `scanf`, `std::vector`, `size_t`…), campos de structs externos ni macros del sistema.
- Si el archivo tiene errores de parseo, renombrar solo fuera de los nodos `ERROR`, igual que las
  transformaciones del experimento de robustez.

### 4.3 Pruebas primero (RED → GREEN)

- **Determinismo:** el mismo código produce siempre el mismo resultado.
- **Invarianza:** dos programas que solo difieren en nombres producen **exactamente** el mismo código canónico.
- **Lo que no se renombra:** `printf`, `main` y las palabras reservadas no cambian.
- **Ámbitos:** una variable `i` en dos funciones distintas recibe nombres consistentes con su ámbito.
- **Sintaxis:** el código canónico sigue parseando sin nodos `ERROR` nuevos (`models/robustness/validity.py:11`).
- **Métricas con valores conocidos:** grupos perfectamente separados dan MAP@R = 1, y similitudes aleatorias se acercan a la línea base.
- **Unión con `last_test_results`:** sobre un fixture pequeño, las llaves se unen bien y `""`/`0/0` se descartan.

### 4.4 CLI

```bash
python scripts/logic_grouping_eval.py \
    --split data/splits/split_v1.json.gz \
    --methods jaccard,winnowing,v2,v2_nodfg,v2_norm \
    --per-assignment 60 --seed 42 --n-boot 1000 \
    --out runs/logic_eval
```

`--smoke` ejecuta con 5 tareas y 10 archivos por tarea para medir el tiempo antes de la corrida completa.

### 4.5 Salida: `runs/logic_eval/<timestamp>/`

```
config.json            # métodos, semilla, muestra, sha del split, git sha
sample.json            # ids de archivos usados en E1 y E2
e1_metrics.json        # MAP@R, Recall@1, AUC, silhouette por método, con IC95
e1_contrasts.json      # diferencias pareadas entre métodos
e1_confusion.json      # confusión entre tareas
e2_metrics.json        # AUC y Spearman por tarea y agregados
report.md              # resumen legible
plots/                 # sección 5
```

---

## 5. Gráficas

Las gráficas **ilustran**; las conclusiones salen de las métricas de la sección 3, calculadas en el
espacio original.

### G1. Mapa de calor de similitud ordenado por tarea (la más honesta)

- Se ordenan los archivos por tarea y se dibuja la matriz de similitud coseno.
- Si el modelo agrupa por lógica, aparecen **bloques claros en la diagonal**: alta similitud dentro de
  cada tarea y baja entre tareas.
- Un panel por método (`jaccard`, `v2`, `v2_norm`), con la misma escala de color.
- No reduce dimensión, así que no distorsiona nada. Usar 8–10 tareas con ~30 archivos cada una para
  que sea legible.

### G2. Proyección 2D de los embeddings (la que pediste)

Muestra visualmente cómo se agrupan las soluciones de una misma lógica y cómo las de otro problema
caen en otra zona.

- **Selección:** 6–8 tareas, ~40 soluciones cada una, eligiendo a propósito:
  - tareas **muy distintas** (por ejemplo, una de cadenas y una de matrices), que deberían quedar en clusters separados;
  - y **dos tareas parecidas** (por ejemplo, dos de ciclos simples), para mostrar honestamente dónde se mezclan.
- **Color por tarea**, y una **estrella** por tarea para la entrega usada como referencia en E2.
- **Paneles lado a lado:** `v2` contra `v2_norm`, para ver si normalizar los nombres compacta los clusters.
- **Técnica:**
  - **t-SNE** (`sklearn.manifold.TSNE`, ya instalado): `metric="cosine"`, `perplexity=30`, `init="pca"`, semilla fija.
  - **UMAP** opcional (`pip install umap-learn`; hoy no está instalado): `metric="cosine"`, `n_neighbors=15`, `min_dist=0.1`. Suele conservar mejor la estructura global.
  - **Para Jaccard**, que no genera vectores: t-SNE con `metric="precomputed"` sobre la distancia `1 − Jaccard`.
- **Estabilidad:** repetir con 3 semillas y mostrar que los clusters se mantienen; si cambian mucho,
  decirlo.
- **Nota obligatoria en el pie de figura:** "La proyección 2D distorsiona distancias; las distancias
  entre clusters no son interpretables. Las conclusiones se basan en MAP@R y silhouette calculados en
  el espacio original."

### G3. Barras de MAP@R por método

- MAP@R con IC95 para cada método, con una línea horizontal en el valor aleatorio.
- Es la figura principal de resultados.

### G4. Similitud con la referencia según el resultado de las pruebas (E2)

- Por tarea, un diagrama de caja o de puntos de la similitud con la referencia, separado en **pasa todo / parcial / falla todo**.
- Si E2-H1 se cumple, "pasa todo" queda más arriba.

### G5. Vista del docente (ilustrativa)

- Para una tarea, la lista de entregas ordenada por similitud con la referencia, coloreada por el resultado de las pruebas.
- Muestra cómo usaría el docente la información: revisar primero las más alejadas.
- Es útil para la presentación de la tesis.

---

## 6. Ejecución

Desde la raíz del repositorio:

```powershell
python -m pytest tests/test_logic_eval_canonical.py tests/test_logic_eval_metrics.py -q
python scripts/logic_grouping_eval.py --smoke --out runs/logic_eval_smoke
Start-Process python -ArgumentList "-u","scripts/logic_grouping_eval.py","--per-assignment","60","--out","runs/logic_eval" -RedirectStandardOutput logic_eval.log -NoNewWindow
```

```bash
python -m pytest tests/test_logic_eval_canonical.py tests/test_logic_eval_metrics.py -q
python scripts/logic_grouping_eval.py --smoke --out runs/logic_eval_smoke
nohup python -u scripts/logic_grouping_eval.py --per-assignment 60 --out runs/logic_eval > logic_eval.log 2>&1 &
```

- **GPU:** RTX 2060 SUPER 8 GB; calcular los embeddings es la parte lenta. Medir el tiempo con
  `--smoke` y extrapolar.
- **Reanudar:** la caché de embeddings conserva lo ya calculado; al reejecutar se reutiliza.
- **Por verificar:** si la corrida de robustez (`runs/robustness/20261012-050941`) guardó los
  embeddings de test en la misma caché (su `config.json` no registra la ruta de caché). Si es así, se
  reutilizan automáticamente; si no, se recalculan.

---

## 7. Interpretación de resultados

| Resultado | Qué significa | Para la tesis |
|---|---|---|
| `v2` agrupa bien (MAP@R alto) y `v2_norm` mejora | Los embeddings capturan la lógica, pero dependían de los nombres | Usar `v2_norm` en la plataforma; el entrenamiento queda como mejora futura |
| `v2` agrupa bien, pero Jaccard igual o mejor | La lógica de estas tareas se refleja en la forma del código | Jaccard es suficiente para estas tareas; los embeddings valen si se entrenan |
| Ninguno agrupa bien | Las tareas se parecen entre sí o los modelos no capturan lógica | Revisar la confusión entre tareas; el entrenamiento contrastivo queda plenamente justificado |
| E2-H1 se cumple | Parecerse a una solución correcta indica corrección | Respalda el uso de la similitud para priorizar la revisión |
| E2-H1 no se cumple | Similitud ≠ corrección en este dataset | La similitud orienta, pero no sustituye las pruebas; limitación explícita |

---

## 8. En la tesis

- **Dónde:** en la sección de resultados del Canal A en `Documentacion/Documento/capitulos/modelado.tex`,
  después de la subsección de robustez.
- **Contenido:**
  - tabla de E1 (MAP@R, Recall@1, AUC y silhouette por método, con IC95);
  - G1 y G2 como figuras ilustrativas y G3 como figura principal;
  - E2 con G4 y sus limitaciones;
  - G5 en la presentación o el capítulo de la plataforma.
- **Mensaje:** la similitud es información para el docente, no un veredicto. La evaluación mide hasta
  qué punto esa información refleja la lógica y la corrección.

---

## 9. Lista de verificación

- [ ] Verificar la agrupación de tareas entre años (`blocks` de `split_v1`).
- [ ] Escribir las pruebas de `canonical.py` y de las métricas (RED).
- [ ] Implementar `canonical.py`, `data.py`, `grouping.py`, `correctness.py` y `plots.py` (GREEN).
- [ ] Ejecutar `--smoke` y medir el tiempo.
- [ ] Ejecutar la corrida completa.
- [ ] Revisar la estabilidad de G2 con 3 semillas.
- [ ] Escribir `report.md` con los veredictos de las hipótesis tal como se pre-registraron.
- [ ] Actualizar `modelado.tex`.
