"""LLM client factory - the ONLY place that knows which provider's SDK/class to
instantiate. Workers never import ChatGroq/ChatCerebras directly; they call
get_chat_model() and get back a LangChain chat model configured per settings.

Switching providers (Groq <-> Cerebras, or adding a new one later) means editing
ONLY this file - no changes anywhere in the six worker modules.
"""
from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel

from complyagent.config import settings


def get_chat_model(model_name: str | None = None) -> BaseChatModel:
    """Returns a configured LangChain chat model for the active provider.

    model_name: override the configured worker_model (e.g. for the Report Writer's
    higher max_tokens need, or to use a different model for one specific worker).
    Defaults to settings.llm.worker_model if not given.
    """
    model = model_name or settings.llm.worker_model
    provider = settings.llm.provider

    if provider == "groq":
        from langchain_groq import ChatGroq
        return ChatGroq(
            model=model,
            temperature=settings.llm.temperature,
            max_tokens=settings.llm.max_tokens,
            api_key=settings.secrets.groq_api_key,
        )

    if provider == "cerebras":
        from langchain_cerebras import ChatCerebras
        return ChatCerebras(
            model=model,
            temperature=settings.llm.temperature,
            max_tokens=settings.llm.max_tokens,
            api_key=settings.secrets.cerebras_api_key,
        )

    raise ValueError(f"Unknown llm.provider in config: {provider!r}")