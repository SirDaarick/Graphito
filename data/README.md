# Scripts de Generación de Referencias IA

Scripts para generar versiones de código mediante LLMs para enriquecer el dataset de plagio académico.

## Estructura

```
data/
├── config.py                  # Configuración centralizada
├── modelos.py               # Abstracción de LLMs
├── extraer_enunciados.py     # Extrae enunciados del dataset
├── generar_referencias.py # Genera versiones IA
├── estadisticas.py         # Estadísticas
├── enunciados.csv         # Enunciados inferidos (generado)
└── output/                # Referencias generadas
```

---

## Requisitos

```bash
pip install openai anthropic requests
```

Configurar variables de entorno:
```bash
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-..."
```

---

## 1. Configuración (`config.py`)

### Modelos Disponibles

```python
MODELS = {
    "gpt-4o-mini": {"provider": "openai", "model": "gpt-4o-mini"},
    "gpt-4o": {"provider": "openai", "model": "gpt-4o"},
    "claude-3-haiku": {"provider": "anthropic", "model": "claude-3-haiku-20240307"},
    "claude-3-sonnet": {"provider": "anthropic", "model": "claude-3-sonnet-20240229"},
    "ollama-codellama": {"provider": "ollama", "model": "codellama"},
    "ollama-llama3": {"provider": "ollama", "model": "llama3"},
}
```

### Agregar Nuevo Modelo

```python
"mi-modelo": {"provider": "openai", "model": "mi-modelo-especifico"},
```

O con Ollama:
```python
"ollama-mi-modelo": {"provider": "ollama", "model": "mi-modelo"},
```

---

## 2. Extraer Enunciados (`extraer_enunciados.py`)

Infiere los enunciados/tareas del dataset analizando códigos de estudiantes.

### Uso

```bash
# Con modelo por defecto
python extraer_enunciados.py

# Con modelo específico
python extraer_enunciados.py --model ollama-codellama

# Especificar número de muestras
python extraer_enunciados.py --num-samples 3

# Forzar sobrescribir
python extraer_enunciados.py --force
```

### Salida

Genera `enunciados.csv`:
```csv
curso,carpeta,subcarpeta,enunciado,lenguaje
A2016,Z1,Z1,Ordenamiento burbuja,C
A2016,Z1,Z2,Buscar máximo en arreglo,C
```

### Parámetros

| Parámetro | Descripción | Default |
|-----------|-------------|---------|
| `--model` | Modelo LLM a usar | `gpt-4o-mini` |
| `--output` | Archivo CSV de salida | `enunciados.csv` |
| `--num-samples` | Muestras de código por problema | 2 |
| `--force` | Sobrescribir archivo existente | false |

---

## 3. Generar Referencias (`generar_referencias.py`)

Genera versiones de código alternativo usando LLMs.

### Uso

```bash
# Con modelo por defecto (1 modelo, 3 versiones)
python generar_referencias.py

# Con múltiples modelos
python generar_referencias.py --models gpt-4o-mini ollama-codellama claude-3-haiku

# Especificar cantidad de versiones
python generar_referencias.py --versions 5

# Limitar a N problemas (para pruebas)
python generar_referencias.py --limit 10

# Salida detallada
python generar_referencias.py --verbose
```

### Estructura de Salida

```
output/
├── A2016/
│   └── Z1/
│       └── Z1/
│           ├── referencia_v1_gpt-4o-mini.c
│           ├── referencia_v2_gpt-4o-mini.c
│           ├── referencia_v3_gpt-4o-mini.c
│           ├── metadata.json
```

### Metadatos (`metadata.json`)

```json
{
  "references": [
    {
      "asignacion": "A2016/Z1/Z1",
      "enunciado": "Ordenamiento burbuja",
      "codigo_original": "student1013.c",
      "modelo": "gpt-4o-mini",
      "version": 1,
      "timestamp": "2026-04-16T10:30:00"
    }
  ]
}
```

### Parámetros

| Parámetro | Descripción | Default |
|-----------|-------------|---------|
| `--model` | Modelo LLM único | `gpt-4o-mini` |
| `--models` | Lista de modelos | null |
| `--versions` | Versiones por problema | 3 |
| `--enunciados` | Archivo de enunciados | `enunciados.csv` |
| `--limit` | Limitar N problemas | unlimited |
| `--verbose` | Mostrar salida detallada | false |

---

## 4. Estadísticas (`estadisticas.py`)

Muestra estadísticas del dataset y referencias generadas.

### Uso

```bash
# Resumen básico
python estadisticas.py

# Detalle por problema
python estadisticas.py --verbose

# Exportar a CSV
python estadisticas.py --csv reporte.csv

# Exportar a JSON
python estadisticas.py --json reporte.json
```

### Salida Example

```
======================================================================
ESTADÍSTICAS DEL DATASET IEEE PLAGIARISM
======================================================================

Curso/Asignación    Problemas    Referencias IA    
--------------------------------------------------
A2016/Z1            4            12                
A2016/Z2            5            8                 
--------------------------------------------------
TOTAL              72            156               

📊 Resumen:
   - Total de problemas únicos: 72
   - Total de referencias IA generadas: 156
```

### Parámetros

| Parámetro | Descripción | Default |
|-----------|-------------|---------|
| `--verbose` | Mostrar detalle por problema | false |
| `--csv` | Exportar a CSV | null |
| `--json` | Exportar a JSON | null |
| `--dataset-path` | Ruta del dataset | `data/raw/IEEE_plagiarism/src` |
| `--output-path` | Ruta de referencias | `data/output` |

---

## Flujo de Uso

### Paso 1: Extraer Enunciados

```bash
cd data
python extraer_enunciados.py --model gpt-4o-mini
```

### Paso 2: Generar Referencias

```bash
python generar_referencias.py --versions 3
```

### Paso 3: Ver Estadísticas

```bash
python estadisticas.py --verbose
```

---

## Agregar Nuevo Modelo

### En `config.py`:

```python
MODELS = {
    # ... modelos existentes ...
    
    "deepseek-coder": {
        "provider": "openai",
        "model": "deepseek-coder",
    },
}
```

### O usando LiteLLM (soporta 100+ modelos):

```python
# En modelos.py ya está soportado
# Solo agregar config:
MODELS = {
    "azure-gpt4": {
        "provider": "litellm",
        "model": "azure/gpt-4",
    },
}
```

---

## Notas

- Los modelos cloud requieren API keys configuradas como variáveis de entorno
- Ollama debe estar ejecutándose localmente (`ollama serve`)
- Las versiones generadas incluyen metadatos para trazabilidad
- El CSV de enunciados es reutilizable entre ejecuciones