# Plan de estructura y línea narrativa del Trabajo Terminal

**Título:** Sistema de comparación de código mediante similitud semántica para cursos introductorios de
programación en C y C++.

**Objetivo general (textual):** Implementar un sistema de apoyo a la evaluación docente en cursos
introductorios de programación en C/C++ basado en comparación semántica de código, que permita
cuantificar la similitud lógica entre programas mediante el cálculo de la similitud del coseno e
identificar patrones de generación por inteligencia artificial evaluados a través de F1-score y
métricas de clasificación, con el fin de optimizar el proceso de evaluación.

---

## 1. Línea narrativa (el hilo que conecta todo)

Cada capítulo debe poder explicarse como un paso de esta historia:

1. **Problema.** Revisar una a una las entregas de programación consume mucho tiempo docente, y la
   aparición de la IA generativa agrega incertidumbre sobre el origen del código.
2. **Propuesta.** Una plataforma que **informa, no dictamina**: mide qué tan parecida es cada entrega a
   la solución del docente (similitud semántica con GraphCodeBERT y coseno) y añade un indicador
   experimental de estilo generado por IA (CharCNN). El docente decide (*human-in-the-loop*).
3. **Método.** Se sigue la metodología Komorebi: definición → ingeniería de datos → modelización →
   despliegue, con evaluación rigurosa (sin fuga de datos, líneas base e intervalos de confianza).
4. **Lo que mostró la evidencia.** Al evaluar con rigor, el sistema se ajustó:
   - GraphCodeBERT captura semántica ante cambios estructurales y agrupa soluciones por problema, pero
     depende de los nombres de variables; para orientar la revisión rinde igual que una línea base léxica.
   - CharCNN alcanza F1 = 0.884 en el dataset, con la generalización a otros generadores como pregunta abierta.
   - La cantidad de datos de IA se justificó con una curva de aprendizaje.
5. **Resultado.** Una plataforma funcional y verificada, que los docentes probaron y valoraron mediante
   una encuesta.
6. **Cierre.** El objetivo se cumple, con límites medidos y un trabajo futuro concreto.

**Mensaje central (para resumen, presentación y conclusiones):**
> "Graphito permite organizar y priorizar la revisión docente mediante similitud semántica. Su
> evaluación rigurosa muestra qué captura y qué no captura un modelo preentrenado en código
> introductorio, y define una ruta concreta para mejorarlo."

### Reglas de coherencia para todo el documento
- **Una sola fuente de verdad para los números:** las corridas en `runs/` (sección 5). Ningún número
  se escribe "de memoria" ni se copia de versiones anteriores.
- **Plan contra ejecución:** lo planeado en el primer semestre se conserva y se marca como
  "planificado"; lo ejecutado se reporta como resultado; los cambios se justifican con evidencia.
- **Información, no veredicto:** no usar "dictamen", "culpable" ni "plagio confirmado". Usar
  "similitud", "indicador", "orientar la revisión" y "priorizar".
- **Afirmaciones calibradas:** "sugiere", "indica" o "en este dataset" en lugar de "demuestra" o
  "irrefutable". Las explicaciones causales no medidas se presentan como hipótesis.
- **Terminología fija** (usar siempre igual):

| Término | Significado |
|---|---|
| Canal A / similitud semántica | Embeddings de GraphCodeBERT + similitud del coseno |
| Línea base léxica | Jaccard de shingles de 5 tokens abstraídos |
| Canal B / indicador estilométrico | CharCNN v2 (experimental) |
| Solución de referencia | La solución del docente (en la plataforma) o una solución aprobada de alumno (en la evaluación offline) |
| `split_v1` | Partición por tarea, sin fuga de datos |

---

## 2. Estructura capítulo por capítulo

**Estado:** ✅ se conserva · ✏️ actualizar · 🔁 reescribir · 🆕 nuevo

### Cap. 1. Introducción (`generalidades.tex`) ✏️
- Problema, justificación, **objetivo general (textual)** y objetivos específicos, alcance y limitaciones.
- **Agregar** un párrafo de contribuciones, que adelante la historia:
  1. la implementación corregida y verificada de GraphCodeBERT con DFG para C/C++;
  2. un protocolo de evaluación sin fuga de datos, con dos experimentos originales (robustez y agrupamiento lógico);
  3. el indicador estilométrico CharCNN con su curva de aprendizaje;
  4. la plataforma desplegada y su validación con docentes.

### Cap. 2. Estado del arte (`estado_del_arte.tex`) ✏️
- Detección de similitud (léxica: MOSS, JPlag y winnowing; estructural: AST; semántica: CodeBERT,
  GraphCodeBERT y UniXcoder), detección de código generado por IA y herramientas de apoyo docente.
- **Asegurar** que aparezcan los métodos léxicos (Jaccard/winnowing): justifican usarlos como línea base.
- Cerrar con un hueco claro: falta una evaluación honesta de modelos semánticos en código
  **introductorio** en C/C++ orientada al docente.

### Cap. 3. Marco teórico (`marco_teorico_v3.tex`) ✏️
- Transformers, GraphCodeBERT, DFG, similitud del coseno, Jaccard y shingles, CNN de caracteres.
- **Agregar** si falta: métricas (ROC-AUC, PR-AUC, F1, MAP@R, Recall@1, silhouette), bootstrap e
  intervalos de confianza, calibración (isotónica/Platt), t-SNE (y su limitación) y fuga de datos.

### Cap. 4. Propuesta de solución (`propuesta_de_solucion.tex`) ✏️
- Concepto de la plataforma y principio *human-in-the-loop*.
- **Revisar** la línea 165 (el vector unificado con fusión de dimensiones): hoy la fusión es solo
  experimental y no forma parte del sistema desplegado. Presentarla como idea explorada o quitarla.
- Explicitar el principio **"información, no veredicto"**.

### Cap. 5. Análisis del sistema — fase Definición de Komorebi (`analisis.tex`) ✏️
- Requisitos, reglas de negocio, requisitos no funcionales (RNF) y métricas de éxito.
- **Tabla de distribución del dataset (l. 828–854):** cambiar el título a "Distribución **planificada**"
  y reescribir la línea 854 (hoy afirma que N = 20,000 "asegura" el resultado), remitiendo a la
  justificación del Cap. 7.
- Los RNF de calidad (metas de F1, precisión y falsos positivos) se **evalúan en el Cap. 10** con los
  números reales.

### Cap. 6. Diseño del sistema (`diseño.tex`) ✏️
- Arquitectura limpia, modelo de datos e interfaz.
- **Actualizar:** "dictamen" → "resumen de similitud"; mencionar la verificación de artefactos y el catálogo precargado.

Los capítulos 7, 8 y 9 siguen las fases de Komorebi: **Ingeniería de datos**, **Modelización** y
**Despliegue**. Cada uno tiene dos secciones, una por subfase.

### Cap. 7. Ingeniería de datos (`ingenieria_de_datos.tex`) ✏️

**7.1 Adquisición de datos.** El dataset de la universidad y la estrategia para generar la contraparte de IA.
- **Dataset base:** *IEEE Programming Homework Dataset* (Universidad de Sarajevo). 43,771 entregas
  humanas de los cursos A/B de 2016–2017 en C/C++, con tareas `Zn/Zm` y estadísticas por alumno.
- **Limitaciones del dataset:** idioma serbocroata, sin enunciados y sin soluciones oficiales del docente.
- **Reconstrucción de enunciados** mediante ingeniería inversa con LLMs.
- **Estrategia de generación de IA:** mismos problemas, código en serbocroata y perfiles de estudiante,
  para que las clases difieran en el **origen** y no en el problema (1,520 archivos generados).
- **Justificación del tamaño de la clase sintética:** de la planeación (20,000) a lo ejecutado, con la
  curva de aprendizaje (rendimientos decrecientes; no saturada en sentido estricto). Ya está escrita;
  falta suavizar la redacción ("despreciables" → "pequeños") y quitar el cuadro que tapa la curva.

**7.2 Preparación de datos.** Cómo se limpiaron los datos y qué se hizo para poder usarlos.
- **Limpieza:** descartar stubs y generaciones fallidas con el mismo criterio para ambas clases, y
  quitar la cabecera del curso (era un atajo: solo aparecía en código humano).
- **Deduplicación** exacta y casi exacta (`dup_group`): ningún grupo cruza particiones.
- **Partición `split_v1`** por tarea, con los años combinados y sin fuga de datos; sha256 registrado
  para reproducibilidad.
- **Preprocesamiento por canal:**
  - CharCNN: normalización simétrica, UNK distinto de PAD y ventanas;
  - GraphCodeBERT: Tree-sitter, DFG y alineación de subtokens.
- **Tabla de composición final:** 42,389 = 40,936 humanos + 1,453 IA, por partición.

### Cap. 8. Modelización (`modelado.tex`) 🔁
Es el capítulo que más cambia. **Antes de reescribir, auditarlo** contra `runs/`; tiene secciones del
pipeline viejo (LoRA, fusión, Bellon, casos ESCOM, matriz de confusión vieja).

**8.1 Entrenamiento de modelos.** Hiperparámetros, implementación y experimentos.
- **CharCNN v2:**
  - implementación: arquitectura multiescala, pooling enmascarado y ventanas de 4,096 caracteres;
  - hiperparámetros (tabla);
  - curvas de entrenamiento por época;
  - selección de la época en validación.
- **GraphCodeBERT (Canal A):**
  - implementación: DFG fiel al original (verificado contra el código de Microsoft), entrada corregida,
    ventanas de 382 subtokens y *mean pooling*;
  - **experimento de adaptación:** el adaptador LoRA entrenado con MLM empeoraba el resultado
    (AUC 0.630 contra 0.646), así que se usa **zero-shot**. Esto justifica por qué no hay entrenamiento propio.
- **Línea base léxica** (Jaccard): definición y por qué se incluye.
- **Calibración en validación:** isotónica para el Canal A y Platt para CharCNN; umbrales `fpr_0.05` y `fpr_0.01`.
- **Experimentos comparativos de implementación:** pipeline anterior contra el corregido (0.741 → 0.856
  en el Canal A; CharCNN anterior contra v2).

**8.2 Evaluación de modelos.** Métricas, validación y explicabilidad.
- **Protocolo de validación:** test nunca usado para decisiones, bootstrap con IC 95 % e hipótesis pre-registradas.
- **Canal B (CharCNN):**
  - métricas: ROC/PR, matriz de confusión en el umbral desplegado, F1, precisión, recall y calibración;
  - limitaciones: posibles atajos del dataset y generalización a otros generadores no medida.
- **Canal A, bajo la pregunta "¿Qué tan semántica es la similitud?":**
  1. **Pares de plagio** (test): GraphCodeBERT, Jaccard y el pipeline anterior.
  2. **Robustez ante ofuscación:** aguanta los cambios estructurales; es sensible al renombrado y al código muerto.
  3. **Agrupamiento por lógica (E1):** Recall@1 de 82 %, MAP@R; figura de clusters y mapa de calor.
  4. **Similitud y corrección (E2):** señal débil pero positiva y empate con Jaccard.
- **Explicabilidad.** Ser honesto sobre su alcance: hoy **no** hay explicaciones de las decisiones
  internas de los modelos (atención o saliencia). Lo que sí hay:
  - **Visualización del espacio de embeddings:** mapa de calor por tarea y proyección t-SNE. Explican
    *cómo organiza el modelo las soluciones*.
  - **Análisis de robustez:** explica *a qué es sensible* el modelo (nombres, código muerto) y a qué no
    (estructura).
  - **Indicadores en la interfaz:** los de `xai_service` son **heurísticos** (reglas), y así se rotulan.
  - **Interpretabilidad de la línea base:** Jaccard es explicable por construcción ("comparten el X %
    de los fragmentos").
  - **Trabajo futuro:** mapas de saliencia para CharCNN y atención o atribución para GraphCodeBERT.
- **Discusión:** qué captura cada canal, qué no y por qué. Remitir al trabajo futuro.

**Quitar o mover a un anexo,** salvo que se vuelvan a medir con el pipeline actual: los resultados de
LoRA, la fusión bimodal como resultado principal, los clones de Bellon, los casos ESCOM y la matriz de
confusión vieja. *Validación con arquetipos estudiantiles* (l. 490): solo se conserva si se vuelve a
correr `scripts/benchmark_student_archetypes.py` con los modelos actuales.

### Cap. 9. Despliegue (`despliegue.tex`) ✏️

**9.1 Despliegue de modelos.** Cómo se desplegaron, cómo se integran en el sistema y la inferencia.
- **Empaquetado de modelos:** paquete `models/deploy/` con manifiesto y sha256 por archivo; promoción
  por configuración, sin sobrescribir modelos anteriores.
- **Integración:**
  - arquitectura limpia, con puertos de inferencia y almacén vectorial;
  - un `ScoringService` único para el análisis individual, asíncrono y por lote;
  - función de decisión pura en el dominio.
- **Inferencia:**
  - flujo de un análisis: normalización → embeddings y coseno contra las referencias → CharCNN por ventanas → persistencia;
  - Chroma con una colección por versión del modelo y reindexado;
  - inferencia en un hilo aparte para no bloquear la API.
- **Falla segura:** si un artefacto no coincide, `/health` muestra `inference_ready=false` y el análisis
  responde 503. **Nunca** se usa un stub en silencio.
- **Infraestructura:** Docker, Vercel (frontend), Supabase (PostgreSQL), servidor con GPU y túnel de Cloudflare.
- **Presentación al docente:** la similitud como información, no como veredicto. Va con captura de pantalla.

**9.2 Monitorización de los modelos.** Pruebas, métricas y encuesta a profesores.
- **Pruebas automatizadas:** 1,307 pruebas (unitarias, de API, de contrato del frontend y de integridad
  de artefactos) y lint/typecheck/vitest en el frontend.
- **Prueba de extremo a extremo en modo REAL:**
  - el análisis individual y el de lote dan resultados idénticos;
  - un artefacto alterado provoca 503 sin escribir nada;
  - las migraciones y el reindexado son idempotentes.
- **Métricas en operación:**
  - `/health` (estado, motor y sha de cada artefacto);
  - versión del modelo y del umbral en cada reporte, para trazabilidad;
  - estado de calibración visible en la interfaz.
- **Validación con docentes:** catálogo precargado y encuesta (se detalla en la sección 3). Responde
  la parte del objetivo "**con el fin de optimizar el proceso de evaluación**", que los experimentos
  sin usuarios no pueden medir. Incluye resultados (SUS, utilidad percibida, ahorro de tiempo
  estimado) y limitaciones.

> **Nota:** si la sección 9.2 resulta muy larga con la encuesta, puede separarse en un capítulo propio
> ("Validación con docentes") sin cambiar el contenido. Se conserva dentro de Monitorización para
> respetar la estructura de Komorebi.

### Cap. 10. Conclusiones y trabajo futuro (`conclusiones.tex`) 🔁
Hoy contiene afirmaciones falsas: LoRA (l. 23) y métricas del pipeline viejo (l. 27: 92.4 %, 8.2 %,
Bellon). Hay que reescribirlo con esta estructura:

1. **Cumplimiento del objetivo**, con una tabla parte por parte:

| Parte del objetivo | Evidencia | Estado |
|---|---|---|
| Sistema de apoyo a la evaluación docente | Plataforma desplegada, Cap. 9 | Cumplido |
| Similitud lógica con coseno | GraphCodeBERT + coseno; agrupamiento y robustez, Cap. 8.2 | Cumplido, con límites medidos |
| Patrones de IA evaluados con F1 | F1 = 0.884, ROC-AUC = 0.994, Cap. 8.2 | Cumplido en el dataset |
| Optimizar la evaluación | Encuesta docente, Cap. 9.2 (percepción) | Según los resultados |

2. **Requisitos no funcionales:** las metas de F1, precisión y falsos positivos del Cap. 5 contra los
   valores reales del umbral desplegado: F1 0.884, precisión 0.880 y ~1 % de falsos positivos (40 de 4,201).
3. **Hallazgos principales**, uno por experimento, en lenguaje claro.
4. **Limitaciones**, todas juntas: dataset de un solo curso y país; referencia aproximada en la
   evaluación offline; CharCNN sin validar con otros generadores; encuesta de percepción con pocas
   personas; sin medición objetiva del tiempo de revisión.
5. **Trabajo futuro, priorizado:**
   1. entrenamiento contrastivo de GraphCodeBERT, con pares de las transformaciones ya implementadas y negativos del mismo problema;
   2. validar CharCNN con otros LLMs (conjunto de prueba diverso);
   3. medición objetiva del tiempo de revisión con docentes (estudio con y sin plataforma);
   4. métrica de *containment* para que el umbral resista el código agregado;
   5. evaluar modelos alternativos (UniXcoder) o un LLM local como juez.

---

## 3. Validación con docentes (catálogo + encuesta)

### 3.1 Objetivo
Medir la **utilidad percibida**, la **facilidad de uso** y la **expectativa de reducir el tiempo de
evaluación** de la plataforma, según docentes de programación introductoria.

### 3.2 Catálogo de programas precargados
- **Estado:** diseñado en `guias_implementacion/03_banco_tareas_precargadas.md`, **no implementado**
  (no existen `plantilla_service.py` ni `seed_plantillas.py`).
- **Contenido sugerido:** 3–5 problemas introductorios (ciclos, arreglos, cadenas, funciones), cada
  uno con su solución de referencia y unas **10–15 entregas** variadas:
  - correctas con el mismo enfoque;
  - correctas con un enfoque distinto;
  - con errores (por ejemplo, un `<` en lugar de `<=`);
  - incompletas;
  - y alguna generada por IA.
- **Origen de los programas:** tomarlos del dataset público (ya anónimo), adaptando los enunciados al
  español, o escribirlos ex profeso. **No usar código de alumnos reales de ESCOM sin consentimiento.**
- Que cada docente pueda **clonar** el catálogo a su cuenta y explorarlo sin subir nada.

### 3.3 Instrumento (encuesta)
Con 15–20 minutos de uso previo guiado:

1. **Perfil:** años de docencia, cursos que imparte y número típico de alumnos por grupo.
2. **SUS (System Usability Scale):** los 10 ítems estándar, de 1 a 5. Da una calificación de 0 a 100
   comparable con la literatura (más de 68 se considera por encima del promedio).
3. **Utilidad percibida** (escala Likert de 1 a 5, adaptada del modelo TAM):
   - "La similitud con mi solución me ayuda a decidir qué entregas revisar primero."
   - "La información del reporte es clara y fácil de interpretar."
   - "Confiaría en esta información como apoyo, no como calificación."
   - "Usaría una plataforma así en mis cursos."
   - "El indicador de estilo de IA me resulta útil."
4. **Tiempo:**
   - "¿Cuánto tiempo dedica hoy a revisar una entrega típica?" (minutos)
   - "¿Cuánto estima que reduciría ese tiempo con la plataforma?" (0 %, 1–25 %, 26–50 %, más de 50 %)
5. **Preguntas abiertas:** qué fue lo más útil, qué falta o confunde, y qué cambiaría.

**Tarea guiada sugerida:** antes de la encuesta, "Abra el problema X. Sin leer el código, indique qué
3 entregas revisaría primero y por qué." Muestra en la práctica el uso para priorizar.

### 3.4 Participantes, ética y análisis
- **Participantes:** docentes de programación introductoria (ESCOM y otras instituciones). Meta
  realista: **8–15 respuestas**. Reportar el número exacto obtenido.
- **Ética:** consentimiento informado, respuestas anónimas y uso exclusivamente académico. Consultar con
  tu asesor si se requiere algún aval institucional.
- **Análisis:** descriptivo (mediana y rango intercuartílico por ítem, distribución de la estimación de
  ahorro de tiempo), calificación SUS (media e intervalo) y temas recurrentes de las respuestas abiertas.
- **Limitaciones** que deben escribirse: mide **percepción**, no tiempo real; muestra pequeña y
  autoseleccionada; sesgo de novedad.

### 3.5 Contenido de la validación (Cap. 9.2)
Objetivo → catálogo (con captura de pantalla) → instrumento → participantes y procedimiento →
resultados (tablas y gráfica de barras apiladas de la escala Likert, calificación SUS) → discusión
(¿se percibe que optimiza la evaluación?) → limitaciones.

---

## 4. Calendario (del 14 de octubre a principios de noviembre)

| Fechas | Tarea |
|---|---|
| 14–16 oct | Auditoría de `modelado.tex` y `conclusiones.tex` (solo reporte). Ajustes menores de la curva. |
| 15–18 oct | Interfaz sin veredictos + **catálogo precargado** (implementar la guía 03) |
| 18–19 oct | Preparar la encuesta (formulario) y el consentimiento; probarla con 1–2 personas |
| 20–28 oct | **Encuesta abierta a docentes.** En paralelo: reescribir los Cap. 8 y 9 y actualizar los Cap. 1–7 |
| 29–31 oct | Sección 9.2 con los resultados de la encuesta y Cap. 10 (conclusiones) |
| 1–3 nov | Revisión con el asesor, coherencia final de números y presentación |

**Ruta crítica:** el catálogo y la encuesta, porque dependen de terceros (los docentes). Conviene
lanzar la encuesta lo antes posible, aunque la redacción vaya en paralelo.

---

## 5. Fuente única de verdad: números clave

| Dato | Valor | Fuente |
|---|---|---|
| Corpus usado | 42,389 (40,936 humanos / 1,453 IA) | `data/splits/split_v1.json.gz` |
| CharCNN, test | ROC-AUC 0.994; umbral `fpr_0.01` = 0.1715 | `runs/char_cnn/20261011-015734` |
| CharCNN, matriz en el umbral desplegado | VN 4161, FP 40, FN 37, VP 293 → precisión 0.880, recall 0.888, F1 0.884 | ídem |
| Curva de aprendizaje | PR-AUC 0.55 (55 grupos) → 0.98 (874); no saturada | `runs/char_cnn_lc/20261014-023215` |
| Canal A, pares de plagio (test) | Jaccard 0.945, GraphCodeBERT v2 0.856, pipeline anterior 0.741 (ROC-AUC) | `runs/graphcodebert/20261011-082155` |
| Robustez | GraphCodeBERT con renombrado: 0.856 → 0.683; cambios estructurales ≈ sin efecto | `runs/robustness/20261012-050941` |
| Agrupamiento (E1) | v2: MAP@R 0.387, Recall@1 0.825; Jaccard: MAP@R 0.450 | `runs/logic_eval/20261013-152644` |
| Similitud y corrección (E2) | v2: AUC 0.560 [0.520, 0.602]; Jaccard: 0.563; empate | ídem |
| Plataforma | 1,307 pruebas en verde; E2E en modo REAL | `sdd/archive/2026-10-11-backend-model-integration/` |

**Antes de entregar:** buscar en el documento cada número que aparezca y confirmar que coincide con
esta tabla. En particular, eliminar cualquier resto de 20,000, 92.4 %, 8.2 %, LoRA o Bellon como
resultado actual.
