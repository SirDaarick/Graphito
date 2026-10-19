# Plan de redacción — Cap. 9 Despliegue (`despliegue.tex`)

**Objetivo:** reescribir el capítulo 9 según `Documentacion/PLAN_ESTRUCTURA_TESIS.md` (sec. 2 Cap. 9 y
sec. 3), con el mismo registro de los Cap. 7 y 8: formal, ligero, para lectores sin formación técnica;
diagramas y tablas antes que párrafos técnicos.

## 1. Diagnóstico (auditoría del 2026-10-17)

- `despliegue.tex` (295 líneas) describe el sistema viejo: LoRA, `BimodalFusion`, vector de 1792
  dimensiones, "dictamen", endpoint `/analysis/evaluate`, tabla de pruebas con cifras sin respaldo
  ("<5.0 s", "FPR<10 %", "<10 s", "<15 ms"), markdown dentro de LaTeX.
- Solo `\label{cap:despliegue}` se referencia desde otro archivo (`modelado.tex`).
- Capturas de pantalla (`reporte_de_similitud.png`, `biblioteca_de_referencias.png`, etc.) son del
  22/09: diseño viejo ("78 % ALTO", "colaboración no declarada"). **Hay que tomarlas de nuevo.**
- Infraestructura: el repo solo respalda Docker (Postgres 16 + Chroma + backend + frontend). Vercel,
  Supabase, servidor con GPU y túnel de Cloudflare **no tienen evidencia en el repo** → confirmar con el autor.
- Validación con docentes: catálogo del plan (guía 03) **no implementado**; sí existe un catálogo
  ESCOM de 124 programas (17/10). Encuesta: **sin instrumento ni resultados** aún.

## 2. Hechos verificados

**Empaquetado (`models/deploy/`)**: `manifest.json` (esquema `graphito.deploy-manifest/v1`) con sha256
por archivo; Canal A = Jaccard (shingles de 5 tokens), calibración isotónica, umbral `fpr_0.05`
(FPR 0.046, TPR 0.845 en validación); Canal B = CharCNN v2 (`best.pth`, 2.96 MB), Platt, umbral
`fpr_0.01` = 0.1715 (FPR 0.0098, TPR 0.971). GraphCodeBERT no se empaqueta: solo huella del pipeline
y revisión fija; rol `secondary_non_deciding`. Lo genera solo `scripts/build_deploy_artifacts.py`,
que se niega si algún sha no coincide; escribe el manifiesto al final (atómico). El modelo legacy
nunca se sobrescribe.

**Decisión en la plataforma**: un único `ScoringService` para análisis individual, asíncrono y por
lote. Canal A decide con **Jaccard máximo contra las referencias** (calibrado, `fpr_0.05`); Canal B
con **CharCNN v2** (`fpr_0.01`; puede abstenerse si el código es muy corto). GraphCodeBERT se calcula
como coseno contra las referencias en Chroma y se muestra rotulado "Exploratorio, zero-shot, no
decide". Función de decisión pura en el dominio → estados: Similitud alta y estilo atípico /
Similitud alta con la referencia / Estilo atípico / Similitud dentro de lo habitual / No evaluable /
Sin referencia. Umbrales enviados por el cliente se ignoran.

**Por qué Jaccard decide**: resultado del Cap. 8 (Jaccard 0.945 vs GraphCodeBERT 0.856 en pares de
plagio; GraphCodeBERT sensible al renombrado y sin umbral `fpr_0.01` alcanzable). El coseno de
GraphCodeBERT se conserva como información de similitud lógica (cumple el objetivo de "similitud del
coseno") pero no dispara alertas.

**Inferencia**: los tres cálculos corren en paralelo y en hilos aparte para no bloquear la API;
colección de Chroma por versión de modelo (`gcb_{versión}_{pooling}_{huella}`); reindexado con
`scripts/reindex_references.py` (simulación por defecto, `--apply` escribe).

**Falla segura**: `/health` informa `inference_ready`, motor, estado de calibración y sha de cada
artefacto. Si un artefacto no coincide → `inference_ready=false` y las rutas de análisis responden
503 "no se analizó ni se guardó nada". El modo de prueba (STUB) solo existe si se pide explícitamente;
en producción nunca se usa en silencio. `ALLOW_UNCALIBRATED` prohibido en producción.

**Presentación al docente**: etiquetas neutras (lista arriba); aviso "apoya la revisión; la
evaluación final corresponde al docente"; umbrales, motor, estado de calibración, versión de modelo y
leyenda "No validado contra plagio derivado de la referencia" en cada reporte.

**Pruebas**: 1,412 pruebas recolectadas hoy (al cierre de la integración: 1,307 aprobadas, 1 omitida);
frontend: 58 pruebas vitest + lint + typecheck + build. E2E en modo REAL con Docker: `/health` listo
con sha por canal; migraciones aplicadas dos veces sin error; reindexado idempotente; análisis
individual y por lote idénticos; artefacto alterado → 503 sin escribir filas
(`sdd/archive/2026-10-11-backend-model-integration/verify-report.md`).

## 3. Estructura propuesta

### Introducción
Ubicación en Komorebi (última fase). Mapa del capítulo. **Fig. 9.1 (TikZ)**: del modelo entrenado
al docente (paquete verificado → servidor → análisis → reporte → docente decide).

### 9.1 Despliegue de modelos
1. **Empaquetado y verificación** — analogía: "medicamento con sello de garantía". **Fig. (TikZ)**:
   corrida en `runs/` → script de empaquetado → paquete con huellas sha256 → la plataforma verifica
   al arrancar. **Tabla**: qué se despliega (Canal A Jaccard, Canal B CharCNN v2, GraphCodeBERT
   exploratorio) | umbral | rol.
2. **Cómo decide la plataforma** — por qué decide Jaccard (remitir al Cap. 8). **Tabla 2×2**:
   ¿similitud alta? × ¿estilo atípico? → etiqueta mostrada. Información, no veredicto.
3. **Flujo de un análisis** — **Fig. (TikZ, secuencia simple)**: docente sube entrega → se normaliza →
   tres cálculos en paralelo (Jaccard, GraphCodeBERT, CharCNN) → decisión → se guarda → reporte.
   Una frase sobre análisis individual, asíncrono y por lote con el mismo servicio.
4. **Falla segura** — **Tabla**: situación → qué hace el sistema (artefacto alterado, modelo no
   cargado, código demasiado corto, sin referencia). Analogía: "mejor no responder que responder mal".
5. **Arquitectura e infraestructura** — reutilizar o simplificar el diagrama TikZ existente según la
   respuesta del autor (ver pendiente). Arquitectura limpia en un párrafo + remitir al Cap. 6.
6. **Presentación al docente** — capturas nuevas del reporte y del catálogo (pendiente del autor);
   tabla con lo que muestra cada reporte (etiqueta, similitudes, umbral, versión de modelo, aviso).

### 9.2 Monitorización de los modelos
1. **Pruebas automatizadas** — tabla por tipo de prueba (qué verifica en palabras simples) con
   números verificados; sin cifras de tiempo no medidas.
2. **Prueba de extremo a extremo en modo real** — tabla: comprobación | resultado.
3. **Métricas en operación** — `/health`, versión de modelo y umbral en cada reporte (trazabilidad),
   estado de calibración visible.
4. **Validación con docentes** — método completo según sec. 3 del plan general (objetivo, catálogo
   ESCOM de 124 programas, instrumento SUS + Likert TAM + tiempo, participantes, ética, análisis).
   **Resultados: marcador `% TODO resultados de la encuesta`** con la estructura de tablas lista
   (SUS media e intervalo; mediana/RIC por ítem; distribución de ahorro estimado) y limitaciones.

### Conclusión
Resumen y puente al Cap. 10.

## 4. Pendientes del autor
- ~~Confirmar la infraestructura real~~ → el autor confirmó (2026-10-17): Vercel (frontend),
  Supabase (PostgreSQL), servidor con GPU y túnel de Cloudflare; la configuración no está en el repo.
  No afirmar tiempos ni aceleración por GPU sin medición.
- Capturas nuevas de la interfaz (reporte de similitud, catálogo, biblioteca).
- Resultados de la encuesta (20–28 oct).

## 5. Tareas
- [x] T1 Auditoría y plan
- [x] T2 Redacción — delegado (Sonnet)
  - Verificación: begin/end y llaves balanceados; todos los `\ref` y `\cite` existen; sin `\includegraphics`; sin términos prohibidos. `pdflatex` no está en PATH: **no compilado**.
  - Pendientes: 2 capturas (`fig:captura_reporte`, `fig:captura_catalogo`, marcadas `% TODO captura`) y resultados de la encuesta (`% TODO resultados de la encuesta`, 3 tablas vacías).
  - Bib: añadidos `Brooke1996SUS` (editores/editorial de memoria; páginas 189--194 confirmadas) y `Davis1989TAM` (DOI 10.2307/249008 confirmado). Cap. 6 no tiene `\label{cap:...}`, se cita sin `\ref`.
- [ ] T3 Revisión
