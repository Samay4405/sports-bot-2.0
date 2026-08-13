"""LLM provider abstraction layer.

Provides a thin wrapper around LLM providers so the booking agent
doesn't care whether it's talking to Gemini, OpenAI, or a local model.
Swapping providers is a one-line config change.
"""

from __future__ import annotations

import logging
from typing import Protocol, runtime_checkable

from langchain_google_genai import ChatGoogleGenerativeAI

from app.config import settings

logger = logging.getLogger(__name__)


@runtime_checkable
class LLMProvider(Protocol):
    """Protocol for LLM providers — any provider must implement this."""

    def get_llm(self) -> object:
        """Return a LangChain-compatible chat model instance."""
        ...


class GeminiProvider:
    """Google Gemini provider via LangChain.

    Uses ChatGoogleGenerativeAI which is compatible with browser-use's
    Agent class. The free tier of Gemini 2.0 Flash gives 5-15 RPM,
    which is sufficient for our use case with careful rate management.
    """

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        temperature: float = 0.1,
    ):
        self.model = model or settings.llm_model
        self.api_key = api_key or settings.google_api_key
        self.temperature = temperature

        if not self.api_key:
            raise ValueError(
                "GOOGLE_API_KEY is not configured. "
                "Set it in your .env file or pass it directly."
            )

        logger.info("Initializing Gemini provider with model=%s", self.model)

    def get_llm(self) -> ChatGoogleGenerativeAI:
        """Return a configured ChatGoogleGenerativeAI instance.

        Creates a new instance each time to avoid stale state issues
        with long-running processes.
        """
        return ChatGoogleGenerativeAI(
            model=self.model,
            google_api_key=self.api_key,
            temperature=self.temperature,
            convert_system_message_to_human=True,
        )


def get_default_provider() -> GeminiProvider:
    """Factory function for the default LLM provider.

    Returns a GeminiProvider configured from environment variables.
    To swap providers, change this function.
    """
    return GeminiProvider()
