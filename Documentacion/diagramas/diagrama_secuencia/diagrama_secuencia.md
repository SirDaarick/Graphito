%%{init: { 'themeVariables': { 'fontSize': '16px', 'actorFontSize': '18px', 'messageFontSize': '16px', 'noteFontSize': '16px' } } }%%
sequenceDiagram
    autonumber
    
    actor P as Docente
    participant UI as Interfaz<br/>(React)
    participant B as Backend<br/>(FastAPI)
    participant O as Orquestador<br/>(LangGraph)
    participant DB as Bases de Datos<br/>(PG/Chroma)
    participant LLM as API LLM<br/>Externa
    participant IA_S as Canal Semántico<br/>(GraphCodeBERT)
    participant IA_A as Canal Estilométrico<br/>(CharCNN)

    Note over P, DB: Fase 1: Configuración de Referencias
    
    P->>UI: Define problema<br/>y restricciones
    UI->>B: POST /configurar-problema
    B->>O: Iniciar flujo<br/>de configuración
    
    O->>DB: ¿Existen soluciones<br/>previas? (Hash)
    
    alt Caso: No existen en BD
        O->>LLM: Solicitar variantes<br/>equivalentes
        LLM-->>O: Retorno de<br/>códigos sintéticos
        loop Por cada variante
            O->>IA_S: Extraer Embedding<br/>Semántico
            IA_S-->>O: Vector lógico
            O->>DB: Indexar en<br/>ChromaDB
        end
    else Caso: Ya existen
        O->>DB: Recuperar embeddings<br/>de referencia
        DB-->>O: Vectores listos
    end
    O-->>B: Estado: Referencia Lista
    B-->>UI: Confirmación de<br/>configuración

    Note over P, IA_A: Fase 2: Análisis de Entrega (Doble Canal)
    
    P->>UI: Carga archivo<br/>a analizar (.cpp)
    UI->>B: POST /analizar-entrega
    activate B
    
    B->>O: Orquestar análisis<br/>híbrido
    
    par Inferencia en Paralelo
        O->>IA_S: Extraer Embedding<br/>(Semántica)
        IA_S-->>O: Vector Estructural
        O->>IA_A: Analizar Origen<br/>(Estilometría)
        IA_A-->>O: Prob. de generación<br/>sintética (%)
    end

    %% --- FEATURE FUSION ---
    O->>O: Fusión de Características<br/>(Feature Fusion)
    %% -------------------------------------

    Note over O, DB: Fase 3: Consolidación y Persistencia
    
    O->>DB: Buscar referencias<br/>en ChromaDB 
    DB-->>O: Índice de Similitud<br/>del Coseno
    
    O->>O: Consolidar reporte<br/>dual
    
    O->>DB: Guardar metadatos<br/>en PostgreSQL
    O-->>B: Datos del reporte
    
    B-->>UI: 200 OK<br/>(Reporte Generado)
    deactivate B
    UI->>P: Visualiza indicadores<br/>en Dashboard