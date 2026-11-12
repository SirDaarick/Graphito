"""LLM adapters that write AI reference variants (OpenAI-compatible chat API, OpenRouter by default)."""

import logging
import re

import httpx

from app.config import settings
from app.domain.errors import GenerationError
from app.domain.ports.reference_generator_port import ReferenceGeneratorPort

logger = logging.getLogger(__name__)

_FENCE = re.compile(r"```[a-zA-Z+]*\n(.*?)```", re.S)

SYSTEM_PROMPT = (
    "Eres un docente de programacion. Escribes soluciones completas y compilables en C o C++ para "
    "un enunciado. Respondes SOLO con el codigo fuente, sin explicaciones ni bloques markdown."
)


def extract_code(text: str) -> str:
    """The program inside the first markdown fence, or the whole text when there is none."""
    match = _FENCE.search(text or "")
    return (match.group(1) if match else text or "").strip()


class OpenRouterReferenceGenerator(ReferenceGeneratorPort):
    def __init__(self, api_key: str, model: str, base_url: str, timeout: float = 90.0):
        self.api_key, self.model, self.base_url, self.timeout = api_key, model, base_url.rstrip("/"), timeout

    async def generate(self, *, enunciado: str, reference_code: str, instructions: str, language: str) -> str:
        lang = "C++" if language == "cpp" else "C"
        user = (
            f"Lenguaje: {lang}\n\nEnunciado:\n{enunciado}\n\nSolucion de referencia del docente:\n{reference_code}\n\n"
            f"Escribe una solucion DISTINTA a la de referencia que resuelva el mismo problema, siguiendo "
            f"estas instrucciones:\n{instructions}"
        )
        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}],
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
        except (httpx.HTTPError, KeyError, IndexError, ValueError, TypeError) as exc:
            # Never log the key or the response body (it may echo the prompt).
            logger.error("Reference generation failed: %s", type(exc).__name__)
            raise GenerationError("generation_failed", type(exc).__name__) from exc
        code = extract_code(content if isinstance(content, str) else "")
        if not code:
            raise GenerationError("generation_empty", "the model returned no code")
        return code


class StubReferenceGenerator(ReferenceGeneratorPort):
    """Deterministic program for STUB mode and tests: no network, no credits."""

    async def generate(self, *, enunciado: str, reference_code: str, instructions: str, language: str) -> str:
        return f"/* variante: {instructions[:60]} */\n{reference_code}\n"


def get_reference_generator() -> ReferenceGeneratorPort:
    if settings.OPENROUTER_API_KEY:
        return OpenRouterReferenceGenerator(
            settings.OPENROUTER_API_KEY, settings.OPENROUTER_MODEL, settings.OPENROUTER_BASE_URL
        )
    if settings.INFERENCE_MODE.strip().upper() == "STUB":
        return StubReferenceGenerator()
    raise GenerationError("generation_not_configured", "OPENROUTER_API_KEY is not set")
