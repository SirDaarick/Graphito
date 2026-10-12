# Guía de Implementación: Experimento de Robustez del Canal A ante Ofuscación Estructural

> **Estado:** planificado, no ejecutado. Esta guía es el pre-registro del experimento: las hipótesis, el criterio de decisión y el análisis quedan fijados aquí **antes** de mirar un solo resultado sobre `test`.
> **Alcance:** sin reentrenamiento. Solo se transforman archivos y se vuelven a puntuar con los métodos ya existentes.
> **Corrida de referencia:** `runs/graphcodebert/20261011-082155` (zero-shot sobre `split_v1`, `n_boot=1000`, `seed=42`).

---

## 0. Contexto

El Canal A decide hoy con un Jaccard léxico: shingles de 5 tokens sobre un flujo de tokens abstraído (`ID`, `NUM`, `STR`, `CHR`, palabras clave intactas), calibración isotónica ajustada en `val` y umbral `fpr_0.05` (`models/deploy/manifest.json:14-33`). En `test` de `split_v1`, vista `all` (`runs/graphcodebert/20261011-082155/summary.json`):

| Método | ROC-AUC [IC95] | MAP@R |
|---|---|---|
| `jaccard` | 0.945 [0.930, 0.964] | 0.374 |
| `winnowing` | 0.944 [0.930, 0.962] | 0.385 |
| `v2` (DFG, mean) | 0.856 [0.796, 0.893] | 0.295 |
| `v2_nodfg` (mean) | 0.851 [0.788, 0.889] | 0.291 |
| `legacy` | 0.740 [0.653, 0.800] | 0.168 |

Datos de `test`: 6797 archivos, 14 tareas, 1 908 545 pares, **338 positivos** (`runs/graphcodebert/20261011-082155/report.md:30`).

**Pregunta:** ¿la ventaja de Jaccard se debe a que el plagio del dataset es copia léxica? Si es así, una ofuscación estructural que preserva la semántica debería degradar a Jaccard más que a GraphCodeBERT. El resultado decide si se justifica la Fase 2 (fine-tuning contrastivo de GraphCodeBERT) y aporta un hallazgo a la tesis en cualquier caso.

---

## 1. Objetivo e hipótesis (pre-registro)

**Objetivo:** medir la degradación de cada método del Canal A cuando el lado transformado de cada par se ofusca con transformaciones que preservan la semántica, sin reajustar nada.

**Variable primaria:** ROC-AUC, vista `all`, condición `T7@1.0` (combinada, intensidad máxima). Las demás condiciones y métricas son secundarias o exploratorias.

**Estadístico de contraste** (diferencia de diferencias, misma remuestra bootstrap):

```
DiD(Tk; A, B) = [AUC_A(Tk) - AUC_A(T0)] - [AUC_B(Tk) - AUC_B(T0)]
```

| Hipótesis | Enunciado | Se confirma si | Se refuta si |
|---|---|---|---|
| **H1** | Bajo transformaciones estructurales, la ROC-AUC de `jaccard` cae más que la de `v2`. | `DiD(T7@1.0; jaccard, v2)` < 0 y su IC95 excluye 0. | El IC95 excluye 0 con signo opuesto (`v2` cae más). Si el IC contiene 0: **no concluyente**. |
| **H2** | El renombrado de identificadores (T1) apenas afecta a `jaccard`; funciona como **control**. | `ΔAUC_jaccard(T1)` = 0 exactamente (los identificadores ya se abstraen a `ID` en `models/evaluation/normalize.py:89-104`). Lo mismo para `winnowing`. | Cualquier Δ distinto de 0 indica un **error de implementación** (p. ej., renombrar a una palabra clave o a un nombre de biblioteca), no un hallazgo. Se corrige y se repite. |
| **H3** | El DFG ayuda más bajo reordenamiento que sin él. | `DiD(T3; v2_nodfg, v2)` < 0 con IC95 que excluye 0 (`v2_nodfg` cae más que `v2`). | IC95 que excluye 0 con signo opuesto. Si contiene 0: el DFG no aporta robustez medible. |

Reglas adicionales fijadas de antemano:

- Las condiciones secundarias (T1–T6, T7@0.25, T7@0.5) se reportan todas, sin seleccionar las favorables. Se presentan como exploratorias; si se desea un criterio formal, se aplica Holm sobre los 9 contrastes H1 por condición.
- Para `v2` bajo T1 no se fija hipótesis: se reporta como dato (el modelo sí ve los nombres).
- El bootstrap es por tarea (14 unidades en `test`), así que los IC serán anchos. Se acepta de antemano que un resultado "no concluyente" es un resultado válido.

---

## 2. Datos y reglas contra fuga de información

1. **Solo pares de `test` de `split_v1`**, construidos con `EvalPairs.from_manifest(manifest, "test")` (`models/graphcodebert/v2/pairs.py:141-150`). Por defecto `SplitManifest.plagiarism_pairs` excluye los pares con entradas `ambiguous` y `unlabeled` (`models/evaluation/manifest.py:216-257`); la etiqueta proviene de los clústeres de `data/raw/ground-truth-anon.txt` ya volcados en el manifiesto. No usar `include_ambiguous=True`.
2. **Desarrollo y depuración solo con `train`/`val`.** Las pruebas unitarias usan fragmentos sintéticos; las corridas de humo usan `--split val`. `test` se puntúa **una sola vez**, con la configuración congelada (la misma regla que aplica `Evaluation.evaluate_test`, `models/graphcodebert/v2/evaluate.py:487-492`).
3. **Nunca recalibrar ni reelegir umbrales** con datos transformados. Se reutilizan:
   - `jaccard`: la calibración desplegada `models/deploy/channel_a/calibration.json` (isotónica en `val`, umbral calibrado `0.000588`, equivalente a Jaccard bruto ≈ 0.667) mediante `load_calibration(...).decide(raw)` (`models/evaluation/calibration.py:475-483`).
   - Los demás métodos: los umbrales brutos `fpr_0.05` de `runs/graphcodebert/20261011-082155/thresholds_val.json` (p. ej. `v2` = 0.99786, `winnowing` = 0.62229), convertidos con `operating_points` (`models/graphcodebert/v2/evaluate.py:237-253`). El pooling también se fija desde `selection.json` (`mean` para `v2` y `v2_nodfg`).
4. **Transformar el MISMO lado de TODOS los pares, positivos y negativos.** Este punto es crítico:
   - Si solo se transformara el lado copiado de los pares positivos, el clasificador podría separar las clases por "uno de los dos archivos fue transformado" en vez de por similitud. La degradación medida estaría contaminada por un artefacto del diseño, no por la robustez del método.
   - Regla adoptada: para cada par `(a, b)` con `a < b` (índices de `PairSet`), la puntuación es `sim(original_a, T(b))`. Todo par, positivo o negativo, compara un original contra un transformado. Así, lo único que cambia entre T0 y Tk es la ofuscación, igual para ambas clases.
   - Implementación: por tarea se calcula la matriz cruzada `C[i, j] = sim(orig_i, T_j)`. `score_pairs` (`pairs.py:205-237`) toma `sim[a - start, b - start]` con `a < b`, por lo que recibe exactamente `sim(orig_a, T(b))` sin modificar `score_pairs`. `M.map_at_r` (`models/evaluation/metrics.py:257-293`) acepta matrices no simétricas: cada consulta es un original y los candidatos son transformados.
   - Análisis de sensibilidad (secundario): `0.5 * (C[a, b] + C[b, a])`.
5. **Semillas fijas:** `--seed 42` para el bootstrap (igual que la corrida de referencia) y una semilla de transformación derivada por archivo y condición: `int(sha256(f"{seed}:{file_sha256}:{transform}:{intensity}").hexdigest()[:16], 16)`. No usar `hash()` de Python (está aleatorizado por proceso).

---

## 3. Catálogo de transformaciones

Todas se implementan sobre el árbol de tree-sitter (no con regex), reutilizando `parse_source` y `prepare_source` de `models/graphcodebert/v2/dfg.py:88-98` (gramáticas `tree_sitter_c` y `tree_sitter_cpp`, un parser por hilo). Patrón común:

1. `src = prepare_source(text)` (quita comentarios respetando literales; los tres métodos ignoran comentarios de todos modos).
2. Parsear, recolectar **sitios elegibles** fuera de cualquier subárbol con `ERROR` o `MISSING` (≈25 % de los archivos originales tienen errores de parseo, `report.md:31`).
3. Elegir sitios con `random.Random(semilla_derivada)` según la intensidad `p`.
4. Aplicar ediciones por rangos de bytes, de derecha a izquierda; reparsear antes de la siguiente transformación.
5. Devolver `TransformResult(code, n_eligible, n_applied)`. Si `n_eligible == 0`, el código sale **idéntico** byte a byte.

### T0 — Identidad (línea base)

- Devuelve el texto original sin tocar (ni siquiera quita comentarios), para que las incrustaciones coincidan con la caché de la corrida de referencia.
- **Compuerta de cordura:** con T0 la matriz cruzada `C` coincide con la matriz simétrica original, así que las métricas de T0 deben reproducir exactamente `summary.json` de la corrida de referencia (p. ej. `jaccard` ROC-AUC 0.9446, `v2` 0.8559, vista `all`). Si no coinciden, hay un error en la canalización y no se continúa.

### T1 — Renombrado de identificadores (control)

```c
int suma(int n) { int acc = 0; for (int i = 0; i < n; i++) acc += i; return acc; }
/* -> */
int f_1(int v_1) { int v_2 = 0; for (int v_3 = 0; v_3 < v_1; v_3++) v_2 += v_3; return v_2; }
```

- Renombra solo símbolos **declarados en el archivo**: variables locales, parámetros y funciones propias (excepto `main`). Fuentes: `declarator` dentro de `declaration`, `parameter_declaration`, `function_declarator`.
- No renombrar: campos de `struct`/`class` (`field_identifier`), macros (`#define`), nombres de biblioteca (`printf`, `std::vector`), identificadores en `using`/`namespace`, plantillas.
- Nombres nuevos con prefijo fijo y contador; verificar que no colisionen con ningún identificador existente ni con `KEYWORDS` (`normalize.py:12-23`).
- Respetar ámbitos: una tabla de símbolos por `compound_statement`; ante sombreado ambiguo, omitir ese símbolo.

### T2 — Conversión `for` ↔ `while`

```c
for (int i = 0; i < n; i++) { s += a[i]; }
/* -> */
{ int i = 0; while (i < n) { s += a[i]; i++; } }

while (x > 0) x /= 2;
/* -> */
for (; x > 0; ) x /= 2;
```

- `for → while`: envolver en `{ }` para conservar el ámbito del inicializador; condición vacía → `while (1)`; cuerpo sin llaves → agregarlas.
- **Inelegible** si el cuerpo contiene un `continue` que pertenezca a este bucle (saltaría la actualización). Un `continue` dentro de un bucle anidado no cuenta.
- `while → for` siempre es seguro. `do … while` no se toca.

### T3 — Reordenamiento de sentencias y declaraciones independientes

```c
int a = 0;
int b = 5;
c = b * 2;
/* -> */
int b = 5;
int a = 0;
c = b * 2;
```

- Solo intercambios de sentencias **adyacentes** del mismo `compound_statement`, ambas `declaration` o `expression_statement`.
- Calcular conjuntos lectura/escritura por sentencia a partir de los identificadores del árbol (la misma lógica de definición-uso del walker de `dfg.py`, `_Walker` en `dfg.py:140`; se recomienda una función propia `_read_write_sets(node)` porque el DFG trabaja por índice de token, no por sentencia).
- Intercambiar `S1, S2` solo si `W1 ∩ (R2 ∪ W2) = ∅` y `W2 ∩ R1 = ∅`.
- **Inelegible:** cualquier llamada a función (E/S como `printf`/`scanf`/`cin` fija el orden), punteros o arreglos escritos a través de `*p`, `p->x`, `a[i]` (alias posible), `return`, `break`, etiquetas, `goto`, sentencias de control y declaraciones que usan una variable declarada en la otra.
- En C89 estricto las declaraciones deben preceder a las sentencias: no mover una declaración debajo de una sentencia.

### T4 — Operadores equivalentes

| Forma original | Alternativas |
|---|---|
| `x = x + 1;` | `x += 1;` / `x++;` / `++x;` |
| `x = x - 1;` | `x -= 1;` / `x--;` |
| `x = x op e;` (`+ - * / % & \| ^ << >>`) | `x op= e;` (y viceversa) |
| `i++` como sentencia o actualización de `for` | `++i` / `i += 1` |
| `a[i]` | `*(a + i)` (opcional, solo C con arreglos/punteros) |

- Solo cuando `x` es un identificador simple (no `a[f()]` ni `*p++`: la reevaluación del lado izquierdo cambiaría la semántica).
- `x++` ↔ `++x` solo cuando el valor de la expresión se descarta (sentencia o actualización de `for`).
- `x = x op e` → `x op= e` solo si `x` no aparece en `e` con efectos laterales y el operador es el de nivel superior del lado derecho (respetar precedencia: `x = x * a + b` no es `x *= a + b`).

### T5 — Inserción de código muerto o no-ops

```c
int r = n * 2;
/* -> */
int r = n * 2;
if (0) { r = r - 1; }
```

- Plantillas fijas y compatibles con C y C++: `if (0) { <sentencia benigna> }`, `(void)0;`, `{ int __g1 = 0; (void)__g1; }`.
- Insertar solo entre sentencias de un `compound_statement` de cuerpo de función o de bucle, nunca antes de declaraciones en código C89.
- La sentencia benigna dentro de `if (0)` puede reutilizar una variable visible para que el ruido sea plausible; nunca declarar nombres que colisionen.
- Advertencia: T5 agrega tokens, por lo que también diluye la unión del Jaccard; se reporta la magnitud de edición para interpretarlo.

### T6 — Inversión de ramas `if`/`else`

```c
if (x > 0) { pos++; } else { neg++; }
/* -> */
if (!(x > 0)) { neg++; } else { pos++; }
```

- Solo `if` con `else_clause`. Envolver la condición entre paréntesis antes de negar.
- `else if`: la rama `else` contiene otro `if_statement`; al intercambiar, envolverla en `{ }`.
- Inelegible si hay directivas de preprocesador entre las ramas.

### T7 — Combinada (T2 + T3 + T4 + T5) por intensidad

- Orden fijo: T2 → T3 → T4 → T5, reparseando entre pasos.
- Intensidad `p ∈ {0.25, 0.5, 1.0}`: fracción de sitios elegibles de **cada** transformación que se aplica, elegidos con la semilla derivada.
- T1 y T6 quedan fuera de T7 a propósito: T1 es el control, y T6 se evalúa por separado.

### Opcionales o difíciles (fuera del alcance mínimo)

| Transformación | Motivo |
|---|---|
| Extracción de función (*function extraction*) | Requiere análisis de variables libres, punteros para salidas y prototipos; alto riesgo de romper la compilación. **Opcional.** |
| `switch` ↔ cadena `if/else` | `fallthrough` y `break` complican la equivalencia. **Opcional.** |
| Inlining de funciones | Recursión y efectos laterales. **Difícil.** |
| Reordenar funciones del archivo | Requiere prototipos en C; afecta poco a los métodos por ventanas. **Opcional.** |

---

## 4. Verificación de validez

Para cada archivo transformado y cada condición:

1. **Parseo:** reparsear con tree-sitter. Se rechaza si el número de nodos `ERROR`/`MISSING` es mayor que en el original (no se exige 0, porque el 25 % de los originales ya tiene errores).
2. **Compilación** (si hay compilador): `gcc -fsyntax-only -x c` o `g++ -fsyntax-only -x c++` según `Sample.lang`, con timeout de 10 s. Se rechaza si el original compilaba y el transformado no. En esta máquina hay `gcc`/`g++` de MSYS2 (`C:\msys64\ucrt64\bin`). Sin compilador, se registra `compile_ok = null` y el criterio queda solo en el parseo.
3. **Registro por archivo** en `transforms.jsonl`: `id`, `condition`, `sha256_in`, `sha256_out`, `n_eligible`, `n_applied`, `parse_ok`, `compile_ok`, `edit_tokens` (distancia de Levenshtein entre `tokenize(orig)` y `tokenize(T)` normalizada por la longitud original, `normalize.py:74-76`) y `edit_abstract` (lo mismo sobre `shingle_tokens`).
4. **Tasa de éxito por transformación:** archivos con `n_applied > 0`, rechazados por parseo y rechazados por compilación.
5. **Descarte consistente:** si `T(b)` falla la validación, el par se descarta en esa condición **para todos los métodos**, y T0 se recalcula sobre la misma máscara de pares para que los Δ sean pareados. Los archivos sin sitios elegibles se conservan sin cambios y se cuentan aparte (`n_applied = 0`).
6. **Equivalencia de comportamiento:** el dataset no trae entradas ni salidas de prueba (`data/raw/readme.txt` solo describe `src`, `stats` con `last_test_results` y la verdad de referencia), así que **no está disponible** sobre el corpus. Como sustituto parcial, las pruebas unitarias compilan y ejecutan fragmentos pequeños con `gcc` antes y después de cada transformación y comparan la salida estándar (sección 6).

---

## 5. Métodos y métricas

**Métodos:** `jaccard`, `winnowing`, `v2`, `v2_nodfg` y, opcionalmente, `legacy`. Se reutilizan tal cual:

- Léxicos: `jaccard_set`, `winnowing_set` (`models/graphcodebert/v2/baselines.py:45-87`, k = 5, w = 4).
- Incrustaciones: `load_embedders` (`evaluate.py:184-221`) → `V2FileEmbedder` con `use_dfg=True/False` (`baselines.py:115-152`) sobre `GraphCodeBERTV2Embedder.from_pretrained` (`models/graphcodebert/v2/embed.py:96-113`), envuelto en `CachedEmbedder` (`models/graphcodebert/v2/cache.py:119-143`).
- Configuración de ventanas por defecto `GCBV2Config()` (`models/graphcodebert/v2/config.py:23-37`): `code_length=384`, `data_flow_length=128`, `max_windows=16` (ventana de 382 subtokens, paso 191), fp32, atención `eager`. No cambiar nada: la clave de caché depende de estos campos.
- Requisito: `microsoft/graphcodebert-base` en la caché local de Hugging Face y `--local-files-only` (si falta, `load_embedders` rechaza la corrida, `evaluate.py:198-199`).

**Similitudes cruzadas (a crear):**

- `CrossSetSimilarity(orig_sets, trans_sets)`: igual que `SetSimilarity` (`baselines.py:90-109`) pero con dos matrices de incidencia, `inter = inc_o @ inc_t.T`.
- `cross_embedding_similarity(E_orig, E_trans)`: coseno `unit_o @ unit_t.T`, análogo a `embedding_similarity` (`pairs.py:178-188`).

**Métricas por método y condición** (vistas `all` y `no_identical`; la primaria es `all`):

1. ROC-AUC, PR-AUC y MAP@R con IC95 bootstrap por tarea, reutilizando `compute_metrics` (`models/evaluation/report.py:109-126`, `bootstrap_groups=assignment`) y `map_at_r_ci` (`pairs.py:240-284`), igual que `view_metrics` (`evaluate.py:256-268`).
2. **Δ contra T0** y **bootstrap pareado entre métodos** con las mismas remuestras: `bootstrap_many` (`models/evaluation/metrics.py:356-439`) acepta `s` bidimensional, porque indexa `s[idx]`. Se apilan las columnas y se definen las funciones sobre ellas:

   ```python
   S = np.column_stack([s_jac_T0, s_jac_Tk, s_v2_T0, s_v2_Tk])
   fns = {
       "delta_jaccard": lambda y, s: M.roc_auc(y, s[:, 1]) - M.roc_auc(y, s[:, 0]),
       "delta_v2":      lambda y, s: M.roc_auc(y, s[:, 3]) - M.roc_auc(y, s[:, 2]),
       "did_jac_v2":    lambda y, s: (M.roc_auc(y, s[:, 1]) - M.roc_auc(y, s[:, 0]))
                                     - (M.roc_auc(y, s[:, 3]) - M.roc_auc(y, s[:, 2])),
   }
   out = M.bootstrap_many(fns, y, S, n_boot=1000, seed=42, groups=assignment)
   ```

   Una sola llamada con varias funciones garantiza remuestras idénticas para todas.
3. **TPR/FPR en el umbral desplegado:** `jaccard` con `load_calibration("models/deploy/channel_a/calibration.json").decide(raw)`; el resto con los umbrales `fpr_0.05` de `thresholds_val.json` pasados como `operating_points` a `compute_metrics`.
4. **Distribución de la caída en positivos:** para cada par positivo, `s_T0 − s_Tk` por método (histograma o violín, mediana y p90) y la fracción de positivos que cruzan el umbral desplegado hacia abajo.
5. **Auto-similitud (secundaria):** la diagonal `sim(orig_i, T_i)` por método, que mide cuánto "se reconoce" un archivo a sí mismo tras la ofuscación.

**Costo del bootstrap:** el log de `evaluate.py:721-725` estima unos 1 s por remuestra por cada 1.9 M de pares y por métrica. Con 10 condiciones × 4-5 métodos, `n_boot=1000` en todo es demasiado. Política fijada: `n_boot=1000` para el contraste primario (H1 en `T7@1.0`), H2 y H3; `n_boot=200` para las condiciones exploratorias. Se registra en `config.json`.

---

## 6. Plan de implementación

Archivos (todos **a crear**):

| Archivo | Contenido |
|---|---|
| `models/robustness/__init__.py` | Paquete vacío. |
| `models/robustness/transforms.py` | `TransformResult`, `derive_seed`, `t0_identity`…`t6_invert_if`, `t7_combined(p)`, `TRANSFORMS` (registro nombre → función), `apply_condition(code, lang, condition, seed)`. |
| `models/robustness/validity.py` | `count_error_nodes`, `syntax_check(code, lang)` (gcc/g++ opcional, `shutil.which`), `token_edit_ratio`. |
| `models/robustness/scoring.py` | `CrossSetSimilarity`, `cross_embedding_similarity`, `paired_bootstrap(...)` sobre `bootstrap_many`. |
| `scripts/robustness_experiment.py` | CLI; inserta la raíz en `sys.path` como `scripts/build_deploy_artifacts.py:43-44`. |
| `tests/test_robustness_transforms.py` | Pruebas de transformaciones y validez. |
| `tests/test_robustness_scoring.py` | Pruebas de similitud cruzada y bootstrap pareado. |

### 6.1 Pruebas primero (RED → GREEN)

Convenciones existentes: pytest desde la raíz, fixtures en `tests/fixtures/`, árboles sintéticos con `make_tree` de `tests/eval_factory.py:110`, y omisión condicional con `pytest.mark.skipif(shutil.which("gcc") is None, ...)`.

Casos por transformación (parametrizados por `T1`…`T6` y `T7@{0.25,0.5,1.0}`, en C y C++):

1. **Compila:** el fragmento transformado pasa `gcc/g++ -fsyntax-only` y no tiene más nodos `ERROR` que el original.
2. **Se aplica:** con un sitio elegible, `n_applied ≥ 1` y el código cambia (p. ej. T2: aparece `while` y desaparece `for`).
3. **Semántica preservada:** programa pequeño con `main` que imprime resultados; se compila y ejecuta antes y después y la salida estándar coincide (skip sin gcc).
4. **Determinismo:** misma semilla → bytes idénticos; semilla distinta con `p < 1` → puede variar.
5. **Sin sitio elegible no hace nada:** p. ej. T2 sobre código sin bucles, T6 sobre `if` sin `else`, T3 con dos `printf` consecutivos → salida idéntica y `n_applied == 0`.

Casos específicos obligatorios:

- T1: `jaccard_set(orig)` y `jaccard_set(T1(orig))` son **iguales** (prueba de H2 a nivel unitario); `printf`, campos de `struct` y `main` no se renombran.
- T2: un `for` con `continue` no se convierte.
- T3: `a = 1; b = a;` no se intercambia; `x = 1; y = 2;` sí.
- T4: `a[i] = a[i] + 1` no se reescribe como `a[i]++` si `i` tiene efectos laterales (`a[i++]`).
- T6: `if (a) x; else if (b) y; else z;` produce código válido.
- Archivo con `ERROR` previo: no se edita dentro del subárbol erróneo.
- Similitud cruzada: `CrossSetSimilarity` con conjuntos idénticos devuelve la misma matriz que `SetSimilarity`; `cross_embedding_similarity(E, E)` es igual a `embedding_similarity(E)`.
- `paired_bootstrap` con columnas idénticas da Δ = 0 e IC [0, 0].

Comando de verificación:

```bash
pytest tests/test_robustness_transforms.py tests/test_robustness_scoring.py -v
```

### 6.2 CLI de `scripts/robustness_experiment.py`

| Argumento | Defecto | Uso |
|---|---|---|
| `--manifest` | `data/splits/split_v1.json.gz` | Manifiesto. |
| `--expected-sha256` | `e835362d…9e5238f` | Rechaza un manifiesto distinto. |
| `--split` | `val` | `test` exige además `--confirm-test`. |
| `--source-run` | `runs/graphcodebert/20261011-082155` | De dónde se leen `selection.json` y `thresholds_val.json`. |
| `--deploy-calibration` | `models/deploy/channel_a/calibration.json` | Umbral de `jaccard`. |
| `--methods` | `jaccard,winnowing,v2,v2_nodfg` | `legacy` opcional. |
| `--conditions` | `T0,T1,T2,T3,T4,T5,T6,T7@0.25,T7@0.5,T7@1.0` | Condiciones. |
| `--stage` | `all` | `transform`, `embed`, `score`, `report` o `all`. |
| `--resume` | — | Ruta de una corrida previa para continuar. |
| `--seed` / `--n-boot` / `--n-boot-secondary` | 42 / 1000 / 200 | Semillas y bootstrap. |
| `--device` / `--batch-size` | `cuda` / 16 | GPU. |
| `--cache-dir` | `runs/graphcodebert/_cache` | Reutiliza las incrustaciones de T0. |
| `--limit-assignments` | — | Depuración: primeras N tareas. |
| `--local-files-only` | activado | Sin red. |

Flujo interno: `load_manifest` → `EvalPairs.from_manifest(manifest, split)` → `load_files` (verifica sha256, `evaluate.py:147-170`) → transformar los archivos de la muestra (cada archivo necesita su versión original y su versión transformada) → validar → incrustar con `CachedEmbedder.embed(sha256_out, code, lang)` → matriz cruzada por tarea → `score_pairs` → métricas → informe.

### 6.3 Salida en `runs/robustness/<timestamp>/`

Creada con `RunContext.create("robustness", seed=..., split=..., mode="robustness", manifest_path=..., manifest_sha256=..., calibration_path=<deploy calibration>, config=..., argv=...)` (`models/evaluation/report.py:329-391`), que registra `git_sha`, `dirty`, sha del manifiesto, sha de la calibración y entorno. Estado con `set_run_status` (`models/graphcodebert/v2/runs.py:60`).

```
runs/robustness/<timestamp>/
├── config.json              # RunContext: split sha, git sha, seed, argv, condiciones, n_boot
├── transforms.jsonl         # una línea por (archivo, condición): validez y magnitud de edición
├── transform_summary.json   # tasa de éxito y edición media por condición
├── scores/<cond>__<method>.npz   # puntuaciones por par (para reanudar y reanalizar)
├── metrics.json             # por condición y método: AUC, PR-AUC, MAP@R con IC, Δ vs T0, TPR/FPR
├── contrasts.json           # DiD de H1, H2 y H3 con IC pareados
├── report.md                # tablas y veredicto pre-registrado por hipótesis
└── plots/
    ├── degradation_curve.png    # ROC-AUC vs intensidad T7 (0, 0.25, 0.5, 1.0), una línea por método con IC
    ├── delta_by_transform.png   # barras ΔROC-AUC por transformación y método
    └── positive_drop.png        # distribución de la caída en positivos
```

Los gráficos usan el patrón `Figure` + `FigureCanvasAgg` de `evaluate.py:308-326`.

---

## 7. Ejecución paso a paso

Todos los comandos desde la raíz del repositorio.

**1. Pruebas**

```powershell
pytest tests/test_robustness_transforms.py tests/test_robustness_scoring.py -v
```

**2. Humo sobre `val` con 2 tareas** (solo léxicos, minutos):

```powershell
python scripts/robustness_experiment.py --split val --limit-assignments 2 --methods jaccard,winnowing --n-boot 50
```

Revisar `transform_summary.json`: tasas de éxito de parseo/compilación razonables (> 95 %) y `n_applied > 0` en la mayoría de archivos para T2–T7.

**3. Humo con GPU sobre `val`** (cronometrar para estimar):

```powershell
python scripts/robustness_experiment.py --split val --limit-assignments 2 --methods jaccard,v2,v2_nodfg --device cuda --n-boot 50
```

**4. Congelar** la configuración (commit del código y de esta guía) antes de tocar `test`.

**5. Corrida completa sobre `test`, en segundo plano:**

PowerShell:

```powershell
Start-Process -NoNewWindow -FilePath python -ArgumentList "scripts/robustness_experiment.py","--split","test","--confirm-test","--device","cuda" -RedirectStandardError runs/robustness_test.log
```

bash:

```bash
nohup python scripts/robustness_experiment.py --split test --confirm-test --device cuda \
  2> runs/robustness_test.log &
```

**Tiempo esperado y GPU (RTX 2060 SUPER, 8 GB):**

- Transformación y validación: CPU, del orden de minutos a decenas de minutos (las llamadas a `gcc` dominan; paralelizar con `concurrent.futures.ProcessPoolExecutor`).
- Incrustaciones: es la parte lenta. Hay unos 6 800 archivos de `test` con ~4.7 ventanas de media (`report.md:31`), lo que da ~32 000 ventanas por condición y variante. 9 condiciones nuevas × 2 variantes (`v2`, `v2_nodfg`) son ~18 pasadas completas. Medir el tiempo real en el paso 3 y extrapolar; calcular **varias horas**. T0 sale de la caché existente.
- Con `--batch-size 16` y fp32 cabe en 8 GB; ante `CUDA out of memory`, bajar a 8.
- Bootstrap: CPU, del orden de horas con la política de `n_boot` de la sección 5.

**6. Reanudar tras una interrupción:**

```powershell
python scripts/robustness_experiment.py --resume runs/robustness/<timestamp> --stage all
```

- Las incrustaciones se guardan por `sha256` del código transformado en `<cache-dir>/<clave>/xx/<sha>.npz` (`cache.py:88-116`), así que una reanudación solo calcula las que faltan.
- El script debe saltar cualquier etapa cuyo artefacto ya exista (`transforms.jsonl`, `scores/*.npz`) y verificar que `config.json` coincide (mismo manifiesto, semilla y condiciones); si no coincide, rechazar.
- Las transformaciones son deterministas: regenerarlas produce los mismos `sha256_out`.

---

## 8. Guía de interpretación

| Escenario (T7@1.0) | Lectura | Implicación para la tesis | Fase 2 |
|---|---|---|---|
| `jaccard` cae mucho, `v2` se mantiene (H1 confirmada) | La ventaja de Jaccard es léxica; GraphCodeBERT captura estructura. | Jaccard es adecuado para el dataset actual pero frágil ante ofuscación; justifica un canal semántico. | **Justificada:** el fine-tuning contrastivo puede unir la exactitud de Jaccard y la robustez de `v2`. Considerar fusión Jaccard + `v2`. |
| Ambos caen de forma similar (DiD ≈ 0) | Ninguno es robusto; `v2` zero-shot no aporta invariancia estructural. | Hallazgo honesto: la representación zero-shot no basta. | **Justificada con matiz:** entrenar con pares aumentados con estas mismas transformaciones (sobre `train`). |
| Ninguno cae | Las transformaciones son demasiado débiles o el n de positivos no permite detectar efectos. | Revisar magnitud de edición; reportar como límite del experimento. | **No justificada** por este experimento; Jaccard se mantiene como decisor. |
| `v2` cae más que `jaccard` | GraphCodeBERT es más sensible a cambios superficiales que el Jaccard abstraído. | Refuerza a Jaccard como decisor del Canal A. | **No justificada** en su forma actual; replantear (otro modelo o normalización previa). |
| T1 cambia `jaccard` (≠ 0) | Error de implementación. | No reportar; corregir. | — |
| H3: `v2_nodfg` cae más que `v2` en T3 | El DFG aporta robustez al reordenamiento. | Justifica conservar el DFG en el canal. | Mantener DFG en el entrenamiento. |

---

## 9. Cómo reportarlo en la tesis

No hay un capítulo de resultados separado; el lugar es `Documentacion/Documento/capitulos/modelado.tex`, sección `\section{Evaluación y Validación Experimental}` (línea 188). Agregar una subsección nueva después de `\subsection{Evaluación del Canal Semántico ante Clones de Bellon}` (línea 316), por ejemplo `\subsection{Robustez del Canal A ante Ofuscación Estructural}`, con:

- **Tabla** `tab:robustez_canal_a`: filas = condiciones (T0…T7@1.0); columnas = ROC-AUC [IC95] de `jaccard`, `winnowing`, `v2`, `v2_nodfg`, y una columna DiD (`jaccard` − `v2`) [IC95]. Pie de tabla con tasa de éxito de transformación y número de pares retenidos.
- **Figura** `fig:robustez_degradacion`: `degradation_curve.png` (ROC-AUC vs intensidad). Opcional: `delta_by_transform.png`.
- Un párrafo con el veredicto pre-registrado de H1, H2 y H3, y la decisión sobre la Fase 2.

**Limitaciones que deben declararse:**

- La ofuscación es sintética: no reproduce el comportamiento real de un estudiante que disfraza una copia.
- Pocos positivos (338 pares en 14 tareas): IC anchos y bootstrap por tarea con solo 14 unidades.
- Sin verificación de comportamiento sobre el corpus (no hay casos de prueba); la equivalencia solo se comprueba en fragmentos unitarios y por compilación.
- La evaluación es por pares entre estudiantes, no la puntuación desplegada contra soluciones de referencia de cada problema.
- La verdad de referencia es ruidosa (clústeres por tarea; ambiguos excluidos).
- Solo se transforma un lado por par; el escenario en que ambos estudiantes ofuscan no se evalúa.

---

## 10. Lista de verificación

- [ ] Pre-registro: esta guía con H1–H3, variable primaria y política de `n_boot` está en un commit antes de puntuar `test`.
- [ ] Crear `models/robustness/{__init__,transforms,validity,scoring}.py`.
- [ ] Escribir `tests/test_robustness_transforms.py` y `tests/test_robustness_scoring.py` y observarlas fallar (RED).
- [ ] Implementar T0–T7 hasta pasar las pruebas (GREEN); refactorizar con las pruebas en verde.
- [ ] Verificar que T1 deja `jaccard_set` idéntico en las pruebas unitarias.
- [ ] Crear `scripts/robustness_experiment.py` con la CLI de la sección 6.2.
- [ ] Humo en `val` (léxicos), revisar tasas de éxito y magnitud de edición.
- [ ] Humo en `val` con GPU y cronometrar.
- [ ] Comprobar que T0 reproduce las métricas de `runs/graphcodebert/20261011-082155`.
- [ ] Congelar código y configuración (commit).
- [ ] Corrida completa sobre `test` con `--confirm-test`, en segundo plano.
- [ ] Revisar `transform_summary.json`, `metrics.json`, `contrasts.json` y `report.md`.
- [ ] Aplicar la tabla de interpretación y registrar la decisión sobre la Fase 2.
- [ ] Agregar tabla y figura a `modelado.tex` con las limitaciones.
