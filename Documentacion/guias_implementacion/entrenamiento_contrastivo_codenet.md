# Guía de Implementación: Entrenamiento Contrastivo de GraphCodeBERT con CodeNet

> **Estado:** planificado, no ejecutado. Esta guía es el pre-registro del experimento: hipótesis, criterio de decisión y análisis quedan fijados aquí **antes** de entrenar o mirar resultados sobre ESCOM.
> **Alcance:** ajuste contrastivo (LoRA) del Canal A con datos externos (Project CodeNet). La evaluación se hace únicamente sobre datos de ESCOM, en local.
> **Línea base y entrada:** `v2_norm` zero-shot: renombrado canónico de identificadores (`models/logic_eval/canonical.py`, `identifiers_v1`) y luego `v2` (DFG, pooling `mean`), sin adaptador. Es la entrada desplegada del Canal A (`odd/tasks/gcb-v2-norm.md`): en `runs/robustness_v2norm/20261019-222018`, ROC-AUC bajo T1 (renombrado) 0.684 → 0.902 y en T0 0.856 → 0.902; en E1 no hay diferencia significativa. Las menciones de `v2` que quedan en la sección 0 describen resultados ya medidos con esa entrada.

---

## Resumen

| Pregunta | Respuesta |
|---|---|
| ¿Qué se entrena? | Un adaptador LoRA sobre GraphCodeBERT con entrada `v2_norm` (identificadores canónicos + DFG), usando InfoNCE. |
| ¿Con qué datos? | Project CodeNet C++1000: envíos humanos con estado verificado por un juez (Accepted / Wrong Answer). |
| ¿Dónde se evalúa? | En ESCOM (E1, E2 y robustez T1–T7), una sola vez, con la configuración congelada. |
| ¿Cuándo se detiene? | Si el piloto (F2) no cumple el criterio de continuación. Se reporta como resultado negativo. |
| ¿Cuánto cuesta? | 15–25 h de GPU en la RTX 2060 Super, o unos 10–30 USD rentando una GPU para F3. |

---

## 0. Contexto

El Canal A convierte cada entrega en un vector y lo compara por coseno con la **solución de referencia del docente** (`Documentacion/Documento/capitulos/modelado.tex:22`, `:242`). Hoy se usa GraphCodeBERT zero-shot:

- El adaptador LoRA anterior se entrenó con MLM y además recibía la entrada legacy desordenada. Bajaba el ROC-AUC de 0.646 a 0.630 (`archivo/benchmarks_modelos_anteriores/benchmark_baseline_nolora_results.json`). Por eso no se puede atribuir el fracaso solo al objetivo MLM: había dos fallas a la vez.
- Con la entrada corregida (`v2`), GraphCodeBERT obtiene ROC-AUC de 0.741 a 0.856, por debajo de Jaccard (0.945) (`modelado.tex:459-460`).
- En E1, GraphCodeBERT agrupa por tarea peor que Jaccard: ΔMAP@R = −0.0639, IC95 [−0.0830, −0.0443] (`Documentacion/informes/REPORTE_EVALUACION_AGRUPAMIENTO_LOGICO_CANAL_A.md:51`).
- En E2, parecerse a la referencia predice la corrección solo débilmente: Macro-AUC = 0.5598, IC95 [0.5199, 0.6015] (mismo reporte, línea 18).
- Bajo ofuscación, Jaccard no se degradó más que `v2`; H1 quedó refutada (`Documentacion/informes/REPORTE_EXPERIMENTO_ROBUSTEZ_CANAL_A.md:18`).

**Pregunta:** ¿un objetivo contrastivo que enseñe explícitamente "resuelve el mismo problema = vectores cercanos" mejora la similitud con la referencia en ESCOM respecto a `v2_norm` zero-shot?

### Qué significa "parecido" en este experimento

El objetivo **no es detectar plagio** sino medir qué tan cerca está una entrega de la solución del docente:

| Par | Debe quedar |
|---|---|
| Referencia + otra solución correcta del mismo problema (aunque use otro algoritmo) | **cerca** |
| Referencia + solución incorrecta del mismo problema | **más lejos que la correcta** |
| Referencia + programa de otro problema | **lejos** |

---

## 1. Hipótesis (pre-registro)

| Hipótesis | Enunciado | Se confirma si | Se refuta si |
|---|---|---|---|
| **H1** (primaria) | El ajuste mejora la relación entre similitud y corrección. | Macro-AUC de E2 (contrastivo) − Macro-AUC de E2 (`v2_norm`) > 0, con IC95 que excluye 0. | El IC95 excluye 0 con signo opuesto. Si contiene 0: **no concluyente**. |
| **H2** | El ajuste mejora el agrupamiento por tarea. | ΔMAP@R de E1 (contrastivo − `v2_norm`) > 0, con IC95 que excluye 0. | El IC95 excluye 0 con signo opuesto. |
| **H3** (no regresión) | El ajuste no reduce la robustez ante ofuscación. | ΔAUC bajo T1–T7 no es peor que el de `v2_norm` (IC95 de la diferencia contiene 0 o es favorable). | El IC95 excluye 0 en contra del modelo ajustado. |

Reglas fijadas de antemano:

- Se reportan todas las condiciones y ablaciones, sin seleccionar las favorables.
- La comparación contra Jaccard se reporta siempre, aunque no sea hipótesis primaria.
- Expectativa realista para H1: subir de 0.56 a 0.65–0.70 ya sería un resultado sólido. La corrección la deciden las pruebas unitarias, no el coseno; un error de una sola línea (`<` por `<=`) no es separable por un embedding.

---

## 2. Datos y reglas contra fuga de información

| Regla | Detalle |
|---|---|
| Entrenar fuera, evaluar en ESCOM | CodeNet solo se usa para entrenar y validar. ESCOM nunca entra al entrenamiento. |
| División por problema | Se divide CodeNet 80/10/10 **por problema**, nunca por envío. |
| Deduplicación cruzada | Antes de entrenar, se compara CodeNet contra ESCOM con el shingling de `models/graphcodebert/v2/baselines.py` y se descartan coincidencias. |
| Transformaciones reservadas | T1–T7 no se usan para entrenar. Así funcionan como prueba de robustez fuera de distribución. |
| Sin código generado por IA | CodeNet es código humano. Esto evita que el modelo aprenda "estilo de IA = parecido" y contamine el Canal B. |
| Referencias del docente | Antes de F4, el docente o asesor escribe la solución de referencia de las 14 tareas de E2. Hoy la referencia es una entrega aprobada de un alumno (`modelado.tex:698`, `:763`); esto elimina esa limitación. |
| Privacidad | Las entregas de ESCOM se evalúan solo en local. A un servicio externo solo se sube CodeNet y su caché. |
| Licencia | Verificar el archivo LICENSE de `IBM/Project_CodeNet` antes de citarlo en la tesis. |

### Fuente: Project CodeNet

- Unos 13.9 M envíos en 4 053 problemas; C++ es el lenguaje más grande (8.0 M envíos, 4.35 M aceptados).
- Cada envío trae su estado del juez (Accepted, Wrong Answer, etc.).
- Se usa el subconjunto ya depurado **Project_CodeNet_C++1000**, no el dataset completo.

---

## 3. Fases

### F0: Preparación (1–2 días, solo CPU)

1. Descargar C++1000 y los metadatos de estado.
2. Por problema, tomar ~20 envíos Accepted y ~10 Wrong Answer.
3. Conservar solo los que caben en **una ventana `v2`**: ≤384 tokens de código + 128 de DFG (`models/graphcodebert/config.py:31-32`). Así cada muestra cuesta un solo forward.
4. Dividir por problema (80/10/10).
5. Deduplicar contra ESCOM.
6. Precalcular y cachear las entradas `v2_norm` (código con identificadores canónicos; tokens + DFG).

**Resultado:** manifiesto reproducible (semilla fija) y caché de entradas.

### F1: Línea base y benchmark de velocidad (medio día)

1. Medir `v2_norm` zero-shot en la validación de CodeNet: MAP@R y AUC Accepted vs WA.
2. Medir `v2_norm` zero-shot en ESCOM: E1 y E2. Son las líneas base de H1 y H2.
3. Correr ~200 pasos de entrenamiento y medir **secuencias por segundo reales**. Ese dato reemplaza la estimación de la sección 5.

### F2: Piloto, punto de decisión (1 noche)

- 200 problemas, 1 época.
- LoRA r=16 sobre `query`/`value`, con la **misma entrada y pooling que `v2_norm`**.
- Migrar `models/graphcodebert/contrastive_graphcodebert.py` a la entrada `v2_norm`: hoy usa la codificación legacy, triplet loss y negativos de otro problema.
- **Pérdida:** InfoNCE, temperatura ~0.05.

| Rol | Muestra |
|---|---|
| Ancla | Un envío Accepted |
| Positivo | Otro Accepted del mismo problema |
| Negativo difícil | Un Wrong Answer del mismo problema |
| Negativos fáciles | El resto del batch (otros problemas) |

**Criterio para continuar (fijo):** MAP@R en la validación de CodeNet sube ≥ 0.05 respecto a F1 **y** E1 en ESCOM no baja.
**Si no se cumple:** se detiene el experimento y se reporta como resultado negativo. No se ajustan hiperparámetros hasta que pase.

### F3: Entrenamiento completo con ablación (2–3 noches)

| Configuración | Negativos |
|---|---|
| **A** | Solo Accepted + otros problemas |
| **B** | A + Wrong Answer del mismo problema |

- Descartar los WA casi idénticos a un Accepted (Jaccard > 0.9): un error de una línea no es aprendible y solo agrega ruido.
- 2 semillas por configuración.
- Selección del mejor checkpoint solo con la validación de CodeNet.

### F4: Evaluación final en ESCOM (una sola vez)

- E1, E2 (con referencias del docente) y robustez T1–T7.
- Bootstrap por tarea, como en los reportes anteriores.
- Configuración congelada: no se reentrena ni se recalibra después de ver los resultados.

### F5: Integración (solo si gana)

1. Empaquetar el adaptador en `models/deploy/` con `scripts/build_deploy_artifacts.py` (verificación sha256).
2. Repetir la prueba del backend en modo `REAL`.

---

## 4. Riesgos

| Riesgo | Mitigación |
|---|---|
| Cambio de dominio: CodeNet es programación competitiva (stdin/stdout, nombres en inglés); ESCOM son tareas escolares (menús, structs, nombres en español). | El criterio de F2 incluye E1 en ESCOM. Si gana en CodeNet y no en ESCOM, también es un resultado reportable. |
| Batches chicos en 8 GB debilitan InfoNCE. | Gradient checkpointing; si F2 sale flojo, probar GradCache antes que más épocas, o rentar una GPU con más memoria para F3. |
| Los WA casi idénticos fuerzan al modelo a amplificar diferencias mínimas. | Filtro Jaccard > 0.9 y ablación A vs B. |
| Sobreajuste. | LoRA en lugar de fine-tuning completo; división por problema; selección solo con validación de CodeNet. |

---

## 5. Recursos

### Local: RTX 2060 Super (8 GB, Turing)

Estimación, no medición: modelo tipo RoBERTa-base (125 M parámetros), secuencias de 512 tokens, AMP fp16 (Turing no tiene bf16), LoRA y gradient checkpointing. Se esperan **20–40 secuencias/s**; F1 da el valor real.

| Fase | Volumen | Tiempo estimado |
|---|---|---|
| F0 preprocesamiento DFG (CPU) | ~30 k archivos | 15–40 min |
| F2 piloto | ~15 k tripletas = 45 k secuencias | 20–40 min |
| F3 por corrida | 50 k tripletas × 3 épocas = 450 k secuencias | 3–6 h |
| F3 completo | 2 configuraciones × 2 semillas | 12–24 h |
| F4 evaluación | ESCOM + validación CodeNet | < 30 min |

**Total:** ~15–25 h de GPU; 2–3 semanas de calendario contando preparación y migración del script.

### Nube (opcional, solo F3)

Precios de referencia de octubre de 2026; verificarlos en vivo antes de pagar.

| Servicio | GPU | Precio/h | Velocidad aprox. vs 2060 Super |
|---|---|---|---|
| RunPod Community | RTX 4090 (24 GB) | ~$0.34 | 4–6× |
| RunPod | A100 80 GB | ~$1.19 | 5–8× |

- RTX 4090: ~10 h con margen ≈ 4–7 USD. A100: ~8 h ≈ 10 USD.
- La ventaja principal es la memoria: permite batches de 64–256 sin GradCache.
- Recomendado: F0–F2 en local; F3 en una RTX 4090 on-demand. Evitar instancias interrumpibles sin checkpoints frecuentes y Colab (no garantiza GPU ni sesiones largas).

---

## 6. Checklist

- [ ] F0: manifiesto de CodeNet dividido por problema, deduplicado contra ESCOM, caché `v2_norm` generada.
- [ ] Licencia de CodeNet verificada.
- [ ] F1: líneas base de `v2_norm` registradas (CodeNet val, E1, E2) y velocidad real medida.
- [ ] `contrastive_graphcodebert.py` migrado a la entrada `v2_norm`.
- [ ] F2: criterio de continuación evaluado y registrado (continuar o detener).
- [ ] F3: configuraciones A y B, 2 semillas cada una.
- [ ] Referencias del docente escritas para las 14 tareas de E2.
- [ ] F4: evaluación única en ESCOM con bootstrap; H1–H3 resueltas.
- [ ] F5 (si aplica): adaptador empaquetado en `models/deploy/` y backend probado en modo `REAL`.

## Fuentes

- [IBM/Project_CodeNet (GitHub)](https://github.com/IBM/Project_CodeNet)
- [CodeNet, NeurIPS 2021 Datasets & Benchmarks](https://datasets-benchmarks-proceedings.neurips.cc/paper/2021/file/a5bfc9e07964f8dddeb95fc584cd965d-Paper-round2.pdf)
- [RunPod pricing](https://www.runpod.io/gpu-cloud/pricing)
