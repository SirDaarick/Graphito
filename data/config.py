import os
from pathlib import Path

def _load_dotenv_manual(path: Path = None):
    """Carga variables desde .env sin depender de python-dotenv."""
    if path is None:
        path = Path(__file__).parent.parent / ".env"
    if not path.exists():
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    _load_dotenv_manual()

BASE_DIR = Path(__file__).parent.resolve()

DATASET_PATH = BASE_DIR / "raw" / "src"
OUTPUT_PATH = BASE_DIR / "output"
ENUNCIADOS_PATH = BASE_DIR / "enunciados_srb.csv"

DEFAULT_MODEL = "gpt-4o-mini"

VERSIONS_PER_PROBLEM = 3

NUM_EJEMPLOS_ANALISIS = 2

PROMPT_ENUNCIADO = """Analiza estos códigos de estudiantes que resuelven el mismo problema.
Infiere cuál es el enunciado/tarea original basándote en el código.

ADEMAS, analiza TODOS los códigos proporcionados y genera UNA sola generalización del estilo de implementación típico. Considera:
- ¿Usan solo variables simples, ifs y loops básicos?
- ¿Usan arrays/matrices?
- ¿Usan structs/clases?
- ¿Usan funciones auxiliares o todo en main?
- ¿Qué tan complejo es el código? (básico, intermedio, avanzado)

Sé conciso en la generalización (1-2 oraciones).

{codes_section}

Responde en formato exacto:
Enunciado: X
Lenguaje: Y
DetallesImplementacion: Z
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
    "gemini-flash": {
        "provider": "litellm",
        "model": "gemini/gemini-2.0-flash",
    },
    "gemini-1.5-pro": {
        "provider": "litellm",
        "model": "gemini/gemini-1.5-pro",
    },
    "gemini-3-flash-lite-preview": {
        "provider": "litellm",
        "model": "gemini/gemini-3.1-flash-lite-preview",
    },
    "deepseek-v4-flash": {
        "provider": "opencode",
        "model": "deepseek-v4-flash",
    },
    "deepseek-v4-pro": {
        "provider": "opencode",
        "model": "deepseek-v4-pro",
    },
    "glm-5.1": {
        "provider": "opencode",
        "model": "glm-5.1",
    },
    "glm-5.2": {
        "provider": "opencode",
        "model": "glm-5.2",
    },
    "kimi-k2.6": {
        "provider": "opencode",
        "model": "kimi-k2.6",
    },
    "kimi-k2.7-code": {
        "provider": "opencode",
        "model": "kimi-k2.7-code",
    },
    "mimo-v2.5": {
        "provider": "opencode",
        "model": "mimo-v2.5",
    },
    "mimo-v2.5-pro": {
        "provider": "opencode",
        "model": "mimo-v2.5-pro",
    },
    "qwen-3.6-plus": {
        "provider": "opencode",
        "model": "qwen-3.6-plus",
    },
    "qwen-3.7-plus": {
        "provider": "opencode",
        "model": "qwen-3.7-plus",
    },
    "qwen-3.7-max": {
        "provider": "opencode",
        "model": "qwen-3.7-max",
    },
    "minimax-m2.7": {
        "provider": "opencode",
        "model": "minimax-m2.7",
    },
    "minimax-m3": {
        "provider": "opencode",
        "model": "minimax-m3",
    },
    # ============================================================
    # Modelos via OpenRouter (una sola API key para todos)
    # Precios aproximados por 1M tokens: {input, output}
    # ============================================================
    "or-deepseek-chat": {
        "provider": "openrouter",
        "model": "deepseek/deepseek-v4-flash",
        # ~$0.09/$0.18 por 1M tokens — ultra barato, excelente código
    },
    "or-mistral-small": {
        "provider": "openrouter",
        "model": "mistralai/mistral-small-3.1-24b-instruct",
        # ~$0.10/$0.30 por 1M tokens — ultra barato, multilingüe
    },
    "or-codestral": {
        "provider": "openrouter",
        "model": "mistralai/codestral-2508",
        # ~$0.30/$0.90 por 1M tokens — especializado en código
    },
    "or-gemini-flash": {
        "provider": "openrouter",
        "model": "google/gemini-2.5-flash-lite",
        # ~$0.10/$0.40 por 1M tokens — el más barato de Google
    },
    "or-qwen3": {
        "provider": "openrouter",
        "model": "qwen/qwen3-30b-a3b",
        # ~$0.10/$0.40 por 1M tokens — muy barato, decente
    },
    "or-llama4": {
        "provider": "openrouter",
        "model": "meta-llama/llama-4-maverick",
        # ~$0.20/$0.60 por 1M tokens — buen código, multilingüe
    },
    "or-claude-haiku": {
        "provider": "openrouter",
        "model": "anthropic/claude-haiku-4.5",
        # ~$1.00/$5.00 por 1M tokens — Claude rápido, buena calidad
    },
    # ============================================================
    # TIER 2: Modelos premium (calidad sobre cantidad)
    # ============================================================
    "or-gpt-nano": {
        "provider": "openrouter",
        "model": "openai/gpt-4.1-nano",
        # ~$0.01/$0.04 por 1M tokens — ULTRA barato, calidad OpenAI
    },
    "or-gpt-mini": {
        "provider": "openrouter",
        "model": "openai/gpt-4.1-mini",
        # ~$0.15/$0.60 por 1M tokens — excelente calidad/precio
    },
    "or-claude-sonnet": {
        "provider": "openrouter",
        "model": "anthropic/claude-sonnet-4.5",
        # ~$3.00/$15.00 por 1M tokens — Claude premium
    },
    "or-gemini-pro": {
        "provider": "openrouter",
        "model": "google/gemini-2.5-pro",
        # ~$1.25/$5.00 por 1M tokens — mejor Gemini
    },

}

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# ============================================================
# TIER 1: VOLUMEN — modelos baratos, generar cantidad primero
# ============================================================
# Usar con: --tier volume (default)
# Ideal para generar 2-3 refs por problema con modelos baratos.
# ============================================================
GENERATION_PRIORITY = [
    # Motor principal: deepseek — barato, excelente en código
    {"model": "or-deepseek-chat", "max_wait_seconds": 30, "max_retries": 3},
    # Diversidad barata: diferentes estilos de código
    {"model": "or-qwen3", "max_wait_seconds": 45, "max_retries": 2},
    {"model": "or-mistral-small", "max_wait_seconds": 45, "max_retries": 2},
    {"model": "or-codestral", "max_wait_seconds": 45, "max_retries": 2},
    {"model": "or-gemini-flash", "max_wait_seconds": 45, "max_retries": 2},
    {"model": "or-llama4", "max_wait_seconds": 45, "max_retries": 2},
]

# ============================================================
# TIER 2: CALIDAD — modelos premium, rellenar después
# ============================================================
# Usar con: --tier quality
# Después de tener volumen (fase 1), subir --limit-per-problem
# y correr con --tier quality para añadir referencias premium.
# ============================================================
GENERATION_PRIORITY_QUALITY = [
    # GPT-4.1 Nano: ultra barato, pero con el "estilo OpenAI"
    {"model": "or-gpt-nano", "max_wait_seconds": 30, "max_retries": 3},
    # GPT-4.1 Mini: excelente calidad/precio
    {"model": "or-gpt-mini", "max_wait_seconds": 45, "max_retries": 2},
    # Claude Haiku: rápido, buena calidad Anthropic
    {"model": "or-claude-haiku", "max_wait_seconds": 45, "max_retries": 2},
    # Gemini Pro: tope de gama Google
    {"model": "or-gemini-pro", "max_wait_seconds": 60, "max_retries": 1},
    # Claude Sonnet: el mejor, usar con moderación
    {"model": "or-claude-sonnet", "max_wait_seconds": 60, "max_retries": 1},
]