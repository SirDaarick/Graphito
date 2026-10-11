-- ==============================================================================
-- MIGRACIÓN DE BASE DE DATOS: CARACTERÍSTICAS NUEVAS (GRAPHITO)
-- Compatible con PostgreSQL 14+ / Docker Compose (graphito_db)
-- ==============================================================================

-- 1. SOPORTE PARA AUTH CON GOOGLE (OAuth 2.0 / OIDC)
ALTER TABLE docentes ALTER COLUMN hashed_password DROP NOT NULL;
ALTER TABLE docentes ADD COLUMN IF NOT EXISTS google_id VARCHAR(255) UNIQUE;
ALTER TABLE docentes ADD COLUMN IF NOT EXISTS avatar_url VARCHAR(512);
CREATE INDEX IF NOT EXISTS ix_docentes_google_id ON docentes(google_id);

-- 2. BANCO DE TAREAS PRECARGADAS (PLANTILLAS CANÓNICAS)
ALTER TABLE problemas ALTER COLUMN docente_id DROP NOT NULL;
ALTER TABLE problemas ADD COLUMN IF NOT EXISTS es_plantilla BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE problemas ADD COLUMN IF NOT EXISTS dificultad VARCHAR(50) DEFAULT 'Principiante';
CREATE INDEX IF NOT EXISTS ix_problemas_es_plantilla ON problemas(es_plantilla);

-- 3. GRUPOS Y ASIGNACIONES ACADÉMICAS
CREATE TABLE IF NOT EXISTS grupos (
    id SERIAL PRIMARY KEY,
    docente_id INTEGER NOT NULL REFERENCES docentes(id) ON DELETE CASCADE,
    nombre VARCHAR(150) NOT NULL,
    codigo_grupo VARCHAR(50) NOT NULL,
    periodo VARCHAR(50) NOT NULL,
    descripcion TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_grupos_docente_id ON grupos(docente_id);

CREATE TABLE IF NOT EXISTS grupo_problemas (
    id SERIAL PRIMARY KEY,
    grupo_id INTEGER NOT NULL REFERENCES grupos(id) ON DELETE CASCADE,
    problema_id INTEGER NOT NULL REFERENCES problemas(id) ON DELETE CASCADE,
    fecha_limite TIMESTAMP WITH TIME ZONE,
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_grupo_problema UNIQUE (grupo_id, problema_id)
);
CREATE INDEX IF NOT EXISTS ix_grupo_problemas_grupo_id ON grupo_problemas(grupo_id);
CREATE INDEX IF NOT EXISTS ix_grupo_problemas_problema_id ON grupo_problemas(problema_id);

ALTER TABLE codigos_fuente ADD COLUMN IF NOT EXISTS grupo_id INTEGER REFERENCES grupos(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS ix_codigos_fuente_grupo_id ON codigos_fuente(grupo_id);

-- 4. CONTROL DE LOTES PARA CARGA MASIVA EN SEGUNDO PLANO
CREATE TABLE IF NOT EXISTS lotes_analisis (
    id UUID PRIMARY KEY,
    problema_id INTEGER NOT NULL REFERENCES problemas(id) ON DELETE CASCADE,
    docente_id INTEGER NOT NULL REFERENCES docentes(id) ON DELETE CASCADE,
    total_archivos INTEGER NOT NULL DEFAULT 0,
    procesados INTEGER NOT NULL DEFAULT 0,
    errores INTEGER NOT NULL DEFAULT 0,
    estado VARCHAR(50) NOT NULL DEFAULT 'PENDIENTE',
    grupo_id INTEGER REFERENCES grupos(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_lotes_docente_id ON lotes_analisis(docente_id);
CREATE INDEX IF NOT EXISTS ix_lotes_problema_id ON lotes_analisis(problema_id);
CREATE INDEX IF NOT EXISTS ix_lotes_grupo_id ON lotes_analisis(grupo_id);

ALTER TABLE reportes_analisis ADD COLUMN IF NOT EXISTS lote_id UUID REFERENCES lotes_analisis(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS ix_reportes_lote_id ON reportes_analisis(lote_id);

-- 5. TRIAJE DOCENTE (HUMAN-IN-THE-LOOP)
DO $$ BEGIN
    CREATE TYPE decisiondocenteenum AS ENUM ('PENDIENTE', 'APROBADO', 'RECHAZADO', 'EN_DUDA');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

ALTER TABLE reportes_analisis ADD COLUMN IF NOT EXISTS decision_docente decisiondocenteenum NOT NULL DEFAULT 'PENDIENTE';
ALTER TABLE reportes_analisis ADD COLUMN IF NOT EXISTS fecha_decision TIMESTAMP WITH TIME ZONE;
ALTER TABLE reportes_analisis ADD COLUMN IF NOT EXISTS notas_docente TEXT;
CREATE INDEX IF NOT EXISTS ix_reportes_decision_docente ON reportes_analisis(decision_docente);

-- 6. COMENTARIOS Y ANOTACIONES EN EL CÓDIGO
CREATE TABLE IF NOT EXISTS comentarios_revision (
    id SERIAL PRIMARY KEY,
    reporte_id INTEGER NOT NULL REFERENCES reportes_analisis(id) ON DELETE CASCADE,
    docente_id INTEGER NOT NULL REFERENCES docentes(id) ON DELETE CASCADE,
    numero_linea INTEGER,
    contenido TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_comentarios_reporte_id ON comentarios_revision(reporte_id);
CREATE INDEX IF NOT EXISTS ix_comentarios_docente_id ON comentarios_revision(docente_id);

-- 7. INTERPRETABILIDAD Y EXPLICABILIDAD (XAI)
ALTER TABLE indicadores_integridad ADD COLUMN IF NOT EXISTS numero_linea INTEGER;
ALTER TABLE indicadores_integridad ADD COLUMN IF NOT EXISTS categoria VARCHAR(50) DEFAULT 'GENERAL';

-- 8. INTEGRACIÓN DE MODELOS (SDD-4): puntajes anulables, procedencia y dictámenes nuevos
-- apply_migrations.py ejecuta cada sentencia sola en AUTOCOMMIT y se detiene en el primer error.
-- ADD VALUE va fuera de un bloque de transacción (requisito de PostgreSQL).
ALTER TYPE dictamenenum ADD VALUE IF NOT EXISTS 'NO_EVALUABLE';
ALTER TYPE dictamenenum ADD VALUE IF NOT EXISTS 'SIN_REFERENCIA';
-- NULL significa "no evaluado", nunca 0 (dictamen NULL mientras PENDIENTE/PROCESANDO/ERROR).
ALTER TABLE reportes_analisis ALTER COLUMN similitud_semantica DROP NOT NULL;
ALTER TABLE reportes_analisis ALTER COLUMN probabilidad_ia DROP NOT NULL;
ALTER TABLE reportes_analisis ALTER COLUMN discrepancia_score DROP NOT NULL;
ALTER TABLE reportes_analisis ALTER COLUMN dictamen DROP NOT NULL;
ALTER TABLE reportes_analisis ADD COLUMN IF NOT EXISTS engine VARCHAR(20);
ALTER TABLE reportes_analisis ADD COLUMN IF NOT EXISTS canal_a_metodo VARCHAR(30);
ALTER TABLE reportes_analisis ADD COLUMN IF NOT EXISTS estado_canal_a VARCHAR(30);
ALTER TABLE reportes_analisis ADD COLUMN IF NOT EXISTS estado_canal_b VARCHAR(30);
ALTER TABLE reportes_analisis ADD COLUMN IF NOT EXISTS flag_a BOOLEAN;
ALTER TABLE reportes_analisis ADD COLUMN IF NOT EXISTS flag_b BOOLEAN;
ALTER TABLE reportes_analisis ADD COLUMN IF NOT EXISTS umbral_a DOUBLE PRECISION;
ALTER TABLE reportes_analisis ADD COLUMN IF NOT EXISTS umbral_b DOUBLE PRECISION;
ALTER TABLE reportes_analisis ADD COLUMN IF NOT EXISTS puntaje_calibrado_a DOUBLE PRECISION;
ALTER TABLE reportes_analisis ADD COLUMN IF NOT EXISTS calibracion_sha_a VARCHAR(64);
ALTER TABLE reportes_analisis ADD COLUMN IF NOT EXISTS calibracion_sha_b VARCHAR(64);
ALTER TABLE reportes_analisis ADD COLUMN IF NOT EXISTS checkpoint_sha_b VARCHAR(64);
ALTER TABLE reportes_analisis ADD COLUMN IF NOT EXISTS manifest_sha VARCHAR(64);
ALTER TABLE reportes_analisis ADD COLUMN IF NOT EXISTS gcb_similarity DOUBLE PRECISION;
ALTER TABLE reportes_analisis ADD COLUMN IF NOT EXISTS gcb_estado VARCHAR(20);
-- Filas previas: procedencia "legacy"; sus puntajes no se tocan ni se recalculan.
UPDATE reportes_analisis SET engine = 'legacy' WHERE engine IS NULL;
