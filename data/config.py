import os
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()

DATASET_PATH = BASE_DIR / "raw" / "IEEE_plagiarism" / "src"
OUTPUT_PATH = BASE_DIR / "output"
ENUNCIADOS_PATH = BASE_DIR / "enunciados.csv"

DEFAULT_MODEL = "gpt-4o-mini"

VERSIONS_PER_PROBLEM = 3

NUM_EJEMPLOS_ANALISIS = 2

PROMPT_ENUNCIADO = """Analiza estos códigos de estudiantes que resuelven el mismo problema.
Infiere cuál es el enunciado/tarea original basándote en el código.
Solo responde con el enunciado inferred y el lenguaje de programación.

Código 1:
{code1}

Código 2:
{code2}

Responde en formato: "Enunciado: X | Lenguaje: Y"
"""

PROMPT_REFERENCIA = """Given this problem description: "{enunciado}"
And this original solution:
```c
{codigo_original}
```

Generate a functionally equivalent code but with a DIFFERENT implementation approach.
Do NOT copy the logic directly - use alternative algorithms where possible.
The output should be clean, compilable C code.
"""

MODELS = {
    "gpt-4o-mini": {
        "provider": "openai",
        "model": "gpt-4o-mini",
    },
    "gpt-4o": {
        "provider": "openai",
        "model": "gpt-4o",
    },
    "gpt-4-turbo": {
        "provider": "openai",
        "model": "gpt-4-turbo",
    },
    "claude-3-haiku": {
        "provider": "anthropic",
        "model": "claude-3-haiku-20240307",
    },
    "claude-3-sonnet": {
        "provider": "anthropic",
        "model": "claude-3-sonnet-20240229",
    },
    "claude-3-opus": {
        "provider": "anthropic",
        "model": "claude-3-opus-20240229",
    },
    "ollama-codellama": {
        "provider": "ollama",
        "model": "codellama",
    },
    "ollama-llama3": {
        "provider": "ollama",
        "model": "llama3",
    },
    "ollama-mistral": {
        "provider": "ollama",
        "model": "mistral",
    },
}

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")