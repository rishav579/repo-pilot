"""
Base LLM Provider Interface.

Defines a clean contract (`generate`, `provider_name`, `model_name`) for any LLM provider
(Mock, OpenAI, Claude, Ollama, vLLM).
"""

from abc import ABC, abstractmethod


class LLMError(Exception):
    """Raised when an LLM provider fails to generate text."""

    pass


class BaseLLMProvider(ABC):
    """
    Abstract interface for LLM text generation providers.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Name of LLM provider (e.g. "mock", "openai")."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Name of LLM model (e.g. "gpt-4o-mini", "mock-llm")."""
        pass

    @abstractmethod
    def generate(
        self, prompt: str, system_instruction: str = "", temperature: float = 0.2
    ) -> str:
        """
        Generate grounded text response from prompt and system instruction.

        Args:
            prompt: Assembled user prompt with context.
            system_instruction: System prompt rules.
            temperature: Sampling temperature (default 0.2 for deterministic code analysis).

        Returns:
            Generated response text string.
        """
        pass
