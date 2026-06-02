"""OpenRouter LLM configuration."""

import logging
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
    model: str,
    temperature: float = 0.7,
    callbacks: list | None = None,
    thinking_budget: int = 0,
):
    """
    Factory function to get a configured LLM instance (OpenRouter only).

    Args:
        model: OpenRouter model slug (e.g. "deepseek/deepseek-v4-flash")
        temperature: Sampling temperature
        callbacks: Optional LangChain callback handlers
        thinking_budget: Max thinking tokens (0 to disable)

    Returns:
        Configured LLM instance
    """
    if not model:
        raise ValueError("model is required")

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
