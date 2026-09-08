#!/usr/bin/env python3
"""
generar_referencias.py - Generador de código de referencia con múltiples APIs

Características principales:
- Múltiples APIs con prioridad configurable y fallback automático
- Manejo de rate limits (espera inteligente o salto a siguiente API)
- Código generado en serbocroata para evitar detección por idioma
- Estado persistente para continuar ejecuciones interrumpidas
- Genera la misma cantidad de archivos que estudiantes hay por problema
- Modo sample para pruebas rápidas
"""

import argparse
import csv
import itertools
import json
import os
import random
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Excepciones personalizadas
# ---------------------------------------------------------------------------

class RateLimitError(Exception):
    """Rate limit detectado con tiempo de espera sugerido (segundos)."""
    def __init__(self, retry_after: float, api_name: str):
        self.retry_after = retry_after
        self.api_name = api_name
        super().__init__(f"Rate limit en {api_name}: esperar {retry_after}s")


class APIError(Exception):
    """Error no recuperable de una API."""
    def __init__(self, message: str, api_name: str):
        self.api_name = api_name
        super().__init__(f"Error en {api_name}: {message}")


class AllAPIsFailedError(Exception):
    """Todas las APIs fallaron para una petición."""
    pass


# ---------------------------------------------------------------------------
# Perfiles de generación (prompt + temperatura)
# ---------------------------------------------------------------------------
# Cada perfil simula un tipo distinto de estudiante. Se ciclan
# round-robin para dar variedad a las referencias generadas.

PERFILES = {
    "descuidado": {
        "nombre": "descuidado",
        "temperature": 0.85,
        "descripcion": "Student promedio — nombres cortos, código simple, SIN comentarios",
        "prompt": """Napiši {lenguaje} kod koji rešava sledeći zadatak:
{enunciado}

Kod treba da bude jednostavan i funkcionalan. Koristi kratke nazive varijabli (i, j, temp, a, b, niz). Ne dodaj nikakve komentare — studentski kod nema komentare.

Pravila:
- SVI nazivi varijabli i funkcija NA srpskohrvatskom jeziku (kratki: broj, zbir, unos, ispis, temp, n, m)
- SVI stringovi za korisnika (printf, scanf poruke, greške) MORAJU biti na srpskohrvatskom
- NIKAKAV engleski ili španski u kodu
- NEMA komentara u kodu — APSOLUTNO NIKAKVIH // ili /* */ komentara
- Output SAMO raw kod, bez markdowna, bez objašnjenja
- Kod mora biti kompajliran bez grešaka
""",
    },
    "aplicado": {
        "nombre": "aplicado",
        "temperature": 0.4,
        "descripcion": "Student aplicado — nombres descriptivos, código limpio, SIN comentarios",
        "prompt": """Napiši čist, dobro strukturiran i efikasan {lenguaje} kod za sledeći zadatak:
{enunciado}

Koristi jasne i opisne nazive varijabli na srpskohrvatskom jeziku (brojacKaraktera, sumaBodova, indeksNajveceg). Kod treba da bude pregledan i dobro formatiran. Ne dodaj nikakve komentare — studentski kod nema komentare.

Pravila:
- SVI nazivi varijabli i funkcija NA srpskohrvatskom jeziku (deskriptivni: brojPonavljanja, prosjekOcjena, matricaRezultata)
- SVI stringovi za korisnika (printf, scanf poruke, greške) MORAJU biti na srpskohrvatskom
- NIKAKAV engleski ili španski u kodu
- NEMA komentara u kodu — APSOLUTNO NIKAKVIH // ili /* */ komentara
- Output SAMO raw kod, bez markdowna, bez objašnjenja
- Kod mora biti kompajliran bez grešaka
""",
    },
    "kompaktan": {
        "nombre": "kompaktan",
        "temperature": 0.7,
        "descripcion": "Student minimalista — nombres mínimos, código ultra-directo, SIN comentarios",
        "prompt": """Napiši {lenguaje} kod koji rešava sledeći zadatak:
{enunciado}

Piši ga na najkraći mogući način. Koristi najkraće nazive varijabli (jedno ili dva slova). Sve u main() osim ako je baš neophodna pomoćna funkcija. Ne dodaj nikakve komentare.

Pravila:
- SVI nazivi varijabli NA srpskohrvatskom (najkraći: a, b, n, s, t, p, r)
- SVI stringovi za korisnika MORAJU biti na srpskohrvatskom
- NIKAKAV engleski ili španski u kodu
- NEMA komentara u kodu — APSOLUTNO NIKAKVIH // ili /* */ komentara
- Sve u main() osim ako baš mora biti funkcija
- Output SAMO raw kod, bez markdowna, bez objašnjenja
- Kod mora biti kompajliran bez grešaka
""",
    },
    # ================================================================
    # Perfiles CON comentarios (para igualar ~38% de estudiantes reales)
    # ================================================================
    "comentado-bueno": {
        "nombre": "comentado-bueno",
        "temperature": 0.4,
        "descripcion": "Odličan učenik — detaljni komentari, dobro objašnjenje, uredan kod",
        "prompt": """Ti si odličan učenik koji voli da detaljno dokumentuje svoj kod. Napiši {lenguaje} kod za sledeći zadatak:
{enunciado}

Dodaj KOMENTARE na srpskohrvatskom jeziku. Objasni šta program radi na početku, dodaj komentar ispred svake funkcije koji opisuje šta ona radi, i ubaci povremene komentare uz ključne delove koda (petlje, uslove, formule). Komentari neka zvuče kao da ih je pisao učenik koji razume gradivo, a ne profesionalni programer.

Pravila:
- SVI nazivi varijabli, funkcija I KOMENTARI na srpskohrvatskom
- SVI stringovi za korisnika na srpskohrvatskom
- NIKAKAV engleski ili španski
- Output SAMO raw kod sa komentarima, bez markdowna
- Kod mora biti kompajliran bez grešaka
""",
    },
    "comentado-basic": {
        "nombre": "comentado-basic",
        "temperature": 0.7,
        "descripcion": "Prosečan učenik — poneki kratak komentar, neformalno, samo gde treba",
        "prompt": """Napiši {lenguaje} kod za sledeći zadatak:
{enunciado}

Dodaj PONEKI komentar na srpskohrvatskom. Ne moraš komentarisati sve — samo ubaci tu i tamo kratak komentar gde misliš da treba (npr. ispred petlje, ili da objasniš neku formulu). Komentari neka budu kratki i ne previše formalni, kao da ih pišeš za sebe dok učiš.

Pravila:
- SVI nazivi varijabli, funkcija I KOMENTARI na srpskohrvatskom
- SVI stringovi za korisnika na srpskohrvatskom
- NIKAKAV engleski ili španski
- Dodaj 2-4 kratka komentara ukupno (ne više)
- Output SAMO raw kod sa komentarima, bez markdowna
- Kod mora biti kompajliran bez grešaka
""",
    },
    "comentado-malo": {
        "nombre": "comentado-malo",
        "temperature": 0.85,
        "descripcion": "Nemaran učenik — očigledni komentari, greške, na brzinu dodati",
        "prompt": """Napiši {lenguaje} kod za sledeći zadatak:
{enunciado}

Dodaj KOMENTARE na srpskohrvatskom jeziku, ali neka komentari budu MALO LOŠIJI — kao da ih je pisao učenik koji ne voli da komentariše ali mora. Neki komentari neka budu očigledni (npr. "// ovdje se sabiraju brojevi" pored petlje koja očigledno sabira), neki neka imaju slovne greške, neki neka budu nepotrebni. Neka izgleda kao da je učenik na brzinu dodao komentare pred predaju.

Pravila:
- SVI nazivi varijabli, funkcija I KOMENTARI na srpskohrvatskom
- SVI stringovi za korisnika na srpskohrvatskom
- NIKAKAV engleski ili španski
- Komentari neka izgledaju prirodno, ponekad sa greškama, ponekad očigledni
- Output SAMO raw kod sa komentarima, bez markdowna
- Kod mora biti kompajliran bez grešaka
""",
    },
}

PERFILES_LIST = list(PERFILES.keys())
PERFILES_SIN_COMENTARIOS = ["descuidado", "aplicado", "kompaktan"]
PERFILES_CON_COMENTARIOS = ["comentado-bueno", "comentado-basic", "comentado-malo"]


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def load_enunciados(enunciados_path: Path) -> dict[tuple, dict]:
    """Carga enunciados.csv en un diccionario indexado por (curso, carpeta, subcarpeta)."""
    enunciados = {}
    if not enunciados_path.exists():
        print(f"❌ Error: {enunciados_path} no existe. Ejecuta primero extraer_enunciados.py")
        sys.exit(1)

    with enunciados_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = (row["curso"], row["carpeta"], row["subcarpeta"])
            enunciados[key] = {
                "enunciado": row["enunciado"],
                "lenguaje": row["lenguaje"],
                "detalles": row.get("detalles_implementacion", ""),
            }
    return enunciados


def count_student_files(problem_path: Path) -> int:
    """Cuenta archivos .c y .cpp en una carpeta de problema."""
    if not problem_path.exists():
        return 0
    return len(list(problem_path.glob("*.c"))) + len(list(problem_path.glob("*.cpp")))


def load_state(state_file: Path) -> dict:
    """Carga estado persistente de generación."""
    if state_file.exists():
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {"problems": {}, "total_generated": 0}


def save_state(state_file: Path, state: dict):
    """Guarda estado persistente atómicamente."""
    state_file.parent.mkdir(parents=True, exist_ok=True)
    tmp = state_file.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
    tmp.replace(state_file)


# ---------------------------------------------------------------------------
# Providers con manejo de rate limits
# ---------------------------------------------------------------------------

class OpenAIProviderWrapper:
    def __init__(self, model: str, api_key: Optional[str] = None):
        try:
            import openai
        except ImportError:
            raise ImportError("openai package not installed. Run: pip install openai")

        self.model = model
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not set")
        self.client = openai.OpenAI(api_key=self.api_key)
        self.name = f"openai/{model}"

    def generate(self, prompt: str, temperature: float = 0.7) -> str:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
            )
            return response.choices[0].message.content
        except Exception as e:
            self._handle_error(e)

    def _handle_error(self, e):
        retry_after = None
        # OpenAI v1+ expone headers en algunos errores
        headers = getattr(e, "headers", {}) or {}
        if headers:
            ra = headers.get("retry-after") or headers.get("x-ratelimit-reset")
            if ra:
                retry_after = float(ra)

        msg = str(e).lower()
        if "rate limit" in msg or "ratelimit" in msg or "too many requests" in msg or "429" in msg:
            # Si no tenemos retry-after, estimamos 10s
            if retry_after is None:
                retry_after = 10.0
            raise RateLimitError(retry_after, self.name) from e
        raise APIError(str(e), self.name) from e


class AnthropicProviderWrapper:
    def __init__(self, model: str, api_key: Optional[str] = None):
        try:
            import anthropic
        except ImportError:
            raise ImportError("anthropic package not installed. Run: pip install anthropic")

        self.model = model
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")
        self.client = anthropic.Anthropic(api_key=self.api_key)
        self.name = f"anthropic/{model}"

    def generate(self, prompt: str, temperature: float = 0.7) -> str:
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                temperature=temperature,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        except Exception as e:
            self._handle_error(e)

    def _handle_error(self, e):
        msg = str(e).lower()
        retry_after = None
        headers = getattr(e, "headers", {}) or {}
        if headers:
            ra = headers.get("retry-after")
            if ra:
                retry_after = float(ra)

        if "rate limit" in msg or "ratelimit" in msg or "too many requests" in msg or "429" in msg:
            if retry_after is None:
                retry_after = 10.0
            raise RateLimitError(retry_after, self.name) from e
        raise APIError(str(e), self.name) from e


class OllamaProviderWrapper:
    def __init__(self, model: str, base_url: Optional[str] = None):
        self.model = model
        self.base_url = base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.name = f"ollama/{model}"

    def generate(self, prompt: str, temperature: float = 0.7) -> str:
        try:
            import requests
        except ImportError:
            raise ImportError("requests package not installed. Run: pip install requests")

        try:
            response = requests.post(
                f"{self.base_url}/api/chat",
                json={"model": self.model, "messages": [{"role": "user", "content": prompt}], "stream": False, "options": {"temperature": temperature}},
                timeout=120,
            )
            if response.status_code == 429:
                ra = response.headers.get("Retry-After", 5)
                raise RateLimitError(float(ra), self.name)
            response.raise_for_status()
            return response.json()["message"]["content"]
        except (RateLimitError, APIError):
            raise
        except Exception as e:
            raise APIError(str(e), self.name) from e


class LiteLLMProviderWrapper:
    def __init__(self, model: str, api_key: Optional[str] = None):
        try:
            import litellm
        except ImportError:
            raise ImportError("litellm package not installed. Run: pip install litellm")

        self.model = model
        self.api_key = api_key
        self.name = f"litellm/{model}"

    def generate(self, prompt: str, temperature: float = 0.7) -> str:
        try:
            import litellm
            kwargs = {"model": self.model, "messages": [{"role": "user", "content": prompt}], "temperature": temperature}
            if self.api_key:
                kwargs["api_key"] = self.api_key
            response = litellm.completion(**kwargs)
            return response.choices[0].message.content
        except Exception as e:
            msg = str(e).lower()
            if "rate limit" in msg or "ratelimit" in msg or "too many requests" in msg or "429" in msg:
                retry_after = 10.0
                # Intentar extraer retry-after del mensaje
                import re
                m = re.search(r"retry[_\s-]?after[:\s=]*(\d+(?:\.\d+)?)", msg)
                if m:
                    retry_after = float(m.group(1))
                raise RateLimitError(retry_after, self.name) from e
            raise APIError(str(e), self.name) from e


class GeminiNativeProviderWrapper:
    """Provider nativo para Gemini usando requests (sin dependencias extra)."""
    def __init__(self, model: str, api_key: Optional[str] = None):
        self.model = model
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY not set")
        self.name = f"gemini/{model}"

    def generate(self, prompt: str, temperature: float = 0.7) -> str:
        try:
            import requests
        except ImportError:
            raise ImportError("requests package not installed. Run: pip install requests")

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        params = {"key": self.api_key}
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": temperature},
        }

        try:
            response = requests.post(url, params=params, json=payload, timeout=120)
            if response.status_code == 429:
                retry_after = float(response.headers.get("Retry-After", 10))
                raise RateLimitError(retry_after, self.name)
            response.raise_for_status()
            data = response.json()
            # Extraer texto de la respuesta
            candidates = data.get("candidates", [])
            if not candidates:
                raise APIError("Respuesta vacía de Gemini", self.name)
            parts = candidates[0].get("content", {}).get("parts", [])
            if not parts:
                raise APIError("Respuesta sin contenido de Gemini", self.name)
            return parts[0].get("text", "")
        except (RateLimitError, APIError):
            raise
        except Exception as e:
            raise APIError(str(e), self.name) from e


class OpencodeProviderWrapper:
    """Provider para OpenCode AI (compatible con OpenAI API)."""
    BASE_URL = "https://opencode.ai/zen/go/v1"

    def __init__(self, model: str, api_key: Optional[str] = None):
        self.model = model
        self.api_key = api_key or os.getenv("OPENCODE_API_KEY")
        if not self.api_key:
            raise ValueError("OPENCODE_API_KEY not set")
        self.name = f"opencode/{model}"

    def generate(self, prompt: str, temperature: float = 0.7) -> str:
        try:
            import requests
        except ImportError:
            raise ImportError("requests package not installed. Run: pip install requests")

        try:
            response = requests.post(
                f"{self.BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
                "max_tokens": 16384,
                },
                timeout=300,
            )
            if response.status_code == 429:
                retry_after = float(response.headers.get("Retry-After", 10))
                raise RateLimitError(retry_after, self.name)
            response.raise_for_status()
            data = response.json()
            msg = data["choices"][0]["message"]
            content = msg.get("content", "")
            # Algunos modelos reasoning (ej: deepseek) devuelven todo en reasoning_content
            if not content and "reasoning_content" in msg:
                content = msg["reasoning_content"]
            return content
        except (RateLimitError, APIError):
            raise
        except Exception as e:
            raise APIError(str(e), self.name) from e


class OpenRouterProviderWrapper:
    """Provider para OpenRouter (API compatible con OpenAI).

    OpenRouter unifica cientos de modelos bajo una sola API key.
    Los modelos se referencian como "provider/model", ej: "google/gemini-2.5-flash".
    """
    BASE_URL = "https://openrouter.ai/api/v1"

    def __init__(self, model: str, api_key: Optional[str] = None):
        self.model = model
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY not set")
        self.name = f"openrouter/{model}"

    def generate(self, prompt: str, temperature: float = 0.7) -> str:
        try:
            import requests
        except ImportError:
            raise ImportError("requests package not installed. Run: pip install requests")

        try:
            response = requests.post(
                f"{self.BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com/daarick/graphito",
                    "X-Title": "Graphito Plagiarism Detection Dataset",
                },
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": temperature,
                    "max_tokens": 16384,
                },
                timeout=300,
            )
            if response.status_code == 429:
                retry_after = float(response.headers.get("Retry-After", 10))
                raise RateLimitError(retry_after, self.name)
            if response.status_code == 402:
                raise APIError("Crédito insuficiente en OpenRouter", self.name)
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"].get("content", "")
            if not content:
                raise APIError("Respuesta vacía de OpenRouter", self.name)
            return content
        except (RateLimitError, APIError):
            raise
        except Exception as e:
            raise APIError(str(e), self.name) from e


PROVIDER_MAP = {
    "openai": OpenAIProviderWrapper,
    "anthropic": AnthropicProviderWrapper,
    "ollama": OllamaProviderWrapper,
    "litellm": LiteLLMProviderWrapper,
    "gemini": GeminiNativeProviderWrapper,
    "opencode": OpencodeProviderWrapper,
    "openrouter": OpenRouterProviderWrapper,
}


def create_provider(model_config: dict) -> object:
    """Crea un provider wrapper desde config.py MODELS."""
    provider_type = model_config.get("provider")
    model = model_config.get("model")

    # Auto-detect Gemini para usar provider nativo (sin litellm)
    if model and model.startswith("gemini/") and provider_type == "litellm":
        provider_type = "gemini"
        model = model.split("/")[-1]  # gemini/gemini-1.5-flash -> gemini-1.5-flash

    cls = PROVIDER_MAP.get(provider_type)
    if not cls:
        raise ValueError(f"Provider '{provider_type}' no soportado")

    kwargs = {}
    if provider_type == "openai":
        kwargs["api_key"] = os.getenv("OPENAI_API_KEY")
    elif provider_type == "anthropic":
        kwargs["api_key"] = os.getenv("ANTHROPIC_API_KEY")
    elif provider_type == "ollama":
        kwargs["base_url"] = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    elif provider_type in ("litellm", "gemini"):
        kwargs["api_key"] = os.getenv("GOOGLE_API_KEY")
    elif provider_type == "opencode":
        kwargs["api_key"] = os.getenv("OPENCODE_API_KEY")
    elif provider_type == "openrouter":
        kwargs["api_key"] = os.getenv("OPENROUTER_API_KEY")

    return cls(model=model, **kwargs)


# ---------------------------------------------------------------------------
# Orquestador de APIs
# ---------------------------------------------------------------------------

class APIOrchestrator:
    def __init__(self, priority_list: list[dict], models_config: dict, strategy: str = "priority"):
        """
        priority_list: lista de dicts con 'model', 'max_wait_seconds', 'max_retries'
        models_config: dict de config.MODELS
        strategy: "priority" (fallback), "cycle" (round-robin), "random"
        """
        self.priority_list = priority_list
        self.models_config = models_config
        self.strategy = strategy
        self._provider_cache = {}
        self._cycle_index = 0

    def _get_provider(self, model_name: str):
        if model_name not in self._provider_cache:
            cfg = self.models_config.get(model_name)
            if not cfg:
                raise ValueError(f"Modelo '{model_name}' no encontrado en MODELS")
            self._provider_cache[model_name] = create_provider(cfg)
        return self._provider_cache[model_name]

    def _iter_models(self):
        """Genera modelos en orden según la estrategia."""
        n = len(self.priority_list)
        if n == 0:
            return

        if self.strategy == "random":
            start = random.randint(0, n - 1)
        elif self.strategy == "cycle":
            start = self._cycle_index % n
            self._cycle_index = (self._cycle_index + 1) % n
        else:
            start = 0

        for offset in range(n):
            yield self.priority_list[(start + offset) % n]

    def generate(self, prompt: str, lenguaje: str, temperature: float = 0.7) -> tuple[str, str]:
        """
        Intenta generar con cada modelo según la estrategia configurada.
        Retorna (codigo, modelo_usado).
        """
        for prio in self._iter_models():
            model_name = prio["model"]
            max_wait = prio.get("max_wait_seconds", 60)
            max_retries = prio.get("max_retries", 2)

            try:
                provider = self._get_provider(model_name)
            except Exception as e:
                print(f"  ⚠️  No se pudo inicializar {model_name}: {e}")
                continue

            for attempt in range(max_retries):
                try:
                    code = provider.generate(prompt, temperature=temperature)
                    return code, model_name
                except RateLimitError as rle:
                    if rle.retry_after <= max_wait:
                        print(f"  ⏳ Rate limit en {model_name}, esperando {rle.retry_after:.1f}s...")
                        time.sleep(rle.retry_after)
                        # Reintentar con la misma API
                        continue
                    else:
                        print(f"  ⏭️  Rate limit en {model_name} pide esperar {rle.retry_after:.1f}s (>{max_wait}s), saltando...")
                        break  # Pasar a siguiente API
                except APIError as ae:
                    print(f"  ❌ Error en {model_name}: {ae}")
                    break  # Pasar a siguiente API
                except Exception as e:
                    print(f"  ❌ Excepción inesperada en {model_name}: {e}")
                    traceback.print_exc()
                    break  # Pasar a siguiente API

        raise AllAPIsFailedError("Todas las APIs fallaron para esta petición")


# ---------------------------------------------------------------------------
# Generación y guardado
# ---------------------------------------------------------------------------

def extract_code_block(text: str) -> str:
    """Extrae código de bloques markdown si existen."""
    text = text.strip()
    for tag in ("```c\n", "```cpp\n", "```c++\n", "```\n"):
        if tag in text:
            parts = text.split(tag, 1)
            if len(parts) == 2:
                code = parts[1].split("```", 1)[0]
                return code.strip()
    # Si no hay bloques markdown, devolver todo
    return text


def generate_reference(orchestrator: APIOrchestrator, enunciado: str, lenguaje: str, detalles: str = "", perfil: dict = None) -> tuple[str, str, str]:
    """Genera una referencia usando el perfil dado (prompt + temperatura)."""
    if perfil is None:
        perfil = PERFILES["kompaktan"]
    prompt = perfil["prompt"].format(enunciado=enunciado, lenguaje=lenguaje)
    raw_code, model_used = orchestrator.generate(prompt, lenguaje, temperature=perfil["temperature"])
    code = extract_code_block(raw_code)
    return code, model_used, perfil["nombre"]


def save_reference(output_dir: Path, problem_key: str, code: str, metadata: dict) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    # Extensión según lenguaje: .c para C, .cpp para C++
    ext = ".cpp" if metadata.get("lenguaje", "").upper() == "C++" else ".c"
    # Perfil para el nombre del archivo
    perfil = metadata.get("perfil", "gen")
    # Nombre: ref_<perfil>_<modelo>_<timestamp>.<ext>
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_model = metadata["modelo"].replace("/", "_").replace(".", "_")
    filename = f"ref_{perfil}_{safe_model}_{ts}_{metadata['index']:04d}{ext}"
    file_path = output_dir / filename
    file_path.write_text(code, encoding="utf-8")
    return file_path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Generar código de referencia con múltiples APIs y fallback"
    )
    parser.add_argument(
        "--enunciados", type=Path, default=None,
        help="Ruta a enunciados.csv (default: desde config.py)"
    )
    parser.add_argument(
        "--dataset", type=Path, default=None,
        help="Ruta al dataset raw/src (default: desde config.py)"
    )
    parser.add_argument(
        "--output", type=Path, default=None,
        help="Directorio de salida (default: output/ desde config.py)"
    )
    parser.add_argument(
        "--state-file", type=Path, default=None,
        help="Archivo de estado JSON (default: output/.generation_state.json)"
    )
    parser.add_argument(
        "--priority", type=str, default=None,
        help='Lista de modelos en orden de prioridad separados por coma, ej: "gemini-flash,gpt-4o-mini"'
    )
    parser.add_argument(
        "--sample", "-s", type=int, default=None,
        help="Procesar solo N problemas (para pruebas)"
    )
    parser.add_argument(
        "--limit-per-problem", "-l", type=int, default=None,
        help="Máximo de referencias a generar por problema (default: misma cantidad que estudiantes)"
    )
    parser.add_argument(
        "--reset-state", action="store_true",
        help="Borrar estado previo y empezar de cero"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Mostrar salida detallada"
    )
    parser.add_argument(
        "--dry-run", "-n", action="store_true",
        help="Simular sin llamar APIs ni escribir archivos"
    )
    parser.add_argument(
        "--profiles", type=str, default="cycle",
        help='Modo de selección de perfiles: "cycle" (round-robin), "random", o nombre específico (descuidado, aplicado, kompaktan). Default: cycle'
    )
    parser.add_argument(
        "--tier", type=str, default="volume", choices=["volume", "quality"],
        help='Tier de modelos: "volume" (baratos, default) o "quality" (premium, para rellenar después)'
    )
    parser.add_argument(
        "--model-strategy", type=str, default="cycle", choices=["priority", "cycle", "random"],
        help='Estrategia: "priority" (fallback, un solo modelo), "cycle" (round-robin entre todos), "random". Default: cycle'
    )
    parser.add_argument(
        "--model", type=str, default=None,
        help='Usar SOLO este modelo (ignora priority y tier). Ej: --model or-deepseek-chat'
    )

    args = parser.parse_args()

    # Cargar config.py si existe
    config_path = Path(__file__).parent / "config.py"
    models_config = {}
    priority_list = []
    default_dataset = None
    default_output = None
    default_enunciados = None

    if config_path.exists():
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location("config", config_path)
            cfg = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cfg)
            models_config = getattr(cfg, "MODELS", {})
            # Seleccionar tier de modelos
            if args.tier == "quality":
                priority_list = getattr(cfg, "GENERATION_PRIORITY_QUALITY", [])
                if not priority_list:
                    print("⚠️  GENERATION_PRIORITY_QUALITY no definido en config.py, usando tier volume")
                    priority_list = getattr(cfg, "GENERATION_PRIORITY", [])
            else:
                priority_list = getattr(cfg, "GENERATION_PRIORITY", [])
            default_dataset = getattr(cfg, "DATASET_PATH", None)
            default_output = getattr(cfg, "OUTPUT_PATH", None)
            default_enunciados = getattr(cfg, "ENUNCIADOS_PATH", None)
        except Exception as e:
            print(f"⚠️  config.py existe pero falló al cargar: {e}")

    # Fallback inline si config.py no cargó nada
    if not priority_list:
        priority_list = [
            {"model": "gemini-flash", "max_wait_seconds": 60, "max_retries": 2},
            {"model": "gpt-4o-mini", "max_wait_seconds": 60, "max_retries": 2},
        ]

    # Fallbacks
    dataset_path = Path(args.dataset or default_dataset or Path(__file__).parent / "raw" / "src")
    output_path = Path(args.output or default_output or Path(__file__).parent / "output")
    enunciados_path = Path(args.enunciados or default_enunciados or Path(__file__).parent / "enunciados.csv")
    state_file = Path(args.state_file or output_path / ".generation_state.json")

    # Parsear prioridad desde CLI si se pasó
    if args.priority:
        model_names = [m.strip() for m in args.priority.split(",")]
        priority_list = []
        for mn in model_names:
            priority_list.append({"model": mn, "max_wait_seconds": 60, "max_retries": 2})

    if not priority_list:
        print("❌ Error: No hay APIs configuradas. Define GENERATION_PRIORITY en config.py o usa --priority")
        sys.exit(1)

    # Si se especifica --model, sobreescribe la lista de prioridad
    if args.model:
        if args.model not in models_config:
            print(f"❌ Error: Modelo '{args.model}' no encontrado en config.py MODELS")
            print(f"   Modelos disponibles: {', '.join(k for k in models_config if k.startswith('or-'))}")
            sys.exit(1)
        priority_list = [{"model": args.model, "max_wait_seconds": 60, "max_retries": 3}]
        print(f"🎯 Usando modelo único: {args.model}")

    print(f"📁 Dataset: {dataset_path}")
    print(f"📁 Output: {output_path}")
    print(f"📄 Enunciados: {enunciados_path}")
    print(f"💾 Estado: {state_file}")
    print(f"🔌 Prioridad de APIs (tier={args.tier}, strategy={args.model_strategy}): {[p['model'] for p in priority_list]}")

    # Cargar estado
    state = load_state(state_file)
    if args.reset_state:
        state = {"problems": {}, "total_generated": 0}
        if state_file.exists():
            state_file.unlink()
        print("🗑️  Estado previo borrado.")

    # Cargar enunciados
    enunciados = load_enunciados(enunciados_path)
    print(f"📋 Cargados {len(enunciados)} enunciados")

    # Preparar lista de problemas
    problemas = []
    for (curso, carpeta, subcarpeta), data in enunciados.items():
        problem_path = dataset_path / curso / carpeta / subcarpeta
        total_files = count_student_files(problem_path)
        if total_files == 0:
            continue

        key = f"{curso}/{carpeta}/{subcarpeta}"
        prob_state = state["problems"].get(key, {})
        generated = prob_state.get("generated", 0)
        target = args.limit_per_problem or total_files
        remaining = max(0, target - generated)

        problemas.append({
            "key": key,
            "curso": curso,
            "carpeta": carpeta,
            "subcarpeta": subcarpeta,
            "enunciado": data["enunciado"],
            "lenguaje": data["lenguaje"],
            "total_files": total_files,
            "target": target,
            "generated": generated,
            "remaining": remaining,
            "problem_path": problem_path,
        })

    # Filtrar solo los que faltan generar
    problemas_pendientes = [p for p in problemas if p["remaining"] > 0]

    if args.sample:
        problemas_pendientes = problemas_pendientes[:args.sample]
        print(f"🧪 Modo sample: procesando {len(problemas_pendientes)} problemas")

    if not problemas_pendientes:
        print("✅ No hay problemas pendientes. Todo generado.")
        return

    print(f"🎯 Problemas pendientes: {len(problemas_pendientes)}")
    print(f"📝 Referencias faltantes totales: {sum(p['remaining'] for p in problemas_pendientes)}")

    if args.dry_run:
        print("\n🔍 DRY RUN - No se llamarán APIs ni se escribirán archivos")
        for p in problemas_pendientes:
            print(f"  {p['key']}: faltan {p['remaining']} de {p['target']} (estudiantes: {p['total_files']})")
        return

    # Inicializar orquestador
    orchestrator = APIOrchestrator(priority_list, models_config, strategy=args.model_strategy)

    # Configurar perfiles
    profiles_mode = args.profiles
    if profiles_mode == "cycle":
        profile_cycle = itertools.cycle(PERFILES_LIST)
        print(f"👤 Perfiles: cycle ({', '.join(PERFILES_LIST)})")
    elif profiles_mode == "comentados":
        profile_cycle = itertools.cycle(PERFILES_CON_COMENTARIOS)
        print(f"👤 Perfiles: solo comentados ({', '.join(PERFILES_CON_COMENTARIOS)})")
    elif profiles_mode == "random":
        print(f"👤 Perfiles: random ({', '.join(PERFILES_LIST)})")
    elif profiles_mode in PERFILES:
        print(f"👤 Perfil fijo: {profiles_mode}")
    else:
        print(f"⚠️  Perfil '{profiles_mode}' no válido. Usando cycle.")
        profiles_mode = "cycle"
        profile_cycle = itertools.cycle(PERFILES_LIST)

    total_errors = 0
    total_generated_session = 0

    for i, prob in enumerate(problemas_pendientes):
        key = prob["key"]
        print(f"\n[{i+1}/{len(problemas_pendientes)}] {key} — faltan {prob['remaining']} referencias")

        out_dir = output_path / prob["curso"] / prob["carpeta"] / prob["subcarpeta"]
        out_dir.mkdir(parents=True, exist_ok=True)

        # Inicializar estado del problema si no existe
        if key not in state["problems"]:
            state["problems"][key] = {
                "total_files": prob["total_files"],
                "target": prob["target"],
                "generated": 0,
                "references": [],
            }

        for ref_idx in range(prob["remaining"]):
            global_idx = state["problems"][key]["generated"] + 1

            # Seleccionar perfil
            if profiles_mode in ("cycle", "comentados"):
                perfil_nombre = next(profile_cycle)
            elif profiles_mode == "random":
                perfil_nombre = random.choice(PERFILES_LIST)
            else:
                perfil_nombre = profiles_mode
            perfil = PERFILES[perfil_nombre]

            try:
                code, model_used, perfil_usado = generate_reference(
                    orchestrator,
                    prob["enunciado"],
                    prob["lenguaje"],
                    prob.get("detalles", ""),
                    perfil=perfil,
                )

                metadata = {
                    "index": global_idx,
                    "modelo": model_used,
                    "perfil": perfil_usado,
                    "temperatura": perfil["temperature"],
                    "lenguaje": prob["lenguaje"],
                    "timestamp": datetime.now().isoformat(),
                }

                file_path = save_reference(out_dir, key, code, metadata)

                state["problems"][key]["generated"] += 1
                state["problems"][key]["references"].append({
                    "file": file_path.name,
                    "modelo": model_used,
                    "perfil": perfil_usado,
                    "timestamp": metadata["timestamp"],
                })
                state["total_generated"] += 1
                total_generated_session += 1

                if args.verbose:
                    print(f"  ✅ {file_path.name} ({model_used}, perfil: {perfil_usado})")
                else:
                    print(f"  ✅ {global_idx}/{prob['target']} ({model_used}, {perfil_usado})", end="\r")

                # Guardar estado cada 5 referencias
                if total_generated_session % 5 == 0:
                    save_state(state_file, state)

            except AllAPIsFailedError:
                print(f"\n  ❌ TODAS LAS APIs FALLARON para {key}, saltando a siguiente problema...")
                total_errors += 1
                break  # Pasar al siguiente problema
            except KeyboardInterrupt:
                print(f"\n\n⏹️  Interrumpido por el usuario. Guardando estado...")
                save_state(state_file, state)
                print(f"💾 Estado guardado en {state_file}")
                sys.exit(0)
            except Exception as e:
                print(f"\n  ❌ Error inesperado: {e}")
                traceback.print_exc()
                total_errors += 1
                # Continuar con la siguiente referencia
                continue

        # Guardar estado al finalizar cada problema
        save_state(state_file, state)
        print(f"  📊 Progreso: {state['problems'][key]['generated']}/{prob['target']} completado")

    print(f"\n🎉 Completado!")
    print(f"   Generadas esta sesión: {total_generated_session}")
    print(f"   Total acumulado: {state['total_generated']}")
    print(f"   Problemas con error: {total_errors}")
    print(f"   Estado guardado en: {state_file}")


if __name__ == "__main__":
    main()
