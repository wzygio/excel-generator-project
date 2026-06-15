"""LLM manager facade backed by the DeepSeek API.

The public API intentionally keeps the old `llm_manager.chat(...)` shape so
existing parsers, selectors, and report skills do not need broad call-site
changes. Provider names are accepted as legacy labels, but runtime model work
is routed to the configured DeepSeek-compatible chat completions endpoint.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import Any

from openai import OpenAI, OpenAIError

from shared_kernel.config import config

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """Base exception for runtime model calls."""


class LLMConfigurationError(LLMError):
    """Configuration error for the runtime model backend."""


class LLMProviderError(LLMError):
    """Provider error for the runtime model backend."""


class LLMManager:
    """Compatibility facade for project LLM calls.

    DeepSeek is the single backend. The singleton keeps no conversation state;
    every call uses the OpenAI-compatible DeepSeek chat completions API.
    """

    _instance: LLMManager | None = None

    def __new__(cls, *args: Any, **kwargs: Any) -> LLMManager:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        deepseek_client: Any | None = None,
        codex_client: Any | None = None,
    ) -> None:
        injected_client = deepseek_client or codex_client
        if hasattr(self, "_initialized"):
            if injected_client is not None:
                self._deepseek_client = injected_client
            return
        self._initialized = True
        self._deepseek_client = injected_client

    def chat(
        self,
        provider: str = "deepseek",
        messages: list[dict[str, str]] | None = None,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> str:
        """Send a prompt to DeepSeek and return the assistant message text.

        Args keep the legacy LLMManager interface. `provider` is retained for
        compatibility and logged only; it no longer selects multiple backends.
        """
        legacy_provider = (provider or "deepseek").lower().strip()
        if legacy_provider != "deepseek":
            logger.debug("Routing legacy provider=%s through DeepSeek API", legacy_provider)

        try:
            deepseek_config = config.get().llm.deepseek
            client = self._get_deepseek_client()
            completion = client.chat.completions.create(
                model=deepseek_config.model_name or "deepseek-chat",
                messages=self._build_messages(messages, system_prompt),
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )
            return self._extract_message_text(completion)
        except LLMConfigurationError:
            raise
        except OpenAIError as exc:
            raise LLMProviderError(f"DeepSeek API call failed: {exc}") from exc
        except Exception as exc:
            raise LLMProviderError(f"DeepSeek API call failed: {exc}") from exc

    def chat_stream(
        self,
        provider: str = "deepseek",
        messages: list[dict[str, str]] | None = None,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> Iterator[str]:
        """Compatibility streaming API.

        The compatibility facade returns one final message chunk.
        """
        yield self.chat(
            provider=provider,
            messages=messages,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )

    def clear_clients(self) -> None:
        """Reset the DeepSeek client wrapper."""
        self._deepseek_client = None
        logger.info("DeepSeek API client reset")

    def _get_deepseek_client(self) -> OpenAI:
        if self._deepseek_client is not None:
            return self._deepseek_client

        deepseek_config = config.get().llm.deepseek
        if not deepseek_config.api_key:
            raise LLMConfigurationError(
                "DEEPSEEK_API_KEY is missing. Add it to the repository root .env file."
            )

        self._deepseek_client = OpenAI(
            api_key=deepseek_config.api_key,
            base_url=deepseek_config.base_url or "https://api.deepseek.com",
            timeout=deepseek_config.timeout,
            max_retries=deepseek_config.max_retries,
        )
        return self._deepseek_client

    @staticmethod
    def _build_messages(
        messages: list[dict[str, str]] | None,
        system_prompt: str | None,
    ) -> list[dict[str, str]]:
        payload: list[dict[str, str]] = []
        if system_prompt:
            payload.append({"role": "system", "content": system_prompt})
        payload.extend(messages or [])
        return payload

    @staticmethod
    def _extract_message_text(completion: Any) -> str:
        if not completion.choices:
            return ""

        content = completion.choices[0].message.content
        if content is None:
            return ""
        if isinstance(content, str):
            return content
        return str(content)


llm_manager = LLMManager()
