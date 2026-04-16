import os
import json
from abc import ABC, abstractmethod
from typing import Optional

try:
    import openai
except ImportError:
    openai = None

try:
    import anthropic
except ImportError:
    anthropic = None


class LLMProvider(ABC):
    @abstractmethod
    def chat(self, messages: list[dict]) -> str:
        pass

    @abstractmethod
    def generate(self, prompt: str) -> str:
        pass

    @property
    def name(self) -> str:
        return self.__class__.__name__


class OpenAIProvider(LLMProvider):
    def __init__(self, model: str = "gpt-4o-mini", api_key: Optional[str] = None):
        if openai is None:
            raise ImportError("openai package not installed. Run: pip install openai")
        
        self.model = model
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not set in environment")
        
        self.client = openai.OpenAI(api_key=self.api_key)

    def chat(self, messages: list[dict]) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.7,
        )
        return response.choices[0].message.content

    def generate(self, prompt: str) -> str:
        return self.chat([{"role": "user", "content": prompt}])


class AnthropicProvider(LLMProvider):
    def __init__(self, model: str = "claude-3-haiku-20240307", api_key: Optional[str] = None):
        if anthropic is None:
            raise ImportError("anthropic package not installed. Run: pip install anthropic")
        
        self.model = model
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not set in environment")
        
        self.client = anthropic.Anthropic(api_key=self.api_key)

    def chat(self, messages: list[dict]) -> str:
        system_prompt = ""
        user_prompt = ""
        
        for msg in messages:
            if msg["role"] == "system":
                system_prompt = msg["content"]
            elif msg["role"] == "user":
                user_prompt = msg["content"]
        
        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=system_prompt if system_prompt else None,
            messages=[{"role": "user", "content": user_prompt}]
        )
        return response.content[0].text

    def generate(self, prompt: str) -> str:
        return self.chat([{"role": "user", "content": prompt}])


class OllamaProvider(LLMProvider):
    def __init__(self, model: str = "codellama", base_url: Optional[str] = None):
        self.model = model
        self.base_url = base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    def chat(self, messages: list[dict]) -> str:
        try:
            import requests
        except ImportError:
            raise ImportError("requests package not installed. Run: pip install requests")
        
        response = requests.post(
            f"{self.base_url}/api/chat",
            json={
                "model": self.model,
                "messages": messages,
                "stream": False
            }
        )
        response.raise_for_status()
        return response.json()["message"]["content"]

    def generate(self, prompt: str) -> str:
        return self.chat([{"role": "user", "content": prompt}])


class LiteLLMProvider(LLMProvider):
    def __init__(self, model: str = "gpt-4o-mini", api_key: Optional[str] = None, base_url: Optional[str] = None):
        try:
            import litellm
        except ImportError:
            raise ImportError("litellm package not installed. Run: pip install litellm")
        
        self.model = model
        self.api_key = api_key
        self.base_url = base_url

    def chat(self, messages: list[dict]) -> str:
        import litellm
        response = litellm.completion(
            model=self.model,
            messages=messages,
            api_key=self.api_key,
            base_url=self.base_url,
        )
        return response.choices[0].message.content

    def generate(self, prompt: str) -> str:
        return self.chat([{"role": "user", "content": prompt}])


def get_provider(provider_type: str, model: str = None, **kwargs) -> LLMProvider:
    providers = {
        "openai": OpenAIProvider,
        "anthropic": AnthropicProvider,
        "ollama": OllamaProvider,
        "litellm": LiteLLMProvider,
    }
    
    if provider_type not in providers:
        raise ValueError(f"Provider '{provider_type}' not supported. Available: {list(providers.keys())}")
    
    return providers[provider_type](model=model, **kwargs)


def create_provider_from_config(config: dict) -> LLMProvider:
    provider_type = config.get("provider")
    model = config.get("model")
    
    if not provider_type or not model:
        raise ValueError("Config must have 'provider' and 'model' keys")
    
    extra_kwargs = {}
    if provider_type == "openai":
        extra_kwargs["api_key"] = os.getenv("OPENAI_API_KEY")
    elif provider_type == "anthropic":
        extra_kwargs["api_key"] = os.getenv("ANTHROPIC_API_KEY")
    elif provider_type == "ollama":
        extra_kwargs["base_url"] = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    
    return get_provider(provider_type, model, **extra_kwargs)