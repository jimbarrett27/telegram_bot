"""Provider-agnostic LLM configuration."""

import logging
import os
import random
import time
from typing import Any, Optional

from dotenv import load_dotenv
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.messages import BaseMessage
from langchain_core.outputs import ChatResult

from gcp_util.secrets import get_openrouter_api_key

load_dotenv()

logger = logging.getLogger(__name__)

_RETRYABLE_STRINGS = ("rate", "429", "500", "502", "503", "overloaded")


class ResilientChatOpenAI:
    """ChatOpenAI with retry logic for transient OpenRouter failures.

    Overrides ``_generate`` to catch silent failures (e.g. ``choices: null``
    responses) and retry with exponential backoff.
    """

    max_retries_on_error: int = 3
    retry_base_delay: float = 2.0

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: Optional[list[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        for attempt in range(self.max_retries_on_error + 1):
            try:
                return super()._generate(messages, stop, run_manager, **kwargs)
            except Exception as e:
                if attempt == self.max_retries_on_error:
                    raise
                err = str(e).lower()
                retryable = (
                    isinstance(e, TypeError) and "nonetype" in err
                ) or any(s in err for s in _RETRYABLE_STRINGS)
                if not retryable:
                    raise
                delay = self.retry_base_delay * (2 ** attempt) + random.uniform(0, 1)
                logger.warning(
                    "LLM call failed (attempt %d/%d), retrying in %.1fs: %s",
                    attempt + 1, self.max_retries_on_error + 1, delay, e,
                )
                time.sleep(delay)


_ResilientChatOpenAIClass = None


def _get_resilient_class():
    """Return a cached ResilientChatOpenAI subclass of ChatOpenAI."""
    global _ResilientChatOpenAIClass
    if _ResilientChatOpenAIClass is None:
        from langchain_openai import ChatOpenAI
        _ResilientChatOpenAIClass = type(
            "ResilientChatOpenAI", (ResilientChatOpenAI, ChatOpenAI), {}
        )
    return _ResilientChatOpenAIClass


def get_llm(
    provider: str = "openrouter",
    model: str | None = None,
    temperature: float = 0.7,
    callbacks: list | None = None,
    thinking_budget: int = 0,
):
    """
    Factory function to get a configured LLM instance.

    Args:
        provider: LLM provider ("openrouter", "openai", "anthropic", "ollama")
        model: Model name (uses provider default if None)
        temperature: Sampling temperature
        callbacks: Optional LangChain callback handlers
        thinking_budget: Max thinking tokens (0 to disable)

    Returns:
        Configured LLM instance
    """
    if provider == "openrouter":
        if not model:
            raise ValueError("model is required for openrouter provider")

        ResilientLLM = _get_resilient_class()
        kwargs: dict[str, Any] = dict(
            model=model,
            temperature=temperature,
            max_tokens=32768,
            openai_api_key=get_openrouter_api_key(),
            openai_api_base="https://openrouter.ai/api/v1",
            callbacks=callbacks,
        )
        if thinking_budget > 0:
            kwargs["extra_body"] = {
                "reasoning": {"max_tokens": thinking_budget},
            }
        return ResilientLLM(**kwargs)

    elif provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model or "gpt-4o-mini",
            temperature=temperature,
            api_key=os.getenv("OPENAI_API_KEY"),
            callbacks=callbacks,
        )

    elif provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=model or "claude-3-5-sonnet-20241022",
            temperature=temperature,
            api_key=os.getenv("ANTHROPIC_API_KEY"),
            callbacks=callbacks,
        )

    elif provider == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(
            model=model or "llama3.2",
            temperature=temperature,
            callbacks=callbacks,
        )

    else:
        raise ValueError(f"Unknown provider: {provider}")
