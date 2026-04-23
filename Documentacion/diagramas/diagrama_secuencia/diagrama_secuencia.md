sequenceDiagram
    autonumber
    actor P as Profesor
    participant UI as Interfaz (React/TS)
    participant B as Backend (FastAPI)
    participant O as Orquestador (LangGraph)
    participant DB as Bases de Datos (Relacional/Vectorial)
    participant LLM as API LLM Externa
    participant IA_S as Módulo semántico (GraphCodeBERT)
    participant IA_A as Módulo estilométrico (CharCNN)

    Note over P, DB: Fase 1: Configuración de Referencia
    
    P->>UI: Define problema y restricciones
    UI->>B: POST /configurar-problema
    B->>O: Iniciar flujo de preparación
    
    O->>DB: ¿Existen soluciones previas? (Hash)
    
    alt Caso: No existen en Base de Datos
        O->>LLM: Solicitar variantes funcionalmente equivalentes
        LLM-->>O: Retorno de códigos sintéticos (.cpp)
        loop Por cada variante generada
            O->>IA_S: Generar Embedding Semántico
            IA_S-->>O: Vector de características
            O->>DB: Guardar en ChromaDB (Indexación)
        end
    else Caso: Ya existen
        O->>DB: Recuperar embeddings de referencia
        DB-->>O: Vectores listos
    end
    O-->>B: Estado: Referencia Lista
    B-->>UI: Confirmación de configuración

    Note over P, IA_A: Fase 2: Análisis de Entrega (Evaluación de Alumno)
    
    P->>UI: Carga código del alumno (.cpp)
    UI->>B: POST /analizar-entrega
    activate B
    
    B->>O: Orquestar análisis bimodal
    
    par Inferencia en Paralelo
        O->>IA_S: Generar Embedding (Semantic)
        IA_S-->>O: Vector Alumno
        O->>IA_A: Analizar Autoría (Style)
        IA_A-->>O: Probabilidad de autoría (%)
    end

    %% --- PASO AGREGADO: FEATURE FUSION ---
    O->>O: Fusión de Características (Feature Fusion)

    %% -------------------------------------

    Note over O, DB: Fase 3: Cálculo de Similitud y Persistencia
    
    O->>DB: Buscar vectores de referencia en ChromaDB 
    DB-->>O: Score de Similitud del Coseno
    
    O->>O: Consolidar reporte (Bimodal)
    
    O->>DB: Guardar reporte final en PostgreSQL
    O-->>B: Datos del reporte
    
    B-->>UI: 200 OK (Reporte Generado)
    deactivate B
    UI->>P: Visualiza resultados en Dashboard