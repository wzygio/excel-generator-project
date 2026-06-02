"""LLM manager facade backed by Codex CLI.

The public API intentionally keeps the old `llm_manager.chat(...)` shape so
existing parsers, selectors, and report skills do not need broad call-site
changes. Provider names such as "deepseek" and "gemini" are accepted as legacy
labels, but all runtime model work is delegated to Codex CLI.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import Any

from shared_kernel.infrastructure.codex_cli_client import CodexCLIClient, CodexCLIError

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """Base exception for runtime model calls."""


class LLMConfigurationError(LLMError):
    """Configuration error for the runtime model backend."""


class LLMProviderError(LLMError):
    """Provider error for the runtime model backend."""


class LLMManager:
    """Compatibility facade for project LLM calls.

    Codex CLI is the single backend. The singleton keeps no conversation state;
    every call uses `codex exec --ephemeral` through `CodexCLIClient`.
    """

    _instance: LLMManager | None = None

    def __new__(cls, *args: Any, **kwargs: Any) -> LLMManager:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, codex_client: CodexCLIClient | None = None) -> None:
        if hasattr(self, "_initialized"):
            if codex_client is not None:
                self._codex_client = codex_client
            return
        self._initialized = True
        self._codex_client = codex_client or CodexCLIClient()

    def chat(
        self,
        provider: str = "codex",
        messages: list[dict[str, str]] | None = None,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> str:
        """Send a prompt to Codex CLI and return its final message.

        Args keep the legacy LLMManager interface. `provider` is retained for
        compatibility and logged only; it no longer selects DeepSeek/Gemini.
        """
        legacy_provider = (provider or "codex").lower().strip()
        if legacy_provider != "codex":
            logger.debug("Routing legacy provider=%s through Codex CLI", legacy_provider)

        try:
            return self._codex_client.chat(
                messages=messages,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )
        except CodexCLIError as exc:
            raise LLMProviderError(f"Codex CLI call failed: {exc}") from exc
        except Exception as exc:
            raise LLMProviderError(f"Codex CLI call failed: {exc}") from exc

    def chat_stream(
        self,
        provider: str = "codex",
        messages: list[dict[str, str]] | None = None,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> Iterator[str]:
        """Compatibility streaming API.

        Codex CLI returns a final message, so the stream yields one chunk.
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
        """Reset the Codex CLI client wrapper."""
        self._codex_client = CodexCLIClient()
        logger.info("Codex CLI client reset")


llm_manager = LLMManager()
