from abc import ABC, abstractmethod


class ReferenceGeneratorPort(ABC):
    """Writes an alternative solution of a problem with an LLM (AI reference variants).

    Raises `app.domain.errors.GenerationError` when the model is unreachable, misconfigured or
    returns nothing usable; never returns an empty program.
    """

    @abstractmethod
    async def generate(self, *, enunciado: str, reference_code: str, instructions: str, language: str) -> str:
        """Return the source code of one variant, with no markdown fences."""
