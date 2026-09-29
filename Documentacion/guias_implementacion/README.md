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

## 🗺️ Índice Maestro de Guías

| # | Módulo / Funcionalidad | ¿Modifica DB? | Área de Impacto | Documento |
|---|------------------------|:-------------:|-----------------|-----------|
| **01** | **Modo Claro / Oscuro** | ❌ No | Frontend / Tokens CSS | [01_modo_claro_oscuro.md](./01_modo_claro_oscuro.md) |
| **02** | **Autenticación con Google** | ✅ **SÍ** | Backend & Frontend (OAuth2/OIDC) | [02_autenticacion_google.md](./02_autenticacion_google.md) |
| **03** | **Banco de Tareas Precargadas** | ✅ **SÍ** | Persistencia / Onboarding | [03_banco_tareas_precargadas.md](./03_banco_tareas_precargadas.md) |
| **04** | **Grupos y Cursos Académicos** | ✅ **SÍ** | Modelo Relacional / UI | [04_grupos_y_cursos.md](./04_grupos_y_cursos.md) |
| **05** | **Carga Masiva & Background Pipeline** | ✅ **SÍ** | Inferencia Asíncrona / UX | [05_carga_masiva_background.md](./05_carga_masiva_background.md) |
| **06** | **Visualizador Diff & Anotaciones** | ✅ **SÍ** | Monaco Editor / Feedback | [06_visualizador_diff_comentarios.md](./06_visualizador_diff_comentarios.md) |
| **07** | **Botones de Triaje Docente** | ✅ **SÍ** | Human-in-the-Loop / DB | [07_triaje_docente_decision.md](./07_triaje_docente_decision.md) |
| **08** | **Navegación Ágil (Avance Automático)** | ❌ No | UX / Flujo de Revisión | [08_navegacion_agil_autoscroll.md](./08_navegacion_agil_autoscroll.md) |
| **09** | **Mejora de Modelos & Benchmark** | ⚠️ Mínimo | ML / GraphCodeBERT / CharCNN | [09_mejora_modelos_benchmark.md](./09_mejora_modelos_benchmark.md) |
| **10** | **Interpretabilidad en UI (XAI)** | ✅ **SÍ** | Explainable AI / Visualización | [10_interpretabilidad_xai_ui.md](./10_interpretabilidad_xai_ui.md) |

---

## 🏗️ Hoja de Ruta Recomendada de Ejecución

Para evitar refactorizaciones innecesarias y construir sobre cimientos sólidos, se recomienda seguir el siguiente orden secuencial:

### 🔹 Fase 1: Cimientos del Negocio y Adopción Inicial
1. **[Guía 03: Banco de Tareas Precargadas](./03_banco_tareas_precargadas.md)** — Resuelve el problema del lienzo en blanco para que cualquier profesor nuevo pruebe la plataforma inmediatamente.
2. **[Guía 04: Grupos y Cursos Académicos](./04_grupos_y_cursos.md)** — Establece la estructura relacional correcta antes de acumular cientos de entregas.
3. **[Guía 07: Botones de Triaje Docente](./07_triaje_docente_decision.md)** y **[Guía 08: Navegación Ágil](./08_navegacion_agil_autoscroll.md)** — Convierten la revisión docente en un proceso rápido y fluido con etiquetas de verdad fundamental (*ground truth*).

### 🔹 Fase 2: Flujo Operativo y Productividad Docente
4. **[Guía 05: Carga Masiva y Pipeline en Background](./05_carga_masiva_background.md)** — Permite evaluar salones enteros de 30-50 alumnos sin provocar caídas por timeout.
5. **[Guía 06: Visualizador Diff y Anotaciones](./06_visualizador_diff_comentarios.md)** — Permite cotejar los códigos cara a cara con soporte de comentarios.
6. **[Guía 02: Autenticación con Google](./02_autenticacion_google.md)** — Habilita inicio de sesión institucional sin fricción de contraseñas.

### 🔹 Fase 3: Inteligencia Artificial Explicable, Rigor Científico y Ergonomía
7. **[Guía 10: Interpretabilidad en la UI (XAI)](./10_interpretabilidad_xai_ui.md)** — Transforma los porcentajes numéricos en evidencias pedagógicas concretas y visuales.
8. **[Guía 09: Mejora de Modelos y Benchmark](./09_mejora_modelos_benchmark.md)** — Evalúa y refina la robustez de los canales A y B frente a reformateadores de código y variantes sintéticas.
9. **[Guía 01: Modo Claro / Oscuro](./01_modo_claro_oscuro.md)** — Cierra el ciclo con ergonomía visual consolidada basada en variables semánticas.

---

## 📌 Principios de Arquitectura que Rigen Estas Guías
* **Conceptos > Código:** No se implementa una librería sin entender qué problema resuelve ni qué deuda técnica introduce.
* **Separación de Responsabilidades:** El backend en FastAPI mantiene Clean Architecture (Domain $\to$ Application $\to$ Infrastructure $\to$ Presentation). La lógica de negocio no reside en los controladores de ruta.
* **Human-in-the-Loop:** La IA emite probabilidades y sugerencias orientadoras; el docente siempre emite el veredicto final.
