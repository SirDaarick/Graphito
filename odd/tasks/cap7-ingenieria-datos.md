# Plan de redacción — Cap. 7 Ingeniería de datos (`ingenieria_de_datos.tex`)

**Objetivo:** reescribir el capítulo 7 siguiendo `Documentacion/PLAN_ESTRUCTURA_TESIS.md` (sección 2, Cap. 7),
con registro formal pero accesible para lectores sin formación en IA o sistemas (incluso de ciencias
sociales), y con diagramas que hagan dinámica la lectura.

**Archivo a editar:** `Documentacion/Documento/capitulos/ingenieria_de_datos.tex` (único).

---

## 1. Diagnóstico del texto actual (qué está desactualizado)

El capítulo actual mezcla el pipeline viejo con el actual. Errores detectados contra el código:

| Afirmación actual | Realidad (verificar en código) |
|---|---|
| "conjunto balanceado 50 % humano / 50 % IA" (l. 13, 145) | 40,936 humanos vs 1,453 IA: fuertemente desbalanceado, a propósito |
| CharCNN conserva comentarios (tabla l. 316) | `models/char_cnn/v2/preprocess.py` **elimina** comentarios, cabeceras del curso y normaliza espacios (5 pasos) |
| Normalización con `indent_only.py` (l. 329–343) | v2 usa espacio canónico (`canonical_whitespace`) aplicado igual a ambas clases ("normalización simétrica") |
| Head-Tail a 4,096 caracteres (l. 367–371) | Ventanas de 4,096 con paso 2,048, máx. 8 ventanas (`models/char_cnn/v2/config.py`) |
| Vocabulario de 97 con índice 0 = UNK o relleno (l. 366) | PAD=0 y UNK=1 distintos; alfabeto = LF + ASCII imprimible (`config.py`) |
| GraphCodeBERT renombra a `VAR_0`, `FUNC_0` (l. 353) | v2 **no** renombra (por eso es sensible al renombrado, Cap. 8); quita comentarios, Tree-sitter, DFG, ventanas deslizantes de subtokens (`models/graphcodebert/v2/`) |
| Longitud máx. 512 tokens (tabla l. 320) | Ventanas deslizantes con paso de media ventana (`v2/config.py`, `windows.py`) |
| Partición "por problema" sin más detalle (l. 375–401) | `split_v1`: bloque = curso + Zx + Zy con **años combinados**; dedup exacta (`norm_hash`) global + casi exacta (Jaccard de shingles de 5 tokens ≥ 0.85, MinHash/LSH) dentro del bloque; `dup_group` nunca cruza particiones; semilla 42, test 0.20, val 0.15; sha256 registrado (`models/evaluation/splits.py`, `scripts/build_split.py`) |
| Varios generadores (GPT-4o, Claude, Gemini, Ollama…) (l. 169–170) | **Verificar** en `data/modelos.py`, `data/generar_referencias.py` y metadatos de `split_v1`; si fue un solo generador, decirlo y remitir a la limitación del Cap. 8 |
| Se cita "Textbooks Are All You Need" para justificar balance 50/50 | Quitar o reformular: ya no hay balance 50/50 |
| Cierre: "GraphCodeBERT con adaptadores LoRA" (l. 410) | Quitar LoRA; Cap. 8 usa zero-shot |
| "beneficios marginales prácticamente despreciables" (l. 292) | Suavizar a "pequeños"; no saturada en sentido estricto |
| "demuestra", "garantiza", "confirma" en varias partes | Calibrar: "sugiere", "indica", "en este dataset" |

Se conservan (con ajustes de tono): requerimientos del dataset, selección del dataset IEEE, limitaciones
(idioma, sin enunciados), ingeniería inversa de enunciados, perfiles de estudiante, ejemplo comparativo
humano vs IA, experimento de curva de aprendizaje.

## 2. Línea narrativa del capítulo

Una historia en tres actos, contada para un lector no técnico:

1. **¿De dónde salen los datos?** Necesitábamos código real de estudiantes, anterior a la IA generativa,
   y su contraparte generada por IA sobre *los mismos* problemas.
2. **¿Cómo se obtuvo la contraparte de IA sin introducir trampas?** Mismo problema, mismo idioma,
   perfiles de estudiante; ¿cuántos ejemplos bastan? → curva de aprendizaje.
3. **¿Cómo se prepararon para que la evaluación fuera justa?** Limpieza simétrica, eliminación de
   duplicados, partición sin fuga, y preparación específica para cada canal.

Cada sección abre con una frase de "para qué sirve esto" en lenguaje llano y cierra con una frase
puente hacia la siguiente. Los términos técnicos se definen la primera vez con una analogía breve
(p. ej., fuga de datos = "estudiar con las mismas preguntas del examen").

## 3. Estructura detallada

### Introducción del capítulo (≈ 2 párrafos)
- Por qué los datos determinan lo que un modelo aprende (analogía: un alumno aprende de los ejemplos que ve).
- Ubicación en Komorebi: Adquisición + Preparación. Mapa del capítulo.
- **Figura 7.1 (TikZ, existente, actualizar):** flujo general de adquisición (IEEE → enunciados →
  generación → limpieza/dedup → `split_v1`). Quitar nombres de scripts del cuerpo de las cajas
  (moverlos, si acaso, a una nota); usar lenguaje de proceso.

### 7.1 Adquisición de datos
1. **Qué necesitábamos** (requerimientos: autoría humana verificable y nivel introductorio). Conservar
   citas Lopes2017DejaVu y Zhou2023Contamination; reducir tecnicismos.
2. **El dataset base** (IEEE Programming Homework Dataset, Sarajevo): 43,771 entregas humanas,
   cursos A (C) y B (C++), 2016–2017, tareas `Zn/Zm`, estadísticas por alumno. Mantener tabla 7.1
   (verificar 43,771 y el número de problemas en `split_v1`).
3. **Limitaciones**: serbocroata, sin enunciados, sin soluciones oficiales del docente (este último
   punto falta hoy; conecta con "solución de referencia" en la evaluación offline del Cap. 8).
4. **Reconstrucción de enunciados** con LLMs (ingeniería inversa). Conservar la tabla de ejemplos.
   - **Figura nueva (TikZ):** "de varias soluciones a un enunciado": 2–3 códigos → LLM → enunciado
     (ES y SRB). Diagrama horizontal simple.
5. **Generación de la contraparte de IA**: principio "las clases difieren en el **origen**, no en el
   problema". Idioma serbocroata, perfiles de estudiante (tabla de perfiles se conserva), cuota de
   comentarios del 38 %. 1,520 archivos generados (verificar). Corregir la sección de "variedad de
   modelos" según lo verificado.
6. **Ejemplo comparativo humano vs IA**: conservar listados y tabla, pero:
   - suavizar la columna "Implicación para el modelo" (quitar "Demuestra", "Requiere invariancia
     léxica en GraphCodeBERT" — falso, v2 no es invariante a nombres);
   - quitar "enfoque bimodal" como fusión; hablar de "dos canales que miran cosas distintas".
7. **¿Cuántos ejemplos de IA bastan? (curva de aprendizaje)**: de la meta planificada (20,000) a lo
   ejecutado. Conservar el contenido ya escrito, pero:
   - abrir con la pregunta en lenguaje llano y una analogía (estudiar más ejemplos del mismo tipo
     rinde cada vez menos);
   - explicar PR-AUC en una frase intuitiva la primera vez;
   - "despreciables" → "pequeños"; "demostrando" → "lo que sugiere";
   - **Figura 7.x:** `figuras/curva_aprendizaje_charcnn.png` (existente);
   - **Figura 7.x (opcional, recomendada):** `figuras/mejora_marginal_charcnn_lc.png` para mostrar
     los rendimientos decrecientes de forma visual;
   - `figuras/panel_metricas_charcnn_lc.png`: solo si añade algo; si no, omitir para no saturar;
   - cerrar: la limitación es la **diversidad** de generadores, no el volumen (remitir a Cap. 8 y 10).

### 7.2 Preparación de datos
Abrir con: "antes de enseñar a los modelos, hay que asegurarse de que el examen sea justo".

1. **Limpieza** (mismo criterio para ambas clases): descartar stubs, archivos vacíos o rotos y
   generaciones fallidas; quitar la cabecera del curso porque **solo aparecía en código humano** (atajo).
   Explicar "atajo" (shortcut learning, cita Geirhos2020Shortcut) con un ejemplo cotidiano.
   Reemplaza la subsección actual de `indent_only.py`.
2. **Eliminación de duplicados**: exactos y casi exactos (`dup_group`). Explicar intuitivamente
   (dos entregas casi idénticas cuentan como una "familia"; una familia nunca se reparte entre
   entrenamiento y prueba). Detalle técnico (Jaccard ≥ 0.85, MinHash) en una frase o nota al pie.
3. **Partición `split_v1`**: por tarea, años combinados, sin fuga; proporciones; sha256 para
   reproducibilidad. Conservar cita Allamanis2019Adverse (calibrar "hasta en un 100 %" → verificar o
   suavizar).
   - **Figura nueva (TikZ):** esquema de partición: tareas (bloques A/Zx/Zy con 2016+2017 juntos)
     asignadas completas a entrenamiento / validación / prueba, con un "candado" o nota "prueba nunca
     se usa para decidir".
4. **Preparación para cada canal**: un párrafo puente ("cada modelo lee el código de forma distinta").
   - **Figura nueva (TikZ):** bifurcación: un archivo → (a) Canal B: texto normalizado → ventanas de
     caracteres; (b) Canal A: sin comentarios → Tree-sitter → DFG → ventanas de subtokens.
   - **CharCNN:** normalización simétrica (5 pasos en lenguaje llano), PAD ≠ UNK, ventanas de 4,096
     caracteres con traslape. Analogía: leer un documento largo por páginas superpuestas.
   - **GraphCodeBERT:** quitar comentarios, Tree-sitter (cita Brunsfeld2021Treesitter), DFG
     ("quién le pasa valor a quién"), alineación de subtokens y ventanas deslizantes. **No** afirmar
     renombrado de variables.
   - Actualizar la tabla comparativa de preprocesamiento con los valores reales.
5. **Composición final**: tabla 42,389 = 40,936 + 1,453 por partición (24,810/897, 6,808/225,
   9,318/331 — verificar contra `split_v1`). Explicar en una frase por qué el desbalance es
   intencional y realista (en un aula la mayoría del código es humano).
   - **Figura nueva (opcional, TikZ):** embudo 43,771 + 1,520 → limpieza → dedup → 42,389.

### Conclusión del capítulo
- Resumen en 1 párrafo, sin "garantiza". Puente al Cap. 8: "Modelización" (CharCNN v2 entrenado;
  GraphCodeBERT zero-shot; línea base léxica). **Sin LoRA.** Sin negritas markdown (`**`) en LaTeX.

## 4. Reglas de estilo para la redacción
- Español formal, neutro, accesible. Oraciones cortas. Definir cada término técnico la primera vez.
- "Información, no veredicto": no usar "dictamen", "culpable", "plagio confirmado".
- Afirmaciones calibradas: "sugiere", "indica", "en este dataset".
- Terminología fija del plan (Canal A / similitud semántica; Canal B / indicador estilométrico;
  línea base léxica; solución de referencia; `split_v1`).
- Nombres de scripts y rutas: fuera del texto principal salvo cuando aporten reproducibilidad
  (preferir nota al pie).
- Números solo de fuentes verificadas (`data/splits/split_v1.json.gz`, `runs/char_cnn_lc/20261014-023215`).
- Mantener labels existentes (`cap:ingenieria_datos`, `sec:adquisicion_datos`, `sec:preparacion_datos`,
  `fig:curva_aprendizaje_charcnn`, `tab:particion_corpus`, etc.) para no romper referencias cruzadas;
  verificar con grep en `Documentacion/Documento/` antes de renombrar alguno.
- Usar solo paquetes ya cargados en el preámbulo (TikZ, tabularx, listings, float). No añadir paquetes.

## 5. Tareas

- [ ] T1 Plan del capítulo (este documento) — inline
- [x] T2 Redacción del capítulo — delegado (Sonnet), un solo archivo
- [ ] T3 Revisión del resultado y verificación de números/labels — inline

## 6. Pendientes fuera de alcance
- Figura `curva_aprendizaje_charcnn.png`: "quitar el cuadro que tapa la curva" requiere regenerar la
  figura con `scripts/learning_curve_charcnn.py` (no es un cambio del `.tex`).
- Compilación del PDF (verificar en el entorno LaTeX del usuario).

## 7. Notas de verificación (T2)
- Verificado contra `data/splits/split_v1.json.gz`: 43,771 humanos y 1,520 IA; excluidos 2,835 humanos y 67 IA (236 por `cross_split_dup`: 224 + 12); finales 40,936 + 1,453 = 42,389; por partición 24,810/897, 6,808/225, 9,318/331; 89 tareas por cohorte y 48 bloques (años combinados; 30 train / 8 val / 10 test); 874 grupos IA en train; umbral 0.85, shingles de 5, semilla 42, sha256.
- Generadores reales (IA finales): deepseek-chat 1,021, qwen3 424, otros 5 modelos 8 (no los del texto antiguo). Perfiles: 6 (no 4); con comentarios suman 433/1,453 (~30 %).
- Preprocesamiento verificado en `models/char_cnn/v2/{preprocess,config}.py` (5 pasos, PAD=0/UNK=1, ventana 4096, paso 2048, máx. 8; sangría y líneas vacías se eliminan) y `models/graphcodebert/v2/{config,windows,dfg}.py` (sin renombrado; ventana 382 subtokens, paso 191, máx. 16; 384+128 posiciones). Curva de aprendizaje coincide con `runs/char_cnn_lc/20261014-023215/report.md`.
- Muestra de 3,000 archivos humanos: ~50 % con marca de curso vs ~0.3 % en IA (aproximado; el texto dice "cerca de la mitad").
- Cambios frente al plan: se retiró "72 problemas" (split: 89 tareas/48 bloques); se retiró la cita Gunasekar2023Textbooks y el "hasta 100 %" de Allamanis; se añadió el solapamiento de estudiantes entre particiones y la concentración de generadores (>99 % en dos).
- TODO verificar: "entre 100 y 150 estudiantes por cohorte" y "38 % de código humano con comentarios" (heredados; marcados con comentario LaTeX); GPT-4o-mini para enunciados es solo el valor por defecto en `data/config.py`.
- No hay `latexmk`/`pdflatex` en PATH: compilación no realizada. Solo se usa TikZ con la librería `positioning`.
