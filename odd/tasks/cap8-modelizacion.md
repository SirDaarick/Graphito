# Plan de redacción — Cap. 8 Modelización (`modelado.tex`)

**Objetivo:** reescribir el capítulo 8 según `Documentacion/planeacion/PLAN_ESTRUCTURA_TESIS.md` (sec. 2, Cap. 8;
sec. 5 números), con el mismo registro del Cap. 7: formal, accesible a lectores de cualquier
formación, con analogías breves, y con **diagramas que expliquen cómo son y cómo funcionan los
modelos** y **organizadores** (tablas agrupadas) para entender los hiperparámetros.

**Archivo principal:** `Documentacion/Documento/capitulos/modelado.tex`.
**Fuente de hechos:** auditoría del 2026-10-14 (resumida abajo) + `runs/` citados. Ningún número de memoria.

---

## 1. Diagnóstico (auditoría contra `runs/`)

- Solo `\label{cap:modelado}` se referencia desde otros archivos → los demás labels pueden cambiar.
- **Eliminar** (sin anexo; no hay datos actuales que los respalden):
  fusión bimodal y matriz de "dictamen" (l. 112–185), historia V1–V5 con 92.4 % / 8.2 % (l. 195–223,
  304–313, 533), benchmark ESCOM (l. 256–274), invarianza estilométrica (l. 277–289), clones de
  Bellon (l. 316–326), arquetipos (l. 490–526; el JSON es anterior a los modelos v2), LoRA como
  método (l. 24–33).
- **Todos** los números de arquitectura y entrenamiento de CharCNN son del v1 (embedding 64,
  128 filtros, FC 256, dropout 0.5, AdamW 5e-4, batch 32, paciencia 5, "época 10", vocab 97).
- **Figuras obsoletas** (2026-09-27): `curvas_entrenamiento_charcnn.png`, `matriz_confusion_charcnn.png`
  → regenerar con `scripts/generate_tt_figures.py`. Quitar `benchmark_semantico_escom.png` e
  `invarianza_estilometrica.png` del texto.
- **Se conservan con ajustes:** robustez (re-copiar IC de `runs/robustness/20261012-050941/report.md`
  sec. 3; corregir "ocho operadores" → T0 + T1–T7 con T7 en 3 intensidades; H2 no es "control
  perfecto": el harness la marca FAILED por una caída numérica de 2e-6 → explicarlo como ruido
  numérico, sin ocultarlo; verificar el número de pares) y agrupamiento lógico E1/E2 (números ya
  coinciden con `runs/logic_eval/20261013-152644/report.md`).

## 2. Hechos verificados (fuente de verdad para la redacción)

**CharCNN v2** (`runs/char_cnn/20261011-015734`, `models/char_cnn/v2/`):
- Arquitectura: vocab 98 (96 caracteres + PAD + UNK), embedding 128; 4 ramas convolucionales
  k = 3, 5, 7, 9 con 64 filtros cada una; LayerNorm + ReLU; pooling enmascarado max + media
  (solo posiciones reales) → 512; dropout 0.4; capa densa 512→1024 (ReLU, "huella de estilo");
  salida 1024→2. Ventanas de 4,096 caracteres, paso 2,048, máx. 8 (verificar en
  `models/char_cnn/v2/scoring.py` cómo se combinan las ventanas en una sola puntuación).
- Entrenamiento: Adam lr 1e-3, weight decay 1e-4; ReduceLROnPlateau (factor 0.5, paciencia 3;
  lr 1e-3 → 5e-4 en época 20 → 2.5e-4 en época 35); entropía cruzada; batch 128; máx. 50 épocas;
  paro anticipado paciencia 7; semilla 42; muestreo 1:1 por época (874 IA + 874 humanos nuevos =
  1,748 por época). Datos: train 11,562 (10,688 H / 874 IA representantes), val 3,077 (2,868/209),
  test representantes 4,531 (4,201/330).
- Selección: máx. (ROC-AUC val, PR-AUC val); época 31 de 38 (índice 30); val ROC-AUC 0.99905,
  PR-AUC 0.98895.
- Test: ROC-AUC 0.9937 [0.9909, 0.9965]; PR-AUC 0.9581 [0.9437, 0.9726]; ECE 0.0088.
- Calibración Platt en val; umbrales `fpr_0.05` = 0.0075 y `fpr_0.01` = 0.1715 (desplegado).
- En `fpr_0.01` (test): VN 4161, FP 40, FN 37, VP 293 → precisión 0.880 [0.840, 0.912], recall
  0.888 [0.858, 0.922], F1 0.884 [0.860, 0.909], FPR 0.95 %.
- En `fpr_0.05`: VN 4009, FP 192, FN 9, VP 321 → precisión 0.626, recall 0.973, F1 0.762.
- Por generador: deepseek-chat (n=227) AUC 0.992, recall 0.881; qwen3 (n=100) AUC 0.997, recall
  0.900; el resto con n ≤ 1.
- Atajos residuales tras normalizar: `using namespace` (H 0.07 vs IA 0.30), prefijo `std::`
  (0.46 vs 0.24) → limitación.
- Bootstrap: 1,000 remuestreos por `dup_group`, IC 95 %.
- El CharCNN legacy (ROC 0.999) está **contaminado** (entrenado con un split que se traslapa con
  el test): no compararlo; solo advertir que el "96 %" anterior estaba inflado.

**GraphCodeBERT v2** (`runs/graphcodebert/20261011-082155`, `models/graphcodebert/v2/`):
- `microsoft/graphcodebert-base`, zero-shot (sin entrenamiento propio). Entrada: subtokens de
  código + nodos del DFG (384 + 128, máx. 512). Ventanas de 382 subtokens, paso 191, máx. 16.
- Pooling **mean**, elegido en validación (el valor por defecto del código es cls; mean ganó:
  ROC-AUC val 0.865 vs 0.797).
- DFG verificado contra el código original de Microsoft (`tests/reference/graphcodebert/`).
- Zero-shot vs LoRA: en el benchmark anterior el adaptador LoRA entrenado con MLM bajaba AUC de
  0.646 a 0.630 (`archivo/benchmarks_modelos_anteriores/benchmark_baseline_nolora_results.json`, `models/graphcodebert/README.md:246`).
  Advertir que fue en el benchmark anterior (golden set), no en `split_v1`.
- Pares de plagio, test (1,908,545 pares, 338 positivos), ROC-AUC [IC 95 %]: Jaccard 0.945
  [0.930, 0.964]; winnowing 0.944; v2 0.856 [0.796, 0.893]; v2 sin DFG 0.851; pipeline anterior
  0.741 [0.653, 0.800]. El DFG no aporta diferencia medible (IC traslapados).
- Calibración isotónica en val; `fpr_0.05` alcanzable; `fpr_0.01` **inalcanzable** (las similitudes
  zero-shot se concentran cerca de 1).
- Errores de análisis sintáctico 25 %, truncado 11 %, 4.7 ventanas por archivo (README).

**Línea base léxica:** Jaccard de shingles de 5 tokens abstraídos (identificadores → ID, literales
→ NUM/STR/CHR, palabras clave intactas) — `models/graphcodebert/v2/baselines.py`,
`models/evaluation/normalize.py`. Por construcción es invariante al renombrado (explica H2).
Winnowing (k=5, w=4) como segunda línea base.

**Robustez** (`runs/robustness/20261012-050941`): T1 renombrado, T2 for↔while, T3 reordenar
instrucciones independientes, T4 operadores equivalentes, T5 código muerto, T6 inversión de if,
T7 cascada T2→T5 en 0.25/0.5/1.0. ROC-AUC v2: T0 0.856, T1 0.683, T5 0.768, T7@1.0 0.714;
T2/T3/T4/T6 cambian ≤ 0.006. Jaccard: 0.931–0.950. H1 refutada (DiD +0.128 [0.014, 0.276]),
H2 ver arriba, H3 no concluyente.

**Agrupamiento E1/E2** (`runs/logic_eval/20261013-152644`): E1 (2,842 entregas) MAP@R v2 0.387
[0.341, 0.443], Recall@1 0.825; Jaccard MAP@R 0.450, Recall@1 0.847; azar 0.002. E2 (14 tareas,
543 entregas): AUC v2 0.560 [0.520, 0.602], Jaccard 0.563 → empate (diferencia −0.003
[−0.052, +0.036]). La referencia es una entrega aprobada de alumno, no del docente.

**XAI** (`backend/app/application/services/xai_service.py`): fila de similitud a nivel archivo
(Jaccard y referencia más cercana) y líneas marcadas por **reglas** (regex de comentarios típicos de
LLM y construcciones avanzadas), rotuladas "no es salida del modelo". No hay atención ni saliencia.

## 3. Línea narrativa

1. **Qué se construyó** (8.1): dos "lectores" del código que miran cosas distintas, más una regla
   simple de comparación como vara de medir.
2. **Cómo se puso a prueba** (8.2): reglas del juego (prueba intocable, intervalos de confianza,
   hipótesis escritas antes), y la pregunta guía "¿qué tan semántica es la similitud?".
3. **Qué mostró la evidencia:** CharCNN funciona muy bien en este dataset; GraphCodeBERT agrupa
   por problema y resiste cambios de estructura, pero depende de los nombres y no supera a la línea
   base léxica. Se dice con naturalidad: un resultado negativo bien medido también es un aporte.

## 4. Estructura y diagramas

### Introducción (≈ 2 párrafos)
- Ubicación en Komorebi. Mapa del capítulo.
- **Fig. 8.1 (TikZ) Panorama:** un archivo entregado → Canal A (GraphCodeBERT + coseno contra la
  solución de referencia → "similitud") | Canal B (CharCNN → "indicador de estilo IA") | línea base
  léxica (Jaccard). Salidas = información para el docente, no veredicto.

### 8.1 Entrenamiento de modelos
**8.1.1 Canal B: CharCNN v2**
- Idea en palabras simples: lee el código letra por letra con "lupas" de 3, 5, 7 y 9 caracteres
  que detectan hábitos de escritura.
- **Fig. 8.2 (TikZ) Arquitectura**, de abajo hacia arriba o izquierda a derecha, con una etiqueta
  llana en cada bloque: caracteres → embedding (128) → 4 ramas convolucionales (k=3,5,7,9; 64
  filtros) → normalización + ReLU → resumen max + media (ignora relleno) → 512 → dropout → 1024
  ("huella de estilo") → 2 salidas (humano / IA).
- **Fig. 8.3 (TikZ) Ventanas:** archivo largo dividido en ventanas de 4,096 con traslape de 2,048 →
  una puntuación por ventana → combinación (según `scoring.py`).
- **Tabla 8.1 Organizador de hiperparámetros**, agrupada en filas-encabezado: *Entrada* (vocabulario,
  ventana, paso, máx. ventanas), *Arquitectura* (embedding, ramas, filtros, dropout, capa densa),
  *Entrenamiento* (optimizador, tasa de aprendizaje y su reducción, lote, épocas, paciencia,
  semilla, muestreo 1:1), *Selección* (criterio de época). Columnas: Parámetro | Valor | Qué
  significa (una frase llana) | Por qué.
- **Fig. 8.4 (TikZ, opcional) Una época de entrenamiento:** 874 IA + 874 humanos al azar → lotes de
  128 → actualizar pesos → evaluar en validación → ¿mejoró? guardar / ¿7 épocas sin mejorar? parar.
- Curvas de entrenamiento: `figuras/curvas_entrenamiento_charcnn.png` **regenerada**; época
  seleccionada 31 de 38.

**8.1.2 Canal A: GraphCodeBERT (zero-shot)**
- Idea llana: modelo preentrenado con millones de programas que convierte un código en un vector
  (lista de números) que resume lo que hace; dos códigos parecidos producen vectores que apuntan a
  la misma dirección (similitud del coseno; analogía de flechas/brújula).
- **Fig. 8.5 (TikZ) Funcionamiento:** código → subtokens + grafo de flujo de datos (DFG: "quién le
  pasa valor a quién") → GraphCodeBERT → vector por ventana → promedio → vector del archivo →
  coseno con la solución de referencia → similitud.
- **Fig. 8.6 (TikZ, opcional) Similitud del coseno:** dos flechas con ángulo pequeño (parecidos) vs
  ángulo grande (distintos).
- **Tabla 8.2 Organizador de configuración** (mismo formato que 8.1): modelo, longitud de código,
  nodos DFG, ventana, paso, máx. ventanas, pooling (y por qué mean).
- **Por qué zero-shot:** experimento del adaptador LoRA (0.646 → 0.630, con su advertencia).
  Explicar "zero-shot" = usar el modelo tal como viene, sin reentrenarlo.
- **Corrección del pipeline:** del anterior al v2 (ROC-AUC 0.741 → 0.856 en pares de plagio):
  DFG fiel al original y entrada corregida. Sin detalle de código.

**8.1.3 Línea base léxica (Jaccard)**
- Qué es y por qué se incluye (vara de medir simple, explicable, cercana a MOSS/JPlag).
- **Fig. 8.7 (TikZ) Shingles:** una línea de código → tokens abstraídos (ID = ID + NUM ;) →
  ventanas de 5 tokens → dos conjuntos → Jaccard = compartidos / totales.

**8.1.4 Calibración y umbrales**
- Idea llana: convertir una puntuación cruda en algo interpretable y fijar el umbral según cuántas
  falsas alarmas se toleran (1 de cada 100 o 5 de cada 100).
- **Tabla 8.3 Organizador:** Canal | Método (Platt / isotónica) | Ajustado en | Umbral `fpr_0.05` |
  Umbral `fpr_0.01` | Nota (Canal A: `fpr_0.01` inalcanzable).

### 8.2 Evaluación de modelos
**8.2.1 Protocolo**
- **Fig. 8.8 (TikZ) Reglas del juego:** entrenamiento → aprender; validación → decidir (época,
  pooling, umbrales, calibración); prueba → medir **una sola vez**. Más: bootstrap con IC 95 %
  (analogía: repetir la medición con muestras ligeramente distintas para ver cuánto varía) e
  hipótesis registradas antes de ver resultados.
- **Tabla 8.4 Glosario de métricas** (organizador): ROC-AUC, PR-AUC, precisión, recall, F1, FPR,
  ECE, MAP@R, Recall@1 — cada una con "qué pregunta responde" en una frase llana.

**8.2.2 Canal B: resultados**
- ROC/PR: copiar `runs/char_cnn/20261011-015734/roc.png` y `pr.png` a figuras como
  `charcnn_v2_roc.png` / `charcnn_v2_pr.png` (o una sola si basta).
- Matriz de confusión regenerada (`matriz_confusion_charcnn.png`) + explicación llana de cada celda
  (de 4,201 humanos, 40 marcados por error; de 330 IA, 293 detectados).
- Tabla de métricas en `fpr_0.01` y `fpr_0.05` (compromiso entre falsas alarmas y detección).
- Calibración: ECE + `reliability.png` copiado como `charcnn_v2_confiabilidad.png` (opcional).
- Por generador y limitaciones (atajos residuales, dos generadores, legacy contaminado).

**8.2.3 Canal A: ¿qué tan semántica es la similitud?** (cuatro preguntas)
1. Pares de plagio: tabla con Jaccard, winnowing, v2, v2 sin DFG, anterior.
2. Robustez: conservar sección y figura `robustez_degradacion_canal_a.png`; tabla de
   transformaciones con un ejemplo llano de cada una; correcciones del diagnóstico.
3. Agrupamiento por lógica (E1): conservar tablas; figuras `g3_map_at_r.png`, `clusters_canal_a.png`,
   `g1_heatmap.png` y `g2_projection.png` (con la advertencia de que t-SNE deforma distancias).
4. Similitud y corrección (E2): `g4_correctness.png`; empate con Jaccard.
- **Tabla 8.x Organizador de hallazgos:** Pregunta | Resultado | Qué significa para el docente.

**8.2.4 Explicabilidad** — honesto sobre su alcance, según el plan general: visualización del
espacio (heatmap, t-SNE), análisis de robustez, indicadores heurísticos de la interfaz (rotulados
como reglas), interpretabilidad de Jaccard; trabajo futuro (saliencia, atribución).
Opcional: `g5_teacher_view.png` si ilustra la vista del docente.

**8.2.5 Discusión** — qué captura cada canal, qué no y por qué (hipótesis, no causas medidas);
remitir al Cap. 10.

### Conclusión
Resumen y puente al Cap. 9 (Despliegue). Sin LoRA como resultado, sin fusión.

## 5. Reglas de estilo (iguales que Cap. 7)
- Español formal y neutro, oraciones cortas, cada término técnico definido la primera vez con una
  analogía breve. Matemáticas mínimas (coseno y Jaccard con su fórmula y una frase que la lea).
- Calibrado: "sugiere", "indica", "en este dataset". Nunca "demuestra", "garantiza", "dictamen",
  "culpable", "plagio confirmado", "irrefutable".
- Terminología fija del plan general. Resultados negativos dichos sin rodeos y sin dramatismo.
- TikZ: solo la librería `positioning` está cargada; no editar el preámbulo.
- Mantener `\label{cap:modelado}`. Verificar `\cite` contra `referencias.bib`.
- Comentar `% TODO verificar` cualquier dato que no se pueda confirmar.

## 6. Tareas
- [x] T1 Auditoría y plan — inline + explorador
- [x] T2 Regenerar figuras y redactar el capítulo — delegado (Sonnet)
- [ ] T3 Revisión de números, labels y figuras — inline
- [x] T4 Subsección de evolución de versiones (`subsec:evolucion_modelos`) — delegado
  - Verificado: 0.630/0.646 (todo) y 0.603/0.627 (prueba) en `benchmark_baseline*_results.json`; canal B anterior 0.999/0.992 es la vista de prueba (en "todo" son 0.9985/0.987).
  - Verificado: clang-format FPR 0.667 (prueba) / 0.727 (todo); canónico AUC 0.996, F1 0.881, 23 de 108 IA perdidas; arquetipo "completamente diferente" raw 0.8983; LoRA perplejidad 1.89; 22,714; 98.7 %; 1,825/2,621; 0.9615; marcadores de curso 5.63e-5 (0.0056 %).
  - Sin tabla V1–V5 (TF-IDF/RF); sin citas nuevas; texto de "Zero-Shot" y "Corrección del Pipeline" acortado con `\ref{subsec:evolucion_modelos}`.

- [x] T5 Simplificación y limitaciones — delegado
  - Evolución reducida a intro + línea de tiempo + tabla + lección; winnowing, "v2 sin DFG" y "nombres normalizados" salen de las tablas (una frase cada uno); tablas de Canal A solo GraphCodeBERT vs Jaccard (+ azar).
  - Nueva subsubsección "Adaptación a C y C++" (diagrama DFG, tabla de ajustes de `models/graphcodebert/v2/dfg.py` l. 1-27, tabla de apuntadores) y nueva subsección "Limitaciones e Ideas no Exploradas" (dos tablas) antes de Discusión.
  - Verificado: CodeSearchNet (2.3M funciones, seis lenguajes: Ruby, JavaScript, Go, Python, Java, PHP; sin C/C++) en arXiv 2009.08366v4 (HTML).
  - Tablas de hiperparámetros y de configuración de GraphCodeBERT pasan a 3 columnas (se quita "Por qué"); se eliminan las tablas de contrastes E1 y de E2 (cifras pasan a prosa).

## Notas de verificación (T2)
- Combinación de ventanas CharCNN (`models/char_cnn/v2/scoring.py`): se promedian los logits de las ventanas y luego softmax; en entrenamiento se usa un solo recorte aleatorio. Fusión de ventanas GraphCodeBERT (`embed.py`): media por subtokens de código en cada ventana, media sin pesos entre ventanas.
- Robustez: 1,908,545 pares (338 positivos), 6,797 programas, 14 asignaciones (el texto anterior decía 1,993,656 pares: era erróneo). T7 = T2→T3→T4→T5. IC re-copiados de `report.md` sec. 3 (difieren en el tercer decimal del texto anterior).
- Épocas: `selection.epoch`=30 (índice desde 0) = 31.ª de 38; la figura regenerada la marca como 30. LR baja en los índices 20 y 35.
- Calibración Canal A `fpr_0.05` = 0.00045 (espacio calibrado; TPR val 0.489, FPR 0.040); `fpr_0.01` inalcanzable.
- Tasas de error de análisis (25 %), truncado (11 %) y 4.7 ventanas son sobre los 11,886 archivos embebidos (val+test), no solo la prueba.
- Figuras: regeneradas `curvas_entrenamiento_charcnn.png` y `matriz_confusion_charcnn.png`; copiadas ROC/PR de CharCNN. No se usó `reliability.png` (ruidosa, en inglés; se eliminó la copia), `comparativa_canal_a.png`, `g2_projection.png` ni `g5_teacher_view.png` (rótulos en inglés). `g1`, `g3`, `g4` y ROC/PR tienen rótulos en inglés (se avisa en el pie de figura); conviene regenerarlas en español.
- Pendiente: compilar (no hay pdflatex en PATH); `% TODO verificar` sobre la columna "Por qué" de la Tabla de hiperparámetros.

## 7. Notas
- Se corrigió en el Cap. 7 el número de humanos de entrenamiento: CharCNN usa 10,688
  representantes (uno por familia de casi-copias), no 24,810.
