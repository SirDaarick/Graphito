# 📚 Guías de Implementación Arquitectónica — Graphito

Este directorio reúne las **10 especificaciones técnicas de diseño e implementación** para la evolución funcional y algorítmica de **Graphito** (Sistema de Apoyo a la Decisión Docente para Integridad Académica en C/C++).

Cada guía ha sido formulada bajo principios de **Clean Architecture**, patrones de diseño consolidados, buenas prácticas en TypeScript/React y FastAPI/PostgreSQL, y el principio ético fundamental de **Human-in-the-Loop**.

---

## 🗄️ Estado y Migración de la Base de Datos

Las entidades de dominio y modelos SQLAlchemy ya se encuentran actualizados en:
👉 [`backend/app/infrastructure/database/models.py`](file:///c:/Users/edani/OneDrive/Documents/Proyectos/Graphito/backend/app/infrastructure/database/models.py)

### ¿Cómo aplicar los cambios a la base de datos PostgreSQL?

Dado que `Base.metadata.create_all` en SQLAlchemy solo crea tablas nuevas y **no altera tablas existentes**, se han preparado dos mecanismos inmediatos:

#### Opción 1: Ejecutar el script automatizado en Python (Recomendado)
Desde la raíz del proyecto o dentro del contenedor del backend:
```bash
python backend/apply_migrations.py
```
*Este script se conecta mediante el motor asíncrono configurado en `.env` y aplica el script DDL de forma idempotente.*

#### Opción 2: Ejecutar el script SQL directo en PostgreSQL
Si utilizas DBeaver, pgAdmin o `docker exec`:
```bash
docker exec -i graphito-postgres psql -U graphito -d graphito_db < backend/migrations/migration_features.sql
```
El archivo de migración con las sentencias DDL se encuentra en:
👉 [`backend/migrations/migration_features.sql`](file:///c:/Users/edani/OneDrive/Documents/Proyectos/Graphito/backend/migrations/migration_features.sql)

---

## 🗺️ Índice Maestro de Guías y Estado de Implementación

| # | Módulo / Funcionalidad | Estado | ¿Modifica DB? | Área de Impacto | Documento |
|---|------------------------|:------:|:-------------:|-----------------|-----------|
| **01** | **Modo Claro / Oscuro** | ✅ **Implementada** | ❌ No | Frontend / Tokens CSS | [01_modo_claro_oscuro.md](./01_modo_claro_oscuro.md) |
| **02** | **Autenticación con Google** | ✅ **Implementada** | ✅ **SÍ** | Backend & Frontend (OAuth2/OIDC) | [02_autenticacion_google.md](./02_autenticacion_google.md) |
| **03** | **Banco de Tareas Precargadas** | ⏳ **Pendiente** | ✅ **SÍ** | Persistencia / Onboarding | [03_banco_tareas_precargadas.md](./03_banco_tareas_precargadas.md) |
| **04** | **Grupos y Cursos Académicos** | ✅ **Implementada** | ✅ **SÍ** | Modelo Relacional / UI | [04_grupos_y_cursos.md](./04_grupos_y_cursos.md) |
| **05** | **Carga Masiva & Background Pipeline** | ✅ **Implementada** | ✅ **SÍ** | Inferencia Asíncrona / UX | [05_carga_masiva_background.md](./05_carga_masiva_background.md) |
| **06** | **Visualizador Diff & Anotaciones** | ✅ **Implementada** | ✅ **SÍ** | Monaco Editor / Feedback | [06_visualizador_diff_comentarios.md](./06_visualizador_diff_comentarios.md) |
| **07** | **Botones de Triaje Docente** | ✅ **Implementada** | ✅ **SÍ** | Human-in-the-Loop / DB | [07_triaje_docente_decision.md](./07_triaje_docente_decision.md) |
| **08** | **Navegación Ágil (Avance Automático)** | ✅ **Implementada** | ❌ No | UX / Flujo de Revisión | [08_navegacion_agil_autoscroll.md](./08_navegacion_agil_autoscroll.md) |
| **09** | **Mejora de Modelos & Benchmark** | 🔄 **Fase 1 Lista / Fases 2-4 Plan.** | ⚠️ Mínimo | ML / GraphCodeBERT / CharCNN | [09_mejora_modelos_benchmark.md](./09_mejora_modelos_benchmark.md) & [Reporte de Auditoría](../informes/REPORTE_MEJORA_MODELOS_ML.md) |
| **10** | **Interpretabilidad en UI (XAI)** | ✅ **Implementada** | ✅ **SÍ** | Explainable AI / Visualización | [10_interpretabilidad_xai_ui.md](./10_interpretabilidad_xai_ui.md) |

---

## 🏗️ Estado de Avance en la Hoja de Ruta

### 🔹 Fase 1: Cimientos del Negocio y Adopción Inicial
- [ ] ⏳ **[Guía 03: Banco de Tareas Precargadas](./03_banco_tareas_precargadas.md)** — Catálogo de plantillas maestras para mitigar el síndrome del lienzo en blanco (*Cold Start*).
- [x] ✅ **[Guía 04: Grupos y Cursos Académicos](./04_grupos_y_cursos.md)** — Entidades `Grupo` y `GrupoProblema`, endpoints en `/api/v1/groups`, filtros reactivos en biblioteca y modal de asignación.
- [x] ✅ **[Guía 07: Botones de Triaje Docente](./07_triaje_docente_decision.md)** — Calificación expedita HITL (`APROBADO`, `RECHAZADO`, `EN_DUDA`), persistencia en base de datos y feedback visual.
- [x] ✅ **[Guía 08: Navegación Ágil](./08_navegacion_agil_autoscroll.md)** — Cola de revisión secuencial en `SimilarityReportModal`, animaciones GSAP y auto-avance tras veredicto.

### 🔹 Fase 2: Flujo Operativo y Productividad Docente
- [x] ✅ **[Guía 05: Carga Masiva y Pipeline en Background](./05_carga_masiva_background.md)** — Subida de archivos ZIP/múltiples, parsing determinista de nombres de alumno, `batch_analysis_service.py` y barra de progreso reactiva.
- [x] ✅ **[Guía 06: Visualizador Diff y Anotaciones](./06_visualizador_diff_comentarios.md)** — Comparador Side-by-Side con tema Synthwave '84, numeración sincronizada y comentarios pedagógicos persistidos.
- [x] ✅ **[Guía 02: Autenticación con Google](./02_autenticacion_google.md)** — Integración con Google Identity Services popup, `/api/v1/auth/google`, verificación JWT y creación automática de cuenta.

### 🔹 Fase 3: Inteligencia Artificial Explicable, Rigor Científico y Ergonomía
- [x] ✅ **[Guía 10: Interpretabilidad en la UI (XAI)](./10_interpretabilidad_xai_ui.md)** — Cajón de evidencias periciales (`EvidenceDrawer.tsx`), badges por categoría (Flujo DFG, Patrón LLM, Construcción Avanzada) y salto a número de línea.
- [x] 🔄 **[Guía 09: Mejora de Modelos y Benchmark](./09_mejora_modelos_benchmark.md)** — **Fase 1 completada y validada** (salvaguarda CharCNN $<60$ chars, LoRA 20k fusionado, máscara float32 DFG, calibración logística sigmoidal suave, 47/47 tests unitarios pasando). Fases 2 a 4 estructuradas en el **[Reporte de Auditoría Técnica](../informes/REPORTE_MEJORA_MODELOS_ML.md)**.
- [x] ✅ **[Guía 01: Modo Claro / Oscuro](./01_modo_claro_oscuro.md)** — Arquitectura de tokens CSS en `index.css`, `ThemeContext.tsx` y botón toggle accesible en `Header.tsx`.

---

## 📌 Principios de Arquitectura que Rigen Estas Guías
* **Conceptos > Código:** No se implementa una librería sin entender qué problema resuelve ni qué deuda técnica introduce.
* **Separación de Responsabilidades:** El backend en FastAPI mantiene Clean Architecture (Domain $\to$ Application $\to$ Infrastructure $\to$ Presentation). La lógica de negocio no reside en los controladores de ruta.
* **Human-in-the-Loop:** La IA emite probabilidades y sugerencias orientadoras; el docente siempre emite el veredicto final.
