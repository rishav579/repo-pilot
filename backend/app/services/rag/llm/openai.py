"""
OpenAI-Compatible LLM Provider — Calls external Chat Completions APIs via httpx.

Supports OpenAI, Claude (via proxy), Ollama, vLLM, LMStudio, or LocalAI endpoints.
"""

import httpx
from app.services.rag.llm.base import BaseLLMProvider, LLMError


class OpenAICompatibleLLMProvider(BaseLLMProvider):
    """
    HTTP client provider for OpenAI-compatible Chat Completions API.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str = "gpt-4o-mini",
        api_base: str = "https://api.openai.com/v1",
        timeout_seconds: float = 30.0,
    ):
        self.api_key = api_key
        self._model_name = model_name
        self.api_base = api_base.rstrip("/")
        self.timeout_seconds = timeout_seconds

    @property
    def provider_name(self) -> str:
        return "openai"

    @property
    def model_name(self) -> str:
        return self._model_name

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def generate(
        self, prompt: str, system_instruction: str = "", temperature: float = 0.2
    ) -> str:
        """Execute chat completion request."""
        url = f"{self.api_base}/chat/completions"
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self._model_name,
            "messages": messages,
            "temperature": temperature,
        }

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                resp = client.post(url, json=payload, headers=self._headers())
                if resp.status_code != 200:
                    raise LLMError(
                        f"LLM API error HTTP {resp.status_code}: {resp.text}"
                    )
                data = resp.json()
                choices = data.get("choices", [])
                if not choices:
                    raise LLMError("Empty choices array from LLM API")
                return choices[0]["message"]["content"]
        except httpx.HTTPError as e:
            raise LLMError(f"HTTP connection error to LLM API: {str(e)}")
        except Exception as e:
            raise LLMError(f"Failed to generate answer from LLM: {str(e)}")
