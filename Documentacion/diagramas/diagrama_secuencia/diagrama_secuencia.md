sequenceDiagram
    autonumber
    actor P as Profesor
    participant UI as Interfaz (React)
    participant B as Backend (FastAPI)
    participant DBR as DB Relacional (Postgres)
    participant DBV as ChromaDB (Vectorial)
    participant LLM as External LLM API
    participant IA as Motor IA (Modelos)

    Note over P, DBR: Fase de Configuración de Referencia
    
    alt Opción A: Seleccionar de Biblioteca
        P->>UI: Selecciona problema existente
        UI->>B: GET /problema/{id}
        B->>DBR: obtener_detalles(id)
        B->>DBV: recuperar_embeddings_referencia(id)
        DBV-->>B: vectores_referencia
    else Opción B: Cargar Referencia Nueva
        P->>UI: Sube código y describe problema
        UI->>B: POST /configurar-problema
        activate B
        B->>DBR: verificar_existencia_metadatos(hash)
        
        alt Caso: Es nuevo y no existe en BD
            B->>LLM: generar_variantes(enunciado, instrucciones)
            LLM-->>B: retorno_codigos_sinteticos
            B->>IA: procesar_variantes(codigos)
            IA-->>B: embeddings_sinteticos
            B->>DBV: guardar_referencia_y_variantes(id, embeddings)
        else Caso: Ya existía en BD (Duplicado)
            B->>DBV: recuperar_embeddings_existentes(id)
            DBV-->>B: vectores_referencia
        end
        deactivate B
    end

    Note over P, IA: Fase de Análisis de Entregas (Alumnos)
    P->>UI: Carga código del alumno para comparar
    UI->>B: POST /analizar-entrega
    activate B
    
    B->>B: Pre-procesamiento y Normalización
    
    B->>IA: ejecutar_inferencia_bimodal(codigo_alumno)
    activate IA
    par Inferencia Paralela
        IA->>IA: Análisis Estilométrico (CharCNN)
        IA->>IA: Representación Semántica (GraphCodeBERT)
    end
    Note right of IA: Fusión de Características (769 Dim)
    IA-->>B: vector_alumno_fusionado
    deactivate IA

    Note over B, DBV: Fase de Similitud y Persistencia
    B->>B: Calcular Similitud del Coseno (Vector Alumno vs Referencia)
    B->>IA: interpretar_probabilidad_plagio(score)
    IA-->>B: veredicto_y_alertas
    
    B->>DBR: guardar_reporte_analisis(id_entrega, scores, alertas)
    B->>DBV: guardar_vector_alumno(vector_769)
    
    B-->>UI: 200 OK (Reporte Generado)
    deactivate B
    UI->>P: Visualiza Dashboard de resultados